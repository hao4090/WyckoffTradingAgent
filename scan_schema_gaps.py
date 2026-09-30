"""
扫描代码里所有 Supabase 表访问，比对线上 schema，生成缺口 SQL。

用法
----
    # 1. 导出线上列（Supabase SQL Editor）：
    #    SELECT jsonb_object_agg(table_name, columns) FROM (
    #      SELECT table_name, jsonb_agg(column_name) AS columns
    #      FROM information_schema.columns
    #      WHERE table_schema='public' AND table_name NOT LIKE 'pg_%'
    #      GROUP BY table_name) t;
    #    结果存成 actual_columns.json
    # 2. python scan_schema_gaps.py
    # 3. python scan_schema_gaps.py --actual actual_columns.json --out fix.sql
    #    4. fix.sql 贴到 Supabase SQL Editor 执行
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "artifacts", "logs", "data"}
FAKE_TABLES = {"x", "tmp", "test", "tmp_table", "none", "unknown", "data", "row", "obj"}

QUERY_METHODS = {"select", "eq", "neq", "order", "in_", "gt", "gte", "lt", "lte",
                 "like", "ilike", "is_", "contains", "overlaps", "match"}
WRAPPER_FUNCS = {"_execute_upsert", "_replace_derived_rows", "upsert",
                 "_upsert", "_replace_rows", "_write_rows"}

TYPE_HINTS = [
    (r"(_at|_date|observed|closed|updated|created|inserted|opened)$", "text"),
    (r"^(id|_id)$", "text"),
    (r"(count|size|rank|days|horizon|met_count|touch_count|selected_for_ai|"
     r"ai_recommended|is_fill|useful|risk_evaluated|ranked|eligible)", "text"),
    (r"(pct|score|rate|weight|multiplier|price|amount|volume|value|cash|equity|"
     r"drawdown|mfe|mae|return|change|position|runs|hits)", "text"),
]


def infer_type(col: str) -> str:
    """按列名猜类型。猜不准退化成 text —— 永远安全，PostgREST 会隐式转换。"""
    c = col.lower()
    for pat, typ in TYPE_HINTS:
        if re.search(pat, c):
            return typ
    return "text"


def is_real_table(name: str) -> bool:
    return name not in FAKE_TABLES and len(name) >= 4


def iter_py(root: Path):
    for p in sorted(root.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def build_global_constants(root: Path) -> dict[str, str]:
    """全仓库扫描 TABLE_XXX -> 表名。常量常在 core/constants.py 被别处引用。"""
    out: dict[str, str] = {}
    for py in iter_py(root):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
            for target in targets:
                if not target.id.startswith("TABLE_"):
                    continue
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    out[target.id] = node.value.value
    return out


def literal_str(node) -> str:
    """只接受字面量字符串；变量/拼接返回空。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def table_refs_in(node: ast.AST, consts: dict[str, str]) -> set[str]:
    found: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "table":
            if sub.args:
                arg = sub.args[0]
                if isinstance(arg, ast.Name) and arg.id in consts:
                    found.add(consts[arg.id])
                else:
                    s = literal_str(arg)
                    if s and s.islower():
                        found.add(s)
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            m = re.search(r"rest/v1/([a-z_]+)", sub.value)
            if m:
                found.add(m.group(1))
        if isinstance(sub, ast.Name) and sub.id in consts:
            found.add(consts[sub.id])
    return {f for f in found if is_real_table(f)}


def fields_in(node: ast.AST) -> tuple[set[str], set[str]]:
    cols: set[str] = set()
    conflicts: set[str] = set()

    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr in QUERY_METHODS and sub.args:
                for part in re.split(r"[,\s]+", literal_str(sub.args[0])):
                    part = part.strip()
                    if part and part != "*" and re.match(r"^[a-z_][a-z0-9_]*$", part):
                        cols.add(part)
            if sub.func.attr == "upsert":
                for kw in sub.keywords:
                    if kw.arg == "on_conflict":
                        for part in re.split(r"[,\s]+", literal_str(kw.value)):
                            if part:
                                conflicts.add(part)

    # 包装函数的 on_conflict 走位置参数：
    #   _execute_upsert(TABLE_X, rows, "a,b")
    #   _replace_derived_rows(TABLE_X, rows, {...}, "a,b", ...)
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        if isinstance(sub.func, ast.Name):
            fname = sub.func.id
        elif isinstance(sub.func, ast.Attribute):
            fname = sub.func.attr
        else:
            continue
        if fname not in WRAPPER_FUNCS:
            continue
        for arg in sub.args[2:]:
            s = literal_str(arg)
            if not s or "," not in s:
                continue
            for part in re.split(r"[,\s]+", s):
                if part and re.match(r"^[a-z_][a-z0-9_]*$", part):
                    conflicts.add(part)
            break
    return cols, conflicts


def dict_keys_in(node: ast.AST) -> set[str]:
    keys: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Dict):
            for k in sub.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    if re.match(r"^[a-z_][a-z0-9_]*$", k.value):
                        keys.add(k.value)
    return keys


