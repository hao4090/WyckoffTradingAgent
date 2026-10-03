"""Tushare 全市场批量日线抓取（按交易日维度，分块流式处理）。"""

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

# 每次处理多少个交易日。60 ≈ 3 个月，峰值内存约为全量的 1/10。
CHUNK_DAYS = int(os.getenv("TUSHARE_BATCH_CHUNK_DAYS", "60"))
MAX_TRADE_DAYS = int(os.getenv("TUSHARE_BATCH_MAX_TRADE_DAYS", "600"))
FETCH_SLEEP = float(os.getenv("TUSHARE_BATCH_FETCH_SLEEP", "0.12"))
_FETCH_RETRIES = int(os.getenv("TUSHARE_BATCH_FETCH_RETRIES", "3"))


def is_tushare_batch_enabled() -> bool:
    flag = os.getenv("TUSHARE_BATCH_ENABLED", "1").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    from integrations.tushare_client import has_tushare_token

    return has_tushare_token()


def fetch_tushare_market_batch(symbols, window, *, adjust: str = "qfq"):
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
        trade_days = _trade_days(pro, window.start_trade_date, window.end_trade_date)
        if not trade_days:
            logger.warning("Tushare batch: no trade days in window")
            return None
        chunks = [trade_days[i : i + CHUNK_DAYS] for i in range(0, len(trade_days), CHUNK_DAYS)]
        print(f"[tushare] START symbols={len(symbols)} days={len(trade_days)} chunks={len(chunks)}", flush=True)
        # logger.info(
        #    "Tushare batch start: symbols=%d, trade_days=%d, chunks=%d", len(symbols), len(trade_days), len(chunks)
        # )

        collected = {}
        scanned = 0
        failed_chunks = 0
        for idx, chunk_days in enumerate(chunks, start=1):
            sub_panel = []
            for day in chunk_days:
                daily = _fetch_with_retry(pro.daily, trade_date=day, fields=_DAILY_FIELDS)
                if daily is None or daily.empty:
                    continue
                scanned += len(daily)
                hit = daily[daily["ts_code"].isin(wanted)]
                if not hit.empty:
                    sub_panel.append(hit)
                _sleep()
            if not sub_panel:
                failed_chunks += 1
                continue
            block = pd.concat(sub_panel, ignore_index=True)
            del sub_panel
            if adjust == "qfq":
                factor = _fetch_with_retry(pro.adj_factor, trade_date=chunk_days[-1], fields=_ADJ_FIELDS)
                if factor is not None and not factor.empty:
                    block = _apply_qfq(block, factor)
                else:
                    block = _add_display_columns(block)
            for sym, frame in _split_by_symbol(block).items():
                collected.setdefault(sym, []).append(frame)
            del block
            if idx % 5 == 0 or idx == len(chunks):
                logger.info(
                    "Tushare batch progress: chunk %d/%d, symbols=%d, scanned=%d",
                    idx,
                    len(chunks),
                    len(collected),
                    scanned,
                )
        if not collected:
            logger.warning("Tushare batch: all chunks returned empty")
            return None
        out = {}
        for sym, frames in collected.items():
            out[sym] = pd.concat(frames, ignore_index=True).sort_values("日期").reset_index(drop=True)
        collected.clear()
        logger.info(
            "Tushare batch done: symbols=%d, rows=%d, failed_chunks=%d",
            len(out),
            sum(len(v) for v in out.values()),
            failed_chunks,
        )
        return out
    except Exception as exc:
        logger.warning("Tushare batch failed, falling back: %s", exc)
        return None


def _to_ts_code_set(symbols):
    out = set()
    for symbol in symbols:
        try:
            code = to_ts_code(str(symbol).strip())
        except Exception:
            continue
        if code:
            out.add(code)
    return out


def _trade_days(pro, start: date, end: date):
    span = (end - start).days
    if span < 0:
        return []
    lookback = min(span + 20, MAX_TRADE_DAYS + 40)
    cal = _fetch_with_retry(
        pro.trade_cal,
        exchange="SSE",
        start_date=date.fromordinal(start.toordinal() - lookback).strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        is_open="1",
    )
    if cal is None or cal.empty or "cal_date" not in cal.columns:
        return []
    days = sorted(str(d) for d in cal["cal_date"].tolist())
    return [d for d in days if d >= start.strftime("%Y%m%d")][-MAX_TRADE_DAYS:]


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


def _sleep():
    if FETCH_SLEEP > 0:
        time.sleep(FETCH_SLEEP)


def _apply_qfq(frame, factors):
    factor_map = (
        factors[["ts_code", "trade_date", "adj_factor"]]
        .drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        .copy()
    )
    merged = frame.merge(factor_map, on=["ts_code", "trade_date"], how="left")
    base = (
        merged.dropna(subset=["adj_factor"])
        .sort_values("trade_date")
        .groupby("ts_code", as_index=False)["adj_factor"]
        .last()
        .rename(columns={"adj_factor": "base_adj_factor"})
    )
    merged = merged.merge(base, on="ts_code", how="left")
    scale = merged["adj_factor"] / merged["base_adj_factor"]
    scale = scale.where(scale.notna() & (merged["base_adj_factor"] > 0), 1.0)
    for column in ("open", "high", "low", "close"):
        if column in merged.columns:
            merged[column] = (pd.to_numeric(merged[column], errors="coerce") * scale).round(4)
    return _add_display_columns(merged)


def _add_display_columns(frame):
    out = frame.copy()
    if "换手率" not in out.columns:
        out["换手率"] = pd.NA
    if "振幅" not in out.columns:
        out["振幅"] = pd.NA
    return out


def _normalize_frame(frame):
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
    if "成交量" in out.columns:
        out["成交量"] = pd.to_numeric(out["成交量"], errors="coerce") * 100
    if "成交额" in out.columns:
        out["成交额"] = pd.to_numeric(out["成交额"], errors="coerce") * 1000
    out["换手率"] = pd.NA
    out["振幅"] = pd.NA
    dates = out["日期"].astype(str)
    out["日期"] = dates.str[:4] + "-" + dates.str[4:6] + "-" + dates.str[6:8]
    out = out.dropna(subset=["日期", "收盘"]).sort_values("日期").reset_index(drop=True)
    # 漏斗下游读英文 volume/vol，缺这列换手率门槛会静默失效
    out["volume"] = out["成交量"] if "成交量" in out.columns else pd.NA
    out["vol"] = out["volume"]
    out["close"] = out["收盘"] if "收盘" in out.columns else out.get("close")
    # 漏斗下游按英文列名读（date/volume/close），缺列会静默失效
    out["date"] = out["日期"]
    out["volume"] = out["成交量"]
    out["vol"] = out["成交量"]
    out["close"] = out["收盘"]
    out["open"] = out["开盘"]
    out["high"] = out["最高"]
    out["low"] = out["最低"]
    out["amount"] = out["成交额"]
    out["pct_chg"] = out["涨跌幅"]
    return out.copy()


def _split_by_symbol(frame):
    out = {}
    if "ts_code" not in frame.columns:
        logger.warning("Tushare batch: ts_code column missing")
        return out
    for ts_code, group in frame.groupby("ts_code", sort=False):
        symbol = str(ts_code).split(".")[0]
        if symbol:
            out[symbol] = _normalize_frame(group.drop(columns=["ts_code"]))
    return out
