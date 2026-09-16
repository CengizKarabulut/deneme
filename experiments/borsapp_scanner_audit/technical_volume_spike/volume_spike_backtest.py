from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
DEFAULT_THRESHOLDS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)


def parse_thresholds(value: str) -> tuple[float, ...]:
    items = sorted({float(part.strip()) for part in value.split(",") if part.strip()})
    if not items or any(item <= 0 for item in items):
        raise argparse.ArgumentTypeError("thresholds must contain positive numbers")
    return tuple(items)


def load_symbols(connection: sqlite3.Connection, exchange: str, period: str) -> list[str]:
    rows = connection.execute(
        """
        SELECT DISTINCT symbol
        FROM candles
        WHERE exchange = ? AND period = ?
        ORDER BY symbol
        """,
        (exchange, period),
    ).fetchall()
    return [str(row[0]) for row in rows]


def load_frame(
    connection: sqlite3.Connection,
    symbol: str,
    exchange: str,
    period: str,
) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT candle_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND exchange = ? AND period = ?
        ORDER BY candle_time ASC
        """,
        connection,
        params=(symbol, exchange, period),
    )
    if frame.empty:
        return frame
    frame["candle_time"] = pd.to_datetime(frame["candle_time"], errors="coerce")
    frame = frame.dropna(subset=["candle_time"]).set_index("candle_time")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["open", "high", "low", "close", "volume"])


def atr14(frame: pd.DataFrame) -> pd.Series:
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    close = frame["close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()


def split_samples(events: pd.DataFrame, holdout_fraction: float) -> pd.DataFrame:
    if events.empty:
        return events
    pieces = []
    for threshold, group in events.groupby("threshold", sort=True):
        group = group.sort_values(["signal_time", "symbol"]).copy()
        count = len(group)
        holdout_count = max(1, int(math.ceil(count * holdout_fraction))) if count >= 5 else 0
        group["sample"] = "research"
        if holdout_count:
            group.iloc[-holdout_count:, group.columns.get_loc("sample")] = "holdout"
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    for (threshold, sample), group in events.groupby(["threshold", "sample"], sort=True):
        row = {
            "threshold": float(threshold),
            "sample": str(sample),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "fresh_event_rate_pct": float(group["fresh_event"].mean() * 100.0),
            "median_rvol": float(group["rvol"].median()),
            "median_average_turnover": float(group["average_turnover"].median()),
        }
        for horizon in HORIZONS:
            prefix = f"h{horizon}"
            valid = group[group[f"{prefix}_abs_return_pct"].notna()]
            row[f"{prefix}_n"] = int(len(valid))
            if valid.empty:
                continue
            row[f"{prefix}_median_abs_return_pct"] = float(valid[f"{prefix}_abs_return_pct"].median())
            row[f"{prefix}_mean_abs_return_pct"] = float(valid[f"{prefix}_abs_return_pct"].mean())
            row[f"{prefix}_median_return_pct"] = float(valid[f"{prefix}_return_pct"].median())
            row[f"{prefix}_median_mfe_pct"] = float(valid[f"{prefix}_mfe_pct"].median())
            row[f"{prefix}_median_mae_pct"] = float(valid[f"{prefix}_mae_pct"].median())
            row[f"{prefix}_median_range_atr"] = float(valid[f"{prefix}_range_atr"].median())
            row[f"{prefix}_up_break_rate_pct"] = float(valid[f"{prefix}_up_break"].mean() * 100.0)
            row[f"{prefix}_down_break_rate_pct"] = float(valid[f"{prefix}_down_break"].mean() * 100.0)
            row[f"{prefix}_median_future_volume_ratio"] = float(
                valid[f"{prefix}_future_volume_ratio"].median()
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["threshold", "sample"]).reset_index(drop=True)


def run(args: argparse.Namespace) -> None:
    db_path = Path(args.db).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        symbols = load_symbols(connection, args.exchange, args.period)
        if not symbols:
            raise RuntimeError(
                f"No symbols found for exchange={args.exchange!r}, period={args.period!r}"
            )

        events: list[dict] = []
        for symbol in symbols:
            frame = load_frame(connection, symbol, args.exchange, args.period)
            if len(frame) < args.min_history + 2:
                continue
            frame = frame.copy()
            frame["atr14"] = atr14(frame)
            previous_hit = {threshold: False for threshold in args.thresholds}

            for i in range(len(frame)):
                history = frame.iloc[max(0, i - args.window):i]
                if len(history) < args.min_history:
                    for threshold in args.thresholds:
                        previous_hit[threshold] = False
                    continue

                current = frame.iloc[i]
                baseline_volume = float(history["volume"].mean())
                if not np.isfinite(baseline_volume) or baseline_volume <= 0:
                    for threshold in args.thresholds:
                        previous_hit[threshold] = False
                    continue

                observed_volume = float(current["volume"])
                rvol = observed_volume / baseline_volume
                turnover_window = frame.iloc[max(0, i - args.window + 1): i + 1]
                average_turnover = float(
                    (turnover_window["close"] * turnover_window["volume"]).mean()
                )
                close = float(current["close"])

                pre_high = float(history["high"].max())
                pre_low = float(history["low"].min())
                signal_atr = float(current["atr14"]) if pd.notna(current["atr14"]) else np.nan

                for threshold in args.thresholds:
                    hit = bool(
                        close >= args.min_price
                        and average_turnover >= args.min_turnover
                        and rvol >= threshold
                    )
                    fresh_event = hit and not previous_hit[threshold]
                    previous_hit[threshold] = hit
                    if not hit:
                        continue

                    event = {
                        "symbol": symbol,
                        "signal_time": frame.index[i],
                        "period": args.period,
                        "threshold": threshold,
                        "fresh_event": fresh_event,
                        "close": close,
                        "observed_volume": observed_volume,
                        "baseline_volume": baseline_volume,
                        "baseline_bar_count": int(len(history)),
                        "rvol": rvol,
                        "average_turnover": average_turnover,
                        "signal_atr14": signal_atr,
                    }

                    for horizon in HORIZONS:
                        prefix = f"h{horizon}"
                        end = i + horizon
                        if end >= len(frame):
                            event[f"{prefix}_return_pct"] = np.nan
                            event[f"{prefix}_abs_return_pct"] = np.nan
                            event[f"{prefix}_mfe_pct"] = np.nan
                            event[f"{prefix}_mae_pct"] = np.nan
                            event[f"{prefix}_range_atr"] = np.nan
                            event[f"{prefix}_up_break"] = np.nan
                            event[f"{prefix}_down_break"] = np.nan
                            event[f"{prefix}_future_volume_ratio"] = np.nan
                            continue

                        future = frame.iloc[i + 1: end + 1]
                        end_close = float(future["close"].iloc[-1])
                        future_high = float(future["high"].max())
                        future_low = float(future["low"].min())
                        return_pct = (end_close / close - 1.0) * 100.0
                        mfe_pct = (future_high / close - 1.0) * 100.0
                        mae_pct = (future_low / close - 1.0) * 100.0
                        event[f"{prefix}_return_pct"] = return_pct
                        event[f"{prefix}_abs_return_pct"] = abs(return_pct)
                        event[f"{prefix}_mfe_pct"] = mfe_pct
                        event[f"{prefix}_mae_pct"] = mae_pct
                        event[f"{prefix}_range_atr"] = (
                            (future_high - future_low) / signal_atr
                            if np.isfinite(signal_atr) and signal_atr > 0
                            else np.nan
                        )
                        event[f"{prefix}_up_break"] = bool(future_high > pre_high)
                        event[f"{prefix}_down_break"] = bool(future_low < pre_low)
                        event[f"{prefix}_future_volume_ratio"] = float(
                            future["volume"].mean() / baseline_volume
                        )
                    events.append(event)

        events_frame = pd.DataFrame(events)
        if not events_frame.empty:
            events_frame = split_samples(events_frame, args.holdout_fraction)
            events_frame = events_frame.sort_values(
                ["threshold", "signal_time", "symbol"]
            ).reset_index(drop=True)

        summary = summarize(events_frame)

        events_path = out_dir / f"volume_spike_events_{args.period}.csv"
        summary_path = out_dir / f"volume_spike_summary_{args.period}.csv"
        manifest_path = out_dir / f"volume_spike_manifest_{args.period}.json"

        events_frame.to_csv(events_path, index=False)
        summary.to_csv(summary_path, index=False)
        manifest = {
            "scanner": "technical.volume_spike",
            "database": str(db_path),
            "exchange": args.exchange,
            "period": args.period,
            "window": args.window,
            "min_history": args.min_history,
            "min_price": args.min_price,
            "min_turnover": args.min_turnover,
            "thresholds": list(args.thresholds),
            "holdout_fraction": args.holdout_fraction,
            "symbols": len(symbols),
            "events": int(len(events_frame)),
            "note": "Production baseline is threshold=3.0. RVOL uses previous complete bars only; average turnover includes the current event bar, matching borsapp.",
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        print(summary.to_string(index=False))
        print(f"\nEvents: {events_path}")
        print(f"Summary: {summary_path}")
        print(f"Manifest: {manifest_path}")
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research-only technical.volume_spike audit")
    parser.add_argument("--db", required=True, help="Path to historical SQLite database")
    parser.add_argument("--exchange", default="BIST")
    parser.add_argument("--period", default="1D")
    parser.add_argument("--out", default="experiments/borsapp_scanner_audit/results/volume_spike")
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--min-history", type=int, default=5)
    parser.add_argument("--min-price", type=float, default=1.0)
    parser.add_argument("--min-turnover", type=float, default=20_000_000.0)
    parser.add_argument("--thresholds", type=parse_thresholds, default=DEFAULT_THRESHOLDS)
    parser.add_argument("--holdout-fraction", type=float, default=0.20)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    if not 0.0 <= args.holdout_fraction < 1.0:
        raise SystemExit("--holdout-fraction must be in [0, 1)")
    if args.window < 1 or args.min_history < 1 or args.min_history > args.window:
        raise SystemExit("invalid window/min-history")
    run(args)
