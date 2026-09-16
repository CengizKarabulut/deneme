from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
BANDS = ((20.0, 80.0), (25.0, 75.0), (30.0, 70.0))
RVOL_MIN_VALUES = (0.0, 1.0, 1.5, 2.0)
PROD_LOWER = 25.0
PROD_UPPER = 75.0
PROD_RVOL = 1.0
WARMUP = 60


def load_symbols(con: sqlite3.Connection, exchange: str, period: str) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol",
        (exchange, period),
    ).fetchall()
    return [str(r[0]) for r in rows]


def load_frame(con: sqlite3.Connection, symbol: str, exchange: str, period: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        """SELECT candle_time, open, high, low, close, volume
           FROM candles WHERE symbol=? AND exchange=? AND period=? ORDER BY candle_time""",
        con,
        params=(symbol, exchange, period),
    )
    if df.empty:
        return df
    df["candle_time"] = pd.to_datetime(df["candle_time"], errors="coerce")
    df = df.dropna(subset=["candle_time"]).set_index("candle_time")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close", "volume"])


def rsi14(close: pd.Series, period: int = 14) -> pd.Series:
    # Exact port of production TechnicalMarketContext._rsi_series.
    values = close.astype(float).to_list()
    result = [np.nan] * len(values)
    if len(values) <= period:
        return pd.Series(result, index=close.index, dtype=float)
    changes = [current - previous for previous, current in zip(values, values[1:])]
    gains = [max(value, 0.0) for value in changes]
    losses = [max(-value, 0.0) for value in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period

    def value() -> float:
        if average_loss == 0:
            return 100.0 if average_gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + average_gain / average_loss)

    result[period] = value()
    for index in range(period, len(changes)):
        average_gain = (average_gain * (period - 1) + gains[index]) / period
        average_loss = (average_loss * (period - 1) + losses[index]) / period
        result[index + 1] = value()
    return pd.Series(result, index=close.index, dtype=float)


