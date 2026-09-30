"""Tushare 全市场批量日线抓取（按交易日维度，非按标的）。

为什么需要这个模块
------------------
integrations/data_source_tushare.fetch_stock_tushare() 是 per-symbol 调用
（pro_bar(ts_code=...)），5347 只票 = 5347 次请求，这是 funnel 阶段耗时 40+ 分钟的根因。

Tushare 的 pro.daily() / pro.adj_factor() 支持按 trade_date 维度拉取，
一次返回当天全市场 5000+ 只。取 N 个交易日 = 2N 次请求（daily + adj_factor），
与标的数量无关。N=300 时约 600 次请求，比原来快约 9 倍。

复权口径
--------
pro.daily() 返回不复权价，前复权需自行计算（Tushare 官方口径）：

    qfq_price = close * adj_factor / 该股窗口内最后一个交易日的 adj_factor

注意基准因子是 每只股票各自的窗口末日因子，不能用全局值。
ts.pro_bar(adj="qfq") 也是以 end_date 为基准往前复权，口径一致。

数据源优先顺序
--------------
tools/data_fetcher.fetch_all_ohlcv 的顺序变为：
TickFlow 批量 -> Tushare 全市场 -> per-symbol fallback 链。

任一环节抛错都返回 None，由上层静默降级，不影响既有行为。
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date

import pandas as pd

from integrations.data_source_format import STOCK_HIST_COLUMNS, to_ts_code

logger = logging.getLogger(__name__)

_DAILY_FIELDS = "ts_code,trade_date,open,high,low,close,vol,amount,pct_chg"
_ADJ_FIELDS = "ts_code,trade_date,adj_factor"

MAX_TRADE_DAYS = int(os.getenv("TUSHARE_BATCH_MAX_TRADE_DAYS", "600"))
FETCH_SLEEP = float(os.getenv("TUSHARE_BATCH_FETCH_SLEEP", "0.15"))
_FETCH_RETRIES = int(os.getenv("TUSHARE_BATCH_FETCH_RETRIES", "3"))


def is_tushare_batch_enabled() -> bool:
    """是否启用 Tushare 全市场批量路径。"""
    flag = os.getenv("TUSHARE_BATCH_ENABLED", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    from integrations.tushare_client import has_tushare_token

    return has_tushare_token()


def fetch_tushare_market_batch(symbols, window, *, adjust: str = "qfq"):
    """按交易日维度抓取全市场日线，返回 {6位代码: DataFrame}。"""
    if not symbols or not is_tushare_batch_enabled():
        return None
    if adjust not in {"qfq", "none"}:
        return None

    try:
        from integrations.tushare_client import get_pro

        pro = get_pro()
        if pro is None:
            return None

        wanted = _to_ts_code_set(symbols)
        if not wanted:
            return None

        start = window.start_trade_date
        end = window.end_trade_date
        trade_days = _trade_days(pro, start, end)
        if not trade_days:
            logger.warning("Tushare batch: no trade days in %s~%s", start, end)
            return None

        logger.info(
            "Tushare batch start: symbols=%d, trade_days=%d, calls~%d",
            len(symbols), len(trade_days), len(trade_days) * 2,
        )

        panel = []
        factor_panel = []
        collected = 0
        for index, day in enumerate(trade_days, start=1):
            daily = _fetch_with_retry(pro.daily, trade_date=day, fields=_DAILY_FIELDS)
            if daily is not None and not daily.empty:
                panel.append(daily[daily["ts_code"].isin(wanted)])
                collected += len(daily)

            if adjust == "qfq":
                factor = _fetch_with_retry(
                    pro.adj_factor, trade_date=day, fields=_ADJ_FIELDS
                )
                if factor is not None and not factor.empty:
                    factor_panel.append(factor)
            _sleep_between(index, len(trade_days))

        if not panel:
            logger.warning("Tushare batch: all daily calls returned empty")
            return None

        frame = pd.concat(panel, ignore_index=True)
        if adjust == "qfq" and factor_panel:
            frame = _apply_qfq(frame, pd.concat(factor_panel, ignore_index=True))
        else:
            frame = _add_display_columns(frame)

        # 关键：先按 ts_code 拆分，再做列归一化
        # 归一化会只保留中文列、把 ts_code 丢掉，顺序反了就拆不出来
        out = _split_by_symbol(frame)
        logger.info(
            "Tushare batch done: symbols=%d, rows=%d, market_rows_scanned=%d",
            len(out), len(frame), collected,
        )
        return out
    except Exception as exc:
        logger.warning("Tushare batch failed, falling back: %s", exc)
        return None


def _to_ts_code_set(symbols) -> set:
    out = set()
    for symbol in symbols:
        try:
            code = to_ts_code(str(symbol).strip())
        except Exception:
            continue
        if code:
            out.add(code)
    return out


def _trade_days(pro, start: date, end: date) -> list:
    """返回 [start, end] 区间内的交易日（YYYYMMDD 字符串），升序。"""
    span = (end - start).days
    if span < 0:
        return []
    lookback = min(span + 20, MAX_TRADE_DAYS + 40)
    cal_start = start.toordinal() - lookback
    cal = pro.trade_cal(
        exchange="SSE",
        start_date=date.fromordinal(cal_start).strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        is_open="1",
    )
    if cal is None or cal.empty or "cal_date" not in cal.columns:
        return []
    days = sorted(str(d) for d in cal["cal_date"].tolist())
    lo = start.strftime("%Y%m%d")
    return [d for d in days if d >= lo][-MAX_TRADE_DAYS:]


def _fetch_with_retry(func, **kwargs):
    for attempt in range(1, _FETCH_RETRIES + 1):
        try:
            return func(**kwargs)
        except Exception as exc:
            if attempt >= _FETCH_RETRIES:
                logger.warning("Tushare %s failed after %d: %s", kwargs, attempt, exc)
                return None
            time.sleep(min(2 ** (attempt - 1), 8))
    return None


def _sleep_between(index: int, total: int) -> None:
    if FETCH_SLEEP <= 0 or index >= total:
        return
    time.sleep(FETCH_SLEEP)


def _apply_qfq(frame: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    """按 Tushare 官方口径计算前复权价，保留 ts_code。

    qfq = close * adj_factor / 该股窗口内最后一个交易日的 adj_factor
    """
    factor_map = (
        factors[["ts_code", "trade_date", "adj_factor"]]
        .drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        .copy()
    )
    merged = frame.merge(factor_map, on=["ts_code", "trade_date"], how="left")

    # 每只股票的基准因子 = 其窗口内最后一个交易日的因子
    base = (
        merged.dropna(subset=["adj_factor"])
        .sort_values("trade_date")
        .groupby("ts_code", as_index=False)["adj_factor"]
        .last()
        .rename(columns={"adj_factor": "base_adj_factor"})
    )
    merged = merged.merge(base, on="ts_code", how="left")

    # 因子缺失（新股/停牌）时退回不复权，避免整列变 NaN
    scale = merged["adj_factor"] / merged["base_adj_factor"]
    scale = scale.where(scale.notna() & (merged["base_adj_factor"] > 0), 1.0)

    for column in ("open", "high", "low", "close"):
        if column in merged.columns:
            merged[column] = (
                pd.to_numeric(merged[column], errors="coerce") * scale
            ).round(4)
    return _add_display_columns(merged)


def _add_display_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """补内部标准列占位，保留 ts_code 供后续按标的拆分。"""
    out = frame.copy()
    if "换手率" not in out.columns:
        out["换手率"] = pd.NA
    if "振幅" not in out.columns:
        out["振幅"] = pd.NA
    return out


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """转成项目内部标准列（中文列名 + 成交量/成交额单位换算）。"""
    out = frame.rename(
        columns={
            "trade_date": "日期",
            "open": "开盘",
            "high": "最高",
            "low": "最低",
            "close": "收盘",
            "vol": "成交量",
            "amount": "成交额",
            "pct_chg": "涨跌幅",
        }
    )
    # Tushare: vol 单位=手, amount 单位=千元 -> 对齐内部口径（股 / 元）
    if "成交量" in out.columns:
        out["成交量"] = pd.to_numeric(out["成交量"], errors="coerce") * 100
    if "成交额" in out.columns:
        out["成交额"] = pd.to_numeric(out["成交额"], errors="coerce") * 1000
    out["换手率"] = pd.NA
    out["振幅"] = pd.NA

    dates = out["日期"].astype(str)
    out["日期"] = dates.str[:4] + "-" + dates.str[4:6] + "-" + dates.str[6:8]
    out = out.dropna(subset=["日期", "收盘"])
    out = out.sort_values("日期").reset_index(drop=True)
    keep = [c for c in STOCK_HIST_COLUMNS if c in out.columns]
    return out[keep].copy()


def _split_by_symbol(frame: pd.DataFrame) -> dict:
    """把全市场面板拆成 {6位代码: DataFrame}（拆分后再做列归一化）。"""
    out = {}
    if "ts_code" not in frame.columns:
        logger.warning("Tushare batch: ts_code 列缺失，无法按标的拆分")
        return out
    for ts_code, group in frame.groupby("ts_code", sort=False):
        symbol = str(ts_code).split(".")[0]
        if not symbol:
            continue
        out[symbol] = _normalize_frame(group.drop(columns=["ts_code"]))
    return out
