from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from exact_replay_common import (
    add_forward_metrics,
    finalize_events,
    fresh_from_mask,
    inclusive_volume_ratio,
    legacy_rsi,
    load_symbol,
    load_symbols,
    production_macd,
    production_rsi,
    production_smi,
    recursive_ema,
    rolling_sma,
    wilder_atr,
)

SIGNAL_SCANNERS = {
    "signal.macd_positive_cross",
    "signal.rsi_momentum_volume",
    "signal.rsi_macd_volume",
    "signal.smi_macd_positive",
    "signal.smi_macd_positive_volume_confirmed",
    "signal.smi_macd_early",
    "signal.smi_macd_full",
    "signal.sma_macd_volume",
    "signal.ema_trend_volume",
}


def gt(a: np.ndarray, b: np.ndarray | float) -> np.ndarray:
    return np.isfinite(a) & np.isfinite(b) & (a > b)


def exact_mask(df: pd.DataFrame, scanner: str) -> np.ndarray:
    n = len(df)
    index = np.arange(n)
    close = df.close.to_numpy(dtype=float)
    volume = df.volume.to_numpy(dtype=float)

    macd_line, macd_signal, macd_hist = production_macd(df.close)
    macd_prev_line = np.roll(macd_line, 1)
    macd_prev_signal = np.roll(macd_signal, 1)
    macd_prev_hist = np.roll(macd_hist, 1)
    macd_prev_line[0] = np.nan
    macd_prev_signal[0] = np.nan
    macd_prev_hist[0] = np.nan
    macd_cross = (macd_prev_line <= macd_prev_signal) & (macd_line > macd_signal)
    macd_rising = (macd_line > macd_signal) & (macd_line > macd_prev_line)
    macd_trigger = macd_cross | macd_rising

    if scanner == "signal.macd_positive_cross":
        rsi14 = production_rsi(df.close, 14)
        valid = index >= 34  # MACD provider warmup = 35 bars.
        return valid & (rsi14 > 30.0) & (macd_line > 0.0) & macd_trigger

    mean10, ratio10 = inclusive_volume_ratio(df.volume, 10)
    mean20, ratio20 = inclusive_volume_ratio(df.volume, 20)

    if scanner == "signal.rsi_momentum_volume":
        rsi7 = legacy_rsi(df.close, 7)
        previous = np.roll(rsi7, 1)
        previous[0] = np.nan
        rsi_cross = (previous <= 50.0) & (rsi7 > 50.0)
        rsi_rising = (rsi7 > 50.0) & (rsi7 > previous)
        valid = index >= 29
        volume_ok = np.isfinite(mean10) & (mean10 > 0) & (volume > mean10 * 1.5)
        return valid & (rsi7 > 60.0) & (rsi_cross | rsi_rising) & volume_ok

    if scanner == "signal.rsi_macd_volume":
        rsi14 = legacy_rsi(df.close, 14)
        previous = np.roll(rsi14, 1)
        previous[0] = np.nan
        rsi_cross = (previous <= 50.0) & (rsi14 > 50.0)
        rsi_rising = (rsi14 > 50.0) & (rsi14 > previous)
        valid = index >= 34
        volume_ok = np.isfinite(mean20) & (mean20 > 0) & (volume > mean20 * 1.5)
        return valid & (rsi_cross | rsi_rising) & (rsi14 < 70.0) & macd_trigger & volume_ok

    smi, smi_signal = production_smi(df)
    smi_previous = np.roll(smi, 1)
    smi_previous_signal = np.roll(smi_signal, 1)
    smi_previous[0] = np.nan
    smi_previous_signal[0] = np.nan
    smi_cross = (smi_previous <= smi_previous_signal) & (smi > smi_signal)
    smi_rising = (smi > smi_signal) & (smi > smi_previous)
    smi_trigger = smi_cross | smi_rising
    hist_rising = macd_hist > macd_prev_hist

    sma = {period: rolling_sma(df.close, period) for period in (5, 8, 21, 50, 55, 200)}
    ema = {period: recursive_ema(close, period) for period in (5, 8, 13, 21, 55, 200)}
    valid200 = index >= 199
    volume20_ok = np.isfinite(mean20) & (mean20 > 0) & (volume > mean20 * 1.5)
    full_confirmation = valid200 & (close > sma[200]) & volume20_ok

    if scanner == "signal.smi_macd_positive":
        return valid200 & smi_trigger & (smi > 0.0) & (macd_hist > 0.0) & hist_rising

    if scanner == "signal.smi_macd_positive_volume_confirmed":
        base = valid200 & smi_trigger & (smi > 0.0) & (macd_hist > 0.0) & hist_rising
        return base & full_confirmation

    negative_base = valid200 & smi_trigger & (smi < 0.0) & (macd_hist < 0.0) & hist_rising
    if scanner == "signal.smi_macd_early":
        return negative_base & (~full_confirmation)
    if scanner == "signal.smi_macd_full":
        return negative_base & full_confirmation

    if scanner == "signal.sma_macd_volume":
        ma_ok = np.ones(n, dtype=bool)
        for period in (5, 8, 21, 50, 55, 200):
            ma_ok &= close > sma[period]
        return valid200 & ma_ok & (macd_line > 0.0) & macd_trigger & volume20_ok

    if scanner == "signal.ema_trend_volume":
        previous_ema = {period: np.roll(values, 1) for period, values in ema.items()}
        for values in previous_ema.values():
            values[0] = np.nan

        def ema_trigger(left: int, right: int) -> np.ndarray:
            true_cross = (previous_ema[left] <= previous_ema[right]) & (ema[left] > ema[right])
            rising_above = (ema[left] > ema[right]) & (ema[left] > previous_ema[left])
            return true_cross | rising_above

        long_ok = (close > ema[21]) & (close > ema[55]) & (close > ema[200])
        short_ok = ema_trigger(8, 13) & ema_trigger(5, 8) & ema_trigger(5, 13)
        ratio_ok = np.isfinite(ratio20) & (ratio20 > 1.5)
        return valid200 & long_ok & short_ok & ratio_ok

    raise ValueError(f"Unsupported exact signal scanner: {scanner}")