def atr14(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat(
        [(df["high"] - df["low"]), (df["high"] - prev).abs(), (df["low"] - prev).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    # Recursive EMA seeded from first observation, matching production recursive EMA behaviour.
    values = series.astype(float).to_numpy()
    out = np.empty(len(values), dtype=float)
    if not len(values):
        return pd.Series(dtype=float, index=series.index)
    alpha = 2.0 / (period + 1.0)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return pd.Series(out, index=series.index)


def forward_max(s: pd.Series, h: int) -> pd.Series:
    return s.shift(-1).iloc[::-1].rolling(h, min_periods=h).max().iloc[::-1]


def forward_min(s: pd.Series, h: int) -> pd.Series:
    return s.shift(-1).iloc[::-1].rolling(h, min_periods=h).min().iloc[::-1]


def enrich(df: pd.DataFrame, window: int, min_history: int) -> pd.DataFrame:
    x = df.copy()
    close = x["close"].astype(float)
    volume = x["volume"].astype(float)
    turnover = close * volume
    x["rsi"] = rsi14(close)
    x["baseline_volume"] = volume.shift(1).rolling(window, min_periods=min_history).mean()
    x["rvol"] = volume / x["baseline_volume"].replace(0.0, np.nan)
    x["turnover_current_inclusive"] = turnover.rolling(window, min_periods=1).mean()
    x["turnover_previous_only"] = turnover.shift(1).rolling(window, min_periods=min_history).mean()
    x["atr14"] = atr14(x)
    x["ema21"] = ema(close, 21)
    x["ema55"] = ema(close, 55)
    x["bar_index"] = np.arange(len(x))

    for h in HORIZONS:
        end = close.shift(-h)
        hi = forward_max(x["high"].astype(float), h)
        lo = forward_min(x["low"].astype(float), h)
        x[f"h{h}_return_pct"] = (end / close - 1.0) * 100.0
        x[f"h{h}_bull_favorable_pct"] = (hi / close - 1.0) * 100.0
        x[f"h{h}_bull_adverse_pct"] = (lo / close - 1.0) * 100.0
        x[f"h{h}_bear_favorable_pct"] = (1.0 - lo / close) * 100.0
        x[f"h{h}_bear_adverse_pct"] = (hi / close - 1.0) * 100.0
        x[f"h{h}_range_atr"] = (hi - lo) / x["atr14"].replace(0.0, np.nan)
    return x


def split_samples(events: pd.DataFrame, fraction: float) -> pd.DataFrame:
    if events.empty:
        events["sample"] = pd.Series(dtype=str)
        return events
    ordered = events.sort_values(["signal_time", "symbol"]).copy()
    n = len(ordered)
    hold = max(1, int(math.ceil(n * fraction))) if n >= 5 else 0
    ordered["sample"] = "research"
    if hold:
        ordered.iloc[-hold:, ordered.columns.get_loc("sample")] = "holdout"
    return ordered


def event_rows(data: pd.DataFrame, lower: float, upper: float, rvol_min: float, min_price: float, min_turnover: float) -> pd.DataFrame:
    eligible = (
        (data["bar_index"] >= WARMUP - 1)
        & (data["close"] >= min_price)
        & (data["turnover_current_inclusive"] >= min_turnover)
        & data["rsi"].notna()
        & data["rvol"].notna()
        & (data["rvol"] >= rvol_min)
    )
    oversold = eligible & (data["rsi"] <= lower)
    overbought = eligible & (data["rsi"] >= upper)
    hit = oversold | overbought
    if not bool(hit.any()):
        return pd.DataFrame()
    prior_hit = hit.shift(1, fill_value=False)
    part = data.loc[hit].copy()
    part["side"] = np.where(oversold.loc[hit], "oversold_bullish", "overbought_bearish")
    part["direction_sign"] = np.where(part["side"] == "oversold_bullish", 1.0, -1.0)
    part["fresh_state"] = (~prior_hit.loc[hit]).astype(bool).to_numpy()
    for h in HORIZONS:
        part[f"h{h}_aligned_return_pct"] = part[f"h{h}_return_pct"] * part["direction_sign"]
        bull = part["side"] == "oversold_bullish"
        part[f"h{h}_favorable_pct"] = np.where(
            bull, part[f"h{h}_bull_favorable_pct"], part[f"h{h}_bear_favorable_pct"]
        )
        part[f"h{h}_adverse_pct"] = np.where(
            bull, -part[f"h{h}_bull_adverse_pct"], part[f"h{h}_bear_adverse_pct"]
        )
    return part


def summarize(events: pd.DataFrame, lower: float, upper: float, rvol_min: float) -> list[dict]:
    rows = []
    if events.empty:
        return rows
    for sample, sample_group in events.groupby("sample", sort=True):
        for side in ("all", "oversold_bullish", "overbought_bearish"):
            group = sample_group if side == "all" else sample_group[sample_group["side"] == side]
            if group.empty:
                continue
            base = {
                "lower_rsi": lower,
                "upper_rsi": upper,
                "rvol_min": rvol_min,
                "sample": str(sample),
                "side": side,
                "events": int(len(group)),
                "symbols": int(group["symbol"].nunique()),
                "fresh_state_rate_pct": float(group["fresh_state"].mean() * 100.0),
                "median_rsi": float(group["rsi"].median()),
                "median_rvol": float(group["rvol"].median()),
            }
            for h in HORIZONS:
                valid = group[group[f"h{h}_aligned_return_pct"].notna()]
                row = dict(base)
                row["horizon"] = h
                row["n"] = int(len(valid))
                if not valid.empty:
                    row["median_aligned_return_pct"] = float(valid[f"h{h}_aligned_return_pct"].median())
                    row["mean_aligned_return_pct"] = float(valid[f"h{h}_aligned_return_pct"].mean())
                    row["directional_hit_rate_pct"] = float((valid[f"h{h}_aligned_return_pct"] > 0).mean() * 100.0)
                    row["median_favorable_pct"] = float(valid[f"h{h}_favorable_pct"].median())
                    row["median_adverse_pct"] = float(valid[f"h{h}_adverse_pct"].median())
                    row["median_range_atr"] = float(valid[f"h{h}_range_atr"].median())
                rows.append(row)
    return rows


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{Path(args.db).resolve().as_posix()}?mode=ro", uri=True)
    try:
        symbols = load_symbols(con, args.exchange, args.period)
        config_parts: dict[tuple[float, float, float], list[pd.DataFrame]] = {
            (lo, hi, rv): [] for lo, hi in BANDS for rv in RVOL_MIN_VALUES
        }
        usable = 0
        for symbol in symbols:
            raw = load_frame(con, symbol, args.exchange, args.period)
            if len(raw) < WARMUP + max(HORIZONS):
                continue
            data = enrich(raw, args.window, args.min_history)
            data["symbol"] = symbol
            data["signal_time"] = data.index
            usable += 1
            for lo, hi in BANDS:
                for rv in RVOL_MIN_VALUES:
                    part = event_rows(data, lo, hi, rv, args.min_price, args.min_turnover)
                    if not part.empty:
                        config_parts[(lo, hi, rv)].append(part)

        summary_rows = []
        baseline = pd.DataFrame()
        for (lo, hi, rv), parts in config_parts.items():
            if not parts:
                continue
            events = split_samples(pd.concat(parts, ignore_index=True), args.holdout_fraction)
            summary_rows.extend(summarize(events, lo, hi, rv))
            if (lo, hi, rv) == (PROD_LOWER, PROD_UPPER, PROD_RVOL):
                baseline = events.copy()

        pd.DataFrame(summary_rows).to_csv(out / f"extreme_rsi_summary_{args.period}.csv", index=False)
        baseline.to_csv(out / f"extreme_rsi_events_{args.period}.csv", index=False)
        manifest = {
            "scanner": "technical.extreme_rsi",
            "period": args.period,
            "symbols_in_db": len(symbols),
            "symbols_usable": usable,
            "production_rule": {
                "lower_rsi": PROD_LOWER,
                "upper_rsi": PROD_UPPER,
                "rvol_min": PROD_RVOL,
                "minimum_turnover": args.min_turnover,
                "minimum_price": args.min_price,
                "turnover": "current-inclusive 20-bar average matching production",
                "rsi": "exact production RSI14 Wilder-style port",
                "direction": "RSI<=25 bullish; RSI>=75 bearish",
            },
            "parameter_grid": {
                "bands": [list(x) for x in BANDS],
                "rvol_min": list(RVOL_MIN_VALUES),
            },
            "holdout_fraction": args.holdout_fraction,
            "baseline_events": int(len(baseline)),
        }
        (out / f"extreme_rsi_manifest_{args.period}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    finally:
        con.close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Research-only technical.extreme_rsi audit")
    p.add_argument("--db", required=True)
    p.add_argument("--period", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--exchange", default="BIST")
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--min-history", type=int, default=5)
    p.add_argument("--min-price", type=float, default=1.0)
    p.add_argument("--min-turnover", type=float, default=20_000_000.0)
    p.add_argument("--holdout-fraction", type=float, default=0.20)
    return p


if __name__ == "__main__":
    run(parser().parse_args())
