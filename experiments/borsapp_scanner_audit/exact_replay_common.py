from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)


def load_symbols(conn: sqlite3.Connection, exchange: str, period: str) -> list[str]:
    return [
        str(r[0])
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol",
            (exchange, period),
        ).fetchall()
    ]


def load_symbol(
    conn: sqlite3.Connection,
    symbol: str,
    exchange: str,
    period: str,
) -> pd.DataFrame:
    query = """
    SELECT candle_time, open, high, low, close, volume
    FROM candles
    WHERE symbol=? AND exchange=? AND period=?
    ORDER BY candle_time
    """
    df = pd.read_sql_query(query, conn, params=(symbol, exchange, period))
    if df.empty:
        return df
    df["candle_time"] = pd.to_datetime(df["candle_time"], errors="coerce", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna().reset_index(drop=True)


def recursive_ema(values: Iterable[float], period: int) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    out = np.full(len(arr), np.nan, dtype=float)
    if len(arr) == 0:
        return out
    alpha = 2.0 / (period + 1.0)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1.0 - alpha) * out[i - 1]
    return out


def rma_first(values: Iterable[float], period: int, valid_from: int | None = None) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    out = np.full(len(arr), np.nan, dtype=float)
    if len(arr) == 0:
        return out
    alpha = 1.0 / period
    current = float(arr[0])
    minimum = period - 1 if valid_from is None else valid_from
    for i, value in enumerate(arr):
        if i:
            current = alpha * float(value) + (1.0 - alpha) * current
        if i >= minimum:
            out[i] = current
    return out


def true_range(df: pd.DataFrame) -> np.ndarray:
    high = df.high.to_numpy(dtype=float)
    low = df.low.to_numpy(dtype=float)
    close = df.close.to_numpy(dtype=float)
    out = np.empty(len(df), dtype=float)
    if len(df) == 0:
        return out
    out[0] = high[0] - low[0]
    for i in range(1, len(df)):
        out[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return out


def wilder_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    return rma_first(true_range(df), period, valid_from=period - 1)


def production_macd(close: pd.Series) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = close.to_numpy(dtype=float)
    fast = recursive_ema(values, 12)
    slow = recursive_ema(values, 26)
    line = fast - slow
    signal = recursive_ema(line, 9)
    return line, signal, line - signal


def production_rsi(close: pd.Series, period: int = 14) -> np.ndarray:
    values = close.to_numpy(dtype=float)
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) <= period:
        return out
    changes = np.diff(values)
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    average_gain = float(gains[:period].mean())
    average_loss = float(losses[:period].mean())

    def current_value() -> float:
        if average_loss == 0:
            return 100.0 if average_gain > 0 else 50.0
        return 100.0 - 100.0 / (1.0 + average_gain / average_loss)

    out[period] = current_value()
    for change_index in range(period, len(changes)):
        average_gain = (average_gain * (period - 1) + float(gains[change_index])) / period
        average_loss = (average_loss * (period - 1) + float(losses[change_index])) / period
        out[change_index + 1] = current_value()
    return out


def legacy_rsi(close: pd.Series, period: int) -> np.ndarray:
    values = close.to_numpy(dtype=float)
    out = np.full(len(values), np.nan, dtype=float)
    if len(values) < 2:
        return out
    changes = np.diff(values)
    average_gain = max(float(changes[0]), 0.0)
    average_loss = max(-float(changes[0]), 0.0)
    alpha = 1.0 / period
    for j, change in enumerate(changes):
        if j:
            average_gain = alpha * max(float(change), 0.0) + (1.0 - alpha) * average_gain
            average_loss = alpha * max(-float(change), 0.0) + (1.0 - alpha) * average_loss
        idx = j + 1
        if average_loss == 0:
            out[idx] = 100.0 if average_gain > 0 else np.nan
        else:
            out[idx] = 100.0 - 100.0 / (1.0 + average_gain / average_loss)
    return out