def audit(
    db: Path,
    scanner: str,
    period: str,
    exchange: str,
    out_dir: Path,
    holdout: float,
) -> None:
    if scanner not in SIGNAL_SCANNERS:
        raise ValueError(scanner)
    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    symbols = load_symbols(conn, exchange, period)
    rows: list[dict] = []
    eligible = 0
    raw_events = 0
    for symbol in symbols:
        df = load_symbol(conn, symbol, exchange, period)
        if df.empty:
            continue
        minimum = 200 if scanner not in {
            "signal.macd_positive_cross",
            "signal.rsi_momentum_volume",
            "signal.rsi_macd_volume",
        } else 35
        if scanner == "signal.rsi_momentum_volume":
            minimum = 30
        if len(df) < minimum:
            continue
        eligible += 1
        mask = np.asarray(exact_mask(df, scanner), dtype=bool)
        raw_events += int(mask.sum())
        indices = np.flatnonzero(mask)
        direction = np.ones(len(df), dtype=int)
        atr = wilder_atr(df, 14)
        add_forward_metrics(
            rows,
            df,
            indices,
            direction,
            atr,
            fresh_from_mask(mask),
            symbol,
        )
    conn.close()
    manifest = {
        "scanner": scanner,
        "period": period,
        "exchange": exchange,
        "symbols_in_db": len(symbols),
        "symbols_with_min_history": eligible,
        "raw_matches_before_forward_horizon": raw_events,
        "parity_note": "exact_production_formula_replay_v1",
        "production_source": "borsapp/main signal scanner + momentum/trend feature formulas",
    }
    events, summaries = finalize_events(rows, out_dir, manifest, holdout)
    print(json.dumps({**manifest, "events": len(events), "summary": summaries}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--scanner", required=True, choices=sorted(SIGNAL_SCANNERS))
    parser.add_argument("--period", required=True)
    parser.add_argument("--exchange", default="BIST")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--holdout", type=float, default=0.20)
    args = parser.parse_args()
    audit(Path(args.db), args.scanner, args.period, args.exchange, Path(args.out_dir), args.holdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
