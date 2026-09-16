from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
THRESHOLDS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
INTRADAY = {"15m", "30m", "45m", "1H", "2H", "4H"}


def load_symbols(con: sqlite3.Connection, exchange: str, period: str) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol",
        (exchange, period),
    ).fetchall()
    return [str(row[0]) for row in rows]


def load_frame(con: sqlite3.Connection, symbol: str, exchange: str, period: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT candle_time, open, high, low, close, volume
        FROM candles
        WHERE symbol=? AND exchange=? AND period=?
        ORDER BY candle_time
        """,
        con,
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
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()


def forward_max(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).max().iloc[::-1]


def forward_min(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).min().iloc[::-1]


def enrich(frame: pd.DataFrame, period: str, window: int, min_history: int) -> pd.DataFrame:
    result = frame.copy()
    volume = result["volume"].astype(float)
    turnover = result["close"].astype(float) * volume

    result["baseline_volume"] = volume.shift(1).rolling(window, min_periods=min_history).mean()
    result["rvol"] = volume / result["baseline_volume"].replace(0.0, np.nan)
    result["turnover_current_inclusive"] = turnover.rolling(window, min_periods=1).mean()
    result["turnover_previous_only"] = turnover.shift(1).rolling(window, min_periods=min_history).mean()
    result["atr14"] = atr14(result)
    result["quarter"] = result.index.to_period("Q").astype(str)

    if period in INTRADAY:
        result["slot"] = result.index.strftime("%H:%M")
        result["slot_baseline_volume"] = (
            result.groupby("slot", sort=False)["volume"]
            .transform(lambda values: values.shift(1).rolling(window, min_periods=min_history).mean())
        )
        result["slot_rvol"] = volume / result["slot_baseline_volume"].replace(0.0, np.nan)
    else:
        result["slot"] = "ALL"
        result["slot_rvol"] = result["rvol"]

    log_turnover = np.log10(result["turnover_previous_only"].where(result["turnover_previous_only"] > 0))
    result["turnover_bucket"] = np.floor(log_turnover * 4.0) / 4.0

    close = result["close"].astype(float)
    for horizon in HORIZONS:
        end_close = close.shift(-horizon)
        future_high = forward_max(result["high"].astype(float), horizon)
        future_low = forward_min(result["low"].astype(float), horizon)
        result[f"h{horizon}_return_pct"] = (end_close / close - 1.0) * 100.0
        result[f"h{horizon}_abs_return_pct"] = result[f"h{horizon}_return_pct"].abs()
        result[f"h{horizon}_mfe_pct"] = (future_high / close - 1.0) * 100.0
        result[f"h{horizon}_mae_pct"] = (future_low / close - 1.0) * 100.0
        result[f"h{horizon}_range_atr"] = (future_high - future_low) / result["atr14"].replace(0.0, np.nan)
    return result


def summarize_group(group: pd.DataFrame, threshold: float, label: str, horizon: int) -> dict:
    row = {
        "threshold": threshold,
        "group": label,
        "horizon": horizon,
        "events": int(len(group)),
        "symbols": int(group["symbol"].nunique()) if not group.empty else 0,
    }
    for metric in ("return_pct", "abs_return_pct", "mfe_pct", "mae_pct", "range_atr"):
        series = pd.to_numeric(group[f"h{horizon}_{metric}"], errors="coerce").dropna()
        row[f"median_{metric}"] = float(series.median()) if not series.empty else np.nan
    return row


def rescued_quality(all_rows: pd.DataFrame, min_price: float, min_turnover: float) -> pd.DataFrame:
    rows: list[dict] = []
    for threshold in THRESHOLDS:
        base = (all_rows["close"] >= min_price) & (all_rows["rvol"] >= threshold)
        current_ok = base & (all_rows["turnover_current_inclusive"] >= min_turnover)
        previous_ok = base & (all_rows["turnover_previous_only"] >= min_turnover)
        rescued = all_rows[current_ok & ~previous_ok]
        retained = all_rows[current_ok & previous_ok]
        previous_only = all_rows[previous_ok]
        for horizon in HORIZONS:
            rescued_row = summarize_group(rescued, threshold, "rescued_by_current_bar", horizon)
            retained_row = summarize_group(retained, threshold, "production_retained", horizon)
            previous_row = summarize_group(previous_only, threshold, "previous_only_all", horizon)
            rows.extend([rescued_row, retained_row, previous_row])
    return pd.DataFrame(rows)


def sample_cutoff(events: pd.DataFrame, holdout_fraction: float) -> pd.Timestamp | None:
    if events.empty:
        return None
    ordered = events.sort_values(["candle_time", "symbol"])
    count = len(ordered)
    holdout_count = max(1, int(math.ceil(count * holdout_fraction))) if count >= 5 else 0
    if not holdout_count:
        return None
    return pd.Timestamp(ordered.iloc[-holdout_count]["candle_time"])


def matched_sample(
    all_rows: pd.DataFrame,
    signal_column: str,
    threshold: float,
    min_price: float,
    min_turnover: float,
    holdout_fraction: float,
) -> list[dict]:
    eligible = all_rows[
        (all_rows["close"] >= min_price)
        & (all_rows["turnover_previous_only"] >= min_turnover)
        & all_rows[signal_column].notna()
    ].copy()
    events = eligible[eligible[signal_column] >= threshold].copy()
    cutoff = sample_cutoff(events, holdout_fraction)
    if cutoff is None:
        return []

    eligible["sample"] = np.where(eligible["candle_time"] >= cutoff, "holdout", "research")
    events = eligible[eligible[signal_column] >= threshold].copy()
    controls = eligible[eligible[signal_column] < 1.5].copy()
    keys = ["symbol", "quarter", "slot", "turnover_bucket"]
    metrics = []
    for horizon in HORIZONS:
        metrics.extend(
            [
                f"h{horizon}_abs_return_pct",
                f"h{horizon}_range_atr",
                f"h{horizon}_mfe_pct",
                f"h{horizon}_mae_pct",
            ]
        )

    output: list[dict] = []
    for sample in ("research", "holdout"):
        sample_events = events[events["sample"] == sample].copy()
        sample_controls = controls[controls["sample"] == sample].copy()
        control_medians = sample_controls.groupby(keys, dropna=False)[metrics].median().reset_index()
        matched = sample_events.merge(control_medians, on=keys, how="inner", suffixes=("_event", "_control"))
        for horizon in HORIZONS:
            row = {
                "signal_model": signal_column,
                "threshold": threshold,
                "sample": sample,
                "horizon": horizon,
                "events": int(len(sample_events)),
                "matched_events": int(len(matched)),
                "match_rate_pct": float(len(matched) / len(sample_events) * 100.0) if len(sample_events) else np.nan,
                "cutoff": cutoff.isoformat(),
            }
            for metric in ("abs_return_pct", "range_atr", "mfe_pct", "mae_pct"):
                event_values = pd.to_numeric(matched[f"h{horizon}_{metric}_event"], errors="coerce")
                control_values = pd.to_numeric(matched[f"h{horizon}_{metric}_control"], errors="coerce")
                valid = event_values.notna() & control_values.notna()
                row[f"event_median_{metric}"] = float(event_values[valid].median()) if valid.any() else np.nan
                row[f"control_median_{metric}"] = float(control_values[valid].median()) if valid.any() else np.nan
                row[f"median_edge_{metric}"] = (
                    float((event_values[valid] - control_values[valid]).median()) if valid.any() else np.nan
                )
            output.append(row)
    return output


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{Path(args.db).resolve().as_posix()}?mode=ro", uri=True)
    try:
        frames: list[pd.DataFrame] = []
        symbols = load_symbols(con, args.exchange, args.period)
        for symbol in symbols:
            raw = load_frame(con, symbol, args.exchange, args.period)
            if len(raw) < args.min_history + max(HORIZONS) + 2:
                continue
            enriched = enrich(raw, args.period, args.window, args.min_history)
            enriched["symbol"] = symbol
            frames.append(enriched.reset_index(names="candle_time"))
        if not frames:
            raise RuntimeError("No usable data")
        all_rows = pd.concat(frames, ignore_index=True)

        rescued = rescued_quality(all_rows, args.min_price, args.min_turnover)
        rescued.to_csv(out / f"turnover_rescued_quality_{args.period}.csv", index=False)

        model_rows: list[dict] = []
        for threshold in THRESHOLDS:
            model_rows.extend(
                matched_sample(
                    all_rows,
                    "rvol",
                    threshold,
                    args.min_price,
                    args.min_turnover,
                    args.holdout_fraction,
                )
            )
            model_rows.extend(
                matched_sample(
                    all_rows,
                    "slot_rvol",
                    threshold,
                    args.min_price,
                    args.min_turnover,
                    args.holdout_fraction,
                )
            )
        pd.DataFrame(model_rows).to_csv(out / f"standard_vs_slot_holdout_{args.period}.csv", index=False)

        manifest = {
            "scanner": "technical.volume_spike",
            "stage": "final_checks",
            "period": args.period,
            "symbols_in_db": len(symbols),
            "symbols_usable": int(all_rows["symbol"].nunique()),
            "rows": int(len(all_rows)),
            "thresholds": list(THRESHOLDS),
            "holdout_fraction": args.holdout_fraction,
            "rescued_definition": "production current-inclusive turnover passes but previous-only turnover fails",
            "model_comparison": "standard RVOL versus same-clock-slot RVOL; both require previous-only turnover and are evaluated with chronological research/holdout matched controls",
        }
        (out / f"final_checks_manifest_{args.period}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    finally:
        con.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Final validation checks for technical.volume_spike")
    parser.add_argument("--db", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--exchange", default="BIST")
    parser.add_argument("--window", type=int, default=20)
    parser.add_argument("--min-history", type=int, default=5)
    parser.add_argument("--min-price", type=float, default=1.0)
    parser.add_argument("--min-turnover", type=float, default=20_000_000.0)
    parser.add_argument("--holdout-fraction", type=float, default=0.20)
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    if not 0.0 <= args.holdout_fraction < 1.0:
        raise SystemExit("holdout fraction must be in [0,1)")
    run(args)