def scan(root: Path, aggressive: bool = False) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    table_cols: dict[str, set[str]] = defaultdict(set)
    table_conflicts: dict[str, set[str]] = defaultdict(set)
    global_consts = build_global_constants(root)

    for py in iter_py(root):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        file_tables: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            tables = table_refs_in(node, global_consts)
            if not tables:
                continue
            cols, conflicts = fields_in(node)
            file_tables |= tables
            for t in tables:
                table_cols[t] |= cols
                table_conflicts[t] |= conflicts

        # 文件级字典键默认关闭。跨文件构造的 upsert payload 静态无法追踪，
        # 但把整个文件的字典键都算进去会严重注水
        # （signal_observations 能虚报到 180+ 字段，真实表只有 55 列）。
        # 漏报的字段由 workflow 报错精确指出，比注水划算。
        if file_tables and aggressive:
            file_dict_keys: set[str] = set()
            for node in ast.walk(tree):
                file_dict_keys |= dict_keys_in(node)
            for t in file_tables:
                table_cols[t] |= file_dict_keys

    return dict(table_cols), dict(table_conflicts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--actual", help="线上列 baseline JSON")
    ap.add_argument("--out", help="输出 ALTER SQL 文件")
    ap.add_argument("--aggressive", action="store_true",
                    help="文件级字典键也计入（更全但噪音大）")
    args = ap.parse_args()

    table_cols, conflicts = scan(ROOT, aggressive=args.aggressive)

    print("=" * 76)
    print("WyckoffTradingAgent — Supabase schema 缺口扫描")
    print("=" * 76)

    if not args.actual:
        print(f"\n代码访问了 {len(table_cols)} 张表：\n")
        for t in sorted(table_cols):
            if not is_real_table(t):
                continue
            oc = ",".join(sorted(conflicts.get(t, []))) or "-"
            print(f"  {t:36} {len(table_cols[t]):3d} 字段  |  on_conflict: {oc}")
        return 0

    with open(args.actual, encoding="utf-8") as f:
        baseline = json.load(f)
    if "actual_columns" in baseline:
        baseline = baseline["actual_columns"]

    sql: list[str] = [
        "-- 自动生成：Supabase schema 缺口修复",
        "-- 生成器: scan_schema_gaps.py",
        "",
    ]
    total_tables = 0
    total_cols = 0

    print(f"\n{'表':34} {'状态':12} 缺失字段")
    print("-" * 76)
    for t in sorted(table_cols):
        if not is_real_table(t):
            continue
        have = set(baseline.get(t, []))
        if not have:
            print(f"{t:34} {'TABLE_MISSING':12} -")
            sql += [f"\n-- 表不存在需建表: {t}（参考 scripts/print_*_ddl.py）"]
            total_tables += 1
            continue
        missing = sorted(set(table_cols[t]) - have)
        if not missing:
            print(f"{t:34} {'OK':12} -")
            continue
        total_tables += 1
        total_cols += len(missing)
        print(f"{t:34} {'MISSING':12} {len(missing)}  -> {', '.join(missing[:8])}"
              + (" ..." if len(missing) > 8 else ""))
        sql.append(f"\n-- {t}: 补 {len(missing)} 列")
        for c in missing:
            sql.append(f"ALTER TABLE public.{t} ADD COLUMN IF NOT EXISTS {c} {infer_type(c)};")

        oc = sorted(conflicts.get(t, []) - have)
        if len(oc) > 1:
            idx = f"{t}_" + "_".join(oc[:4]) + "_key"
            sql += [
                f"\n-- {t}: on_conflict 唯一索引（建之前先查重）",
                f"-- SELECT {', '.join(oc)}, count(*) FROM public.{t} "
                f"GROUP BY {', '.join(oc)} HAVING count(*)>1;",
                f"CREATE UNIQUE INDEX IF NOT EXISTS {idx} ON public.{t} ({', '.join(oc)});",
            ]

    print("-" * 76)
    print(f"合计：{total_tables} 张表有缺口，{total_cols} 个字段缺失")

    real_tables = [t for t in sorted(table_cols) if is_real_table(t)]
    sql += [
        "",
        "-- 解除非主键列 NOT NULL（代码会传 NULL；42P16 表示撞到主键列）",
        "DO $$",
        "DECLARE t TEXT; col TEXT;",
        "BEGIN",
        "  FOREACH t IN ARRAY ARRAY[" + ", ".join(f"'{x}'" for x in real_tables) + "] LOOP",
        "    FOR col IN",
        "      SELECT a.attname FROM pg_attribute a",
        "      JOIN pg_class c ON c.oid = a.attrelid",
        "      JOIN pg_namespace n ON n.oid = c.relnamespace",
        "      WHERE n.nspname='public' AND c.relname=t",
        "        AND a.attnotnull AND a.attnum > 0",
        "        AND NOT EXISTS (SELECT 1 FROM pg_constraint k",
        "                        WHERE k.conrelid=c.oid AND k.contype='p'",
        "                          AND a.attnum = ANY(k.conkey))",
        "    LOOP",
        "      EXECUTE format('ALTER TABLE public.%I ALTER COLUMN %I DROP NOT NULL', t, col);",
        "    END LOOP;",
        "  END LOOP;",
        "END $$;",
    ]

    if args.out:
        out = Path(args.out)
        out.write_text("\n".join(sql), encoding="utf-8")
        print(f"\n[OK] SQL 已写入 {out}（{out.stat().st_size} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())