def production_smi(
    df: pd.DataFrame,
    length_k: int = 10,
    length_d: int = 3,
    signal_period: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    n = len(df)
    smi_full = np.full(n, np.nan, dtype=float)
    signal_full = np.full(n, np.nan, dtype=float)
    if n < length_k:
        return smi_full, signal_full
    highs = df.high.to_numpy(dtype=float)
    lows = df.low.to_numpy(dtype=float)
    closes = df.close.to_numpy(dtype=float)
    relative: list[float] = []
    widths: list[float] = []
    for i in range(length_k - 1, n):
        highest = float(np.max(highs[i - length_k + 1 : i + 1]))
        lowest = float(np.min(lows[i - length_k + 1 : i + 1]))
        relative.append(closes[i] - (highest + lowest) / 2.0)
        widths.append(highest - lowest)
    numerator = recursive_ema(recursive_ema(relative, length_d), length_d)
    denominator = recursive_ema(recursive_ema(widths, length_d), length_d)
    smi = np.asarray(
        [200.0 * num / (den if den != 0 else 0.000001) for num, den in zip(numerator, denominator, strict=True)],
        dtype=float,
    )
    signal = recursive_ema(smi, signal_period)
    start = length_k - 1
    smi_full[start:] = smi
    signal_full[start:] = signal
    return smi_full, signal_full


def rolling_sma(series: pd.Series, period: int) -> np.ndarray:
    return series.rolling(period, min_periods=period).mean().to_numpy(dtype=float)


def inclusive_volume_ratio(volume: pd.Series, period: int) -> tuple[np.ndarray, np.ndarray]:
    mean = rolling_sma(volume, period)
    observed = volume.to_numpy(dtype=float)
    ratio = np.divide(observed, mean, out=np.full(len(observed), np.nan), where=np.isfinite(mean) & (mean > 0))
    return mean, ratio


def previous_rvol(volume: pd.Series, window: int = 20, min_history: int = 5) -> np.ndarray:
    baseline = volume.shift(1).rolling(window, min_periods=min_history).mean().to_numpy(dtype=float)
    observed = volume.to_numpy(dtype=float)
    return np.divide(observed, baseline, out=np.full(len(observed), np.nan), where=np.isfinite(baseline) & (baseline > 0))


def average_turnover(df: pd.DataFrame, window: int = 20) -> np.ndarray:
    turnover = df.close * df.volume
    # Production uses all available bars up to window. Technical market context itself needs 60 bars,
    # so later production comparisons always have a full 20-bar turnover window.
    return turnover.rolling(window, min_periods=1).mean().to_numpy(dtype=float)


def adx_series(df: pd.DataFrame, period: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(df)
    if n == 0:
        return np.array([]), np.array([]), np.array([])
    high = df.high.to_numpy(dtype=float)
    low = df.low.to_numpy(dtype=float)
    plus_dm = np.zeros(n, dtype=float)
    minus_dm = np.zeros(n, dtype=float)
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
    atr = wilder_atr(df, period)
    plus_rma = rma_first(plus_dm, period, valid_from=period - 1)
    minus_rma = rma_first(minus_dm, period, valid_from=period - 1)
    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)
    dx = np.zeros(n, dtype=float)
    valid = np.isfinite(atr) & (atr > 0) & np.isfinite(plus_rma) & np.isfinite(minus_rma)
    plus_di[valid] = 100.0 * plus_rma[valid] / atr[valid]
    minus_di[valid] = 100.0 * minus_rma[valid] / atr[valid]
    denom = plus_di + minus_di
    dx_valid = valid & np.isfinite(denom) & (denom != 0)
    dx[dx_valid] = 100.0 * np.abs(plus_di[dx_valid] - minus_di[dx_valid]) / denom[dx_valid]
    adx = rma_first(dx, period, valid_from=period - 1)
    return adx, plus_di, minus_di


def bb_rank_series(close: pd.Series, period: int = 20, rank_window: int = 100) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    values = close.to_numpy(dtype=float)
    n = len(values)
    widths = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    middle = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = values[i - period + 1 : i + 1]
        mean = float(window.mean())
        deviation = float(np.sqrt(np.mean((window - mean) ** 2)))
        widths[i] = 400.0 * deviation / mean if mean else np.nan
        middle[i] = mean
        lower[i] = mean - 2.0 * deviation
        upper[i] = mean + 2.0 * deviation
    ranks = np.full(n, np.nan)
    minimum = max(10, rank_window // 3)
    for i in range(n):
        current = widths[i]
        if not np.isfinite(current):
            continue
        start = max(0, i - rank_window + 1)
        window = widths[start : i + 1]
        window = window[np.isfinite(window)]
        if len(window) >= minimum:
            ranks[i] = float(np.sum(window <= current) / len(window) * 100.0)
    streak = np.zeros(n, dtype=int)
    current_streak = 0
    for i, value in enumerate(ranks):
        if np.isfinite(value) and value <= 25.0:
            current_streak += 1
        else:
            current_streak = 0
        streak[i] = current_streak
    return ranks, streak, lower, middle, upper


def add_forward_metrics(
    rows: list[dict],
    df: pd.DataFrame,
    event_indices: np.ndarray,
    direction: np.ndarray,
    atr: np.ndarray,
    fresh_mask: np.ndarray,
    symbol: str,
) -> None:
    max_h = max(HORIZONS)
    for i in event_indices:
        i = int(i)
        if i + max_h >= len(df):
            continue
        if i >= len(atr) or not np.isfinite(atr[i]) or atr[i] <= 0:
            continue
        entry = float(df.close.iloc[i])
        d = int(direction[i])
        row: dict[str, object] = {
            "symbol": symbol,
            "time": df.candle_time.iloc[i],
            "direction": d,
            "fresh": bool(fresh_mask[i]),
        }
        for h in HORIZONS:
            future = df.iloc[i + 1 : i + h + 1]
            terminal = float(df.close.iloc[i + h])
            row[f"ret_{h}"] = terminal / entry - 1.0
            if d >= 0:
                row[f"mfe_{h}"] = float(future.high.max() / entry - 1.0)
                row[f"mae_{h}"] = float(future.low.min() / entry - 1.0)
            else:
                row[f"mfe_{h}"] = float(entry / future.low.min() - 1.0)
                row[f"mae_{h}"] = float(entry / future.high.max() - 1.0)
            row[f"range_atr_{h}"] = float((future.high.max() - future.low.min()) / atr[i])
        rows.append(row)


def summarize(events: pd.DataFrame, split: str) -> dict:
    x = events if split == "all" else events[events["split"] == split]
    out: dict[str, object] = {
        "split": split,
        "events": int(len(x)),
        "symbols": int(x.symbol.nunique()) if len(x) else 0,
    }
    if x.empty:
        return out
    out["fresh_rate"] = float(x.fresh.mean())
    for h in HORIZONS:
        signed = x[f"ret_{h}"] * x.direction.replace(0, 1)
        out[f"hit_{h}"] = float((signed > 0).mean())
        out[f"median_signed_{h}"] = float(signed.median())
        out[f"median_abs_{h}"] = float(x[f"ret_{h}"].abs().median())
        out[f"median_mfe_{h}"] = float(x[f"mfe_{h}"].median())
        out[f"median_mae_{h}"] = float(x[f"mae_{h}"].median())
        out[f"median_range_atr_{h}"] = float(x[f"range_atr_{h}"].median())
    return out


def finalize_events(
    rows: list[dict],
    out_dir: Path,
    manifest: dict,
    holdout: float,
) -> tuple[pd.DataFrame, list[dict]]:
    events = pd.DataFrame(rows)
    if not events.empty:
        events = events.sort_values("time").reset_index(drop=True)
        cut = int(math.floor(len(events) * (1.0 - holdout)))
        events["split"] = np.where(np.arange(len(events)) < cut, "research", "holdout")
    else:
        events = pd.DataFrame(columns=["symbol", "time", "direction", "fresh", "split"])
    out_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(out_dir / "events.csv", index=False)
    summaries = [summarize(events, split) for split in ("all", "research", "holdout")]
    pd.DataFrame(summaries).to_csv(out_dir / "summary.csv", index=False)
    manifest = dict(manifest)
    manifest["events"] = int(len(events))
    manifest["horizons"] = list(HORIZONS)
    manifest["holdout_fraction"] = holdout
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return events, summaries


def fresh_from_mask(mask: np.ndarray) -> np.ndarray:
    clean = np.asarray(mask, dtype=bool)
    previous = np.concatenate(([False], clean[:-1]))
    return clean & (~previous)
