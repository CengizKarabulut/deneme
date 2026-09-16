from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
BB_RANK_MAX_VALUES = (10.0, 20.0, 30.0)
RVOL_MIN_VALUES = (1.0, 1.5, 2.0, 3.0)
PRODUCTION_BB_RANK_MAX = 20.0
PRODUCTION_RVOL_MIN = 1.5
WARMUP = 60


def load_symbols(connection: sqlite3.Connection, exchange: str, period: str) -> list[str]:
    rows = connection.execute(
        "SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol",
        (exchange, period),
    ).fetchall()
    return [str(row[0]) for row in rows]


def load_frame(connection: sqlite3.Connection, symbol: str, exchange: str, period: str) -> pd.DataFrame:
    frame = pd.read_sql_query(
        """
        SELECT candle_time, open, high, low, close, volume
        FROM candles
        WHERE symbol=? AND exchange=? AND period=?
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
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / 14.0, adjust=False, min_periods=14).mean()


def bollinger_context(close: pd.Series, period: int = 20, rank_window: int = 100) -> tuple[pd.Series, pd.Series]:
    values = pd.to_numeric(close, errors="coerce").astype(float)
    middle = values.rolling(period, min_periods=period).mean()
    deviation = values.rolling(period, min_periods=period).std(ddof=0)
    width = 400.0 * deviation / middle.replace(0.0, np.nan)

    widths = width.to_numpy(dtype=float)
    ranks = np.full(len(widths), np.nan, dtype=float)
    minimum = max(10, rank_window // 3)
    for index, current in enumerate(widths):
        if not np.isfinite(current):
            continue
        start = max(0, index - rank_window + 1)
        window = widths[start : index + 1]
        window = window[np.isfinite(window)]
        if len(window) >= minimum:
            ranks[index] = float(np.sum(window <= current) / len(window) * 100.0)
    return width, pd.Series(ranks, index=close.index)


def forward_max(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).max().iloc[::-1]


def forward_min(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).min().iloc[::-1]


def forward_any(condition: pd.Series, horizon: int) -> pd.Series:
    numeric = condition.astype(float)
    return numeric.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).max().iloc[::-1] > 0.0


def enrich(frame: pd.DataFrame, window: int = 20, min_history: int = 5) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype(float)
    volume = result["volume"].astype(float)
    turnover = close * volume

    result["baseline_volume"] = volume.shift(1).rolling(window, min_periods=min_history).mean()
    result["rvol"] = volume / result["baseline_volume"].replace(0.0, np.nan)
    result["average_turnover"] = turnover.rolling(window, min_periods=1).mean()
    result["atr14"] = atr14(result)
    result["bb_width"], result["bb_rank"] = bollinger_context(close, 20, 100)
    result["prior20_high"] = result["high"].shift(1).rolling(20, min_periods=5).max()
    result["prior20_low"] = result["low"].shift(1).rolling(20, min_periods=5).min()

    for horizon in HORIZONS:
        future_close = close.shift(-horizon)
        future_high = forward_max(result["high"].astype(float), horizon)
        future_low = forward_min(result["low"].astype(float), horizon)
        future_max_width = forward_max(result["bb_width"], horizon)
        result[f"h{horizon}_return_pct"] = (future_close / close - 1.0) * 100.0
        result[f"h{horizon}_abs_return_pct"] = result[f"h{horizon}_return_pct"].abs()
        result[f"h{horizon}_mfe_pct"] = (future_high / close - 1.0) * 100.0
        result[f"h{horizon}_mae_pct"] = (future_low / close - 1.0) * 100.0
        result[f"h{horizon}_range_atr"] = (future_high - future_low) / result["atr14"].replace(0.0, np.nan)
        result[f"h{horizon}_width_expansion_ratio"] = future_max_width / result["bb_width"].replace(0.0, np.nan)
        result[f"h{horizon}_release_gt20"] = forward_any(result["bb_rank"] > 20.0, horizon)
        result[f"h{horizon}_release_gt50"] = forward_any(result["bb_rank"] > 50.0, horizon)
        result[f"h{horizon}_up_break"] = future_high > result["prior20_high"]
        result[f"h{horizon}_down_break"] = future_low < result["prior20_low"]
    return result


def split_samples(events: pd.DataFrame, holdout_fraction: float) -> pd.DataFrame:
    if events.empty:
        events["sample"] = pd.Series(dtype=str)
        return events
    ordered = events.sort_values(["signal_time", "symbol"]).copy()
    count = len(ordered)
    holdout_count = max(1, int(math.ceil(count * holdout_fraction))) if count >= 5 else 0
    ordered["sample"] = "research"
    if holdout_count:
        ordered.iloc[-holdout_count:, ordered.columns.get_loc("sample")] = "holdout"
    return ordered


def summarize(events: pd.DataFrame, bb_rank_max: float, rvol_min: float) -> list[dict]:
    rows: list[dict] = []
    if events.empty:
        return rows
    for sample, group in events.groupby("sample", sort=True):
        base = {
            "bb_rank_max": bb_rank_max,
            "rvol_min": rvol_min,
            "sample": str(sample),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "fresh_state_rate_pct": float(group["fresh_state"].mean() * 100.0),
            "median_bb_rank": float(group["bb_rank"].median()),
            "median_rvol": float(group["rvol"].median()),
        }
        for horizon in HORIZONS:
            row = dict(base)
            row["horizon"] = horizon
            valid = group[group[f"h{horizon}_abs_return_pct"].notna()]
            row["n"] = int(len(valid))
            if not valid.empty:
                for metric in ("return_pct", "abs_return_pct", "mfe_pct", "mae_pct", "range_atr", "width_expansion_ratio"):
                    row[f"median_{metric}"] = float(valid[f"h{horizon}_{metric}"].median())
                row["release_gt20_rate_pct"] = float(valid[f"h{horizon}_release_gt20"].mean() * 100.0)
                row["release_gt50_rate_pct"] = float(valid[f"h{horizon}_release_gt50"].mean() * 100.0)
                row["up_break_rate_pct"] = float(valid[f"h{horizon}_up_break"].mean() * 100.0)
                row["down_break_rate_pct"] = float(valid[f"h{horizon}_down_break"].mean() * 100.0)
            rows.append(row)
    return rows


def run(args: argparse.Namespace) -> None:
    db_path = Path(args.db).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        symbols = load_symbols(connection, args.exchange, args.period)
        config_parts: dict[tuple[float, float], list[pd.DataFrame]] = {
            (bb, rv): [] for bb in BB_RANK_MAX_VALUES for rv in RVOL_MIN_VALUES
        }
        baseline_parts: list[pd.DataFrame] = []
        usable_symbols = 0

        for symbol in symbols:
            raw = load_frame(connection, symbol, args.exchange, args.period)
            if len(raw) < WARMUP + max(HORIZONS):
                continue
            data = enrich(raw, args.window, args.min_history)
            data = data.copy()
            data["symbol"] = symbol
            data["signal_time"] = data.index
            eligible = (
                (np.arange(len(data)) >= WARMUP - 1)
                & (data["close"] >= args.min_price)
                & (data["average_turnover"] >= args.min_turnover)
                & data["bb_rank"].notna()
                & data["rvol"].notna()
            )
            if not bool(np.any(eligible)):
                continue
            usable_symbols += 1

            for bb_rank_max in BB_RANK_MAX_VALUES:
                for rvol_min in RVOL_MIN_VALUES:
                    hit = eligible & (data["bb_rank"] <= bb_rank_max) & (data["rvol"] >= rvol_min)
                    if not bool(hit.any()):
                        continue
                    fresh = hit & ~hit.shift(1, fill_value=False)
                    columns = [
                        "symbol", "signal_time", "close", "bb_rank", "bb_width", "rvol",
                        "average_turnover", "atr14",
                    ]
                    for horizon in HORIZONS:
                        columns.extend(
                            [
                                f"h{horizon}_return_pct", f"h{horizon}_abs_return_pct",
                                f"h{horizon}_mfe_pct", f"h{horizon}_mae_pct",
                                f"h{horizon}_range_atr", f"h{horizon}_width_expansion_ratio",
                                f"h{horizon}_release_gt20", f"h{horizon}_release_gt50",
                                f"h{horizon}_up_break", f"h{horizon}_down_break",
                            ]
                        )
                    part = data.loc[hit, columns].copy()
                    part["fresh_state"] = fresh.loc[hit].astype(bool).to_numpy()
                    config_parts[(bb_rank_max, rvol_min)].append(part)
                    if bb_rank_max == PRODUCTION_BB_RANK_MAX and rvol_min == PRODUCTION_RVOL_MIN:
                        baseline_parts.append(part)

        summary_rows: list[dict] = []
        for (bb_rank_max, rvol_min), parts in config_parts.items():
            if not parts:
                continue
            events = pd.concat(parts, ignore_index=True)
            events = split_samples(events, args.holdout_fraction)
            summary_rows.extend(summarize(events, bb_rank_max, rvol_min))

        summary = pd.DataFrame(summary_rows)
        summary.to_csv(out_dir / f"squeeze_volume_summary_{args.period}.csv", index=False)

        if baseline_parts:
            baseline = pd.concat(baseline_parts, ignore_index=True)
            baseline = split_samples(baseline, args.holdout_fraction)
            baseline.to_csv(out_dir / f"squeeze_volume_events_{args.period}.csv", index=False)
        else:
            baseline = pd.DataFrame()
            baseline.to_csv(out_dir / f"squeeze_volume_events_{args.period}.csv", index=False)

        manifest = {
            "scanner": "technical.squeeze_volume",
            "period": args.period,
            "symbols_in_db": len(symbols),
            "symbols_usable": usable_symbols,
            "production_rule": {
                "bb_rank_max": PRODUCTION_BB_RANK_MAX,
                "rvol_min": PRODUCTION_RVOL_MIN,
                "min_price": args.min_price,
                "min_turnover": args.min_turnover,
                "turnover": "current-inclusive 20-bar average matching production",
                "bb_rank": "BB20 width percentile in trailing up-to-100 widths including current width; minimum 33 widths; production technical-context warmup 60 bars",
            },
            "parameter_grid": {
                "bb_rank_max": list(BB_RANK_MAX_VALUES),
                "rvol_min": list(RVOL_MIN_VALUES),
            },
            "holdout_fraction": args.holdout_fraction,
            "baseline_events": int(len(baseline)),
        }
        (out_dir / f"squeeze_volume_manifest_{args.period}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research-only technical.squeeze_volume audit")
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
