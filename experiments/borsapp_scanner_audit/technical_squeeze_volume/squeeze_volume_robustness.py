from __future__ import annotations

import argparse
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
PRODUCTION_BB_RANK_MAX = 20.0
PRODUCTION_RVOL_MIN = 1.5
WARMUP = 60
INTRADAY = {"15m", "30m", "45m", "1H", "2H", "4H"}


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


def bollinger_context(close: pd.Series, period: int = 20, rank_window: int = 100) -> tuple[pd.Series, pd.Series, pd.Series]:
    values = pd.to_numeric(close, errors="coerce").astype(float)
    middle = values.rolling(period, min_periods=period).mean()
    deviation = values.rolling(period, min_periods=period).std(ddof=0)
    width = 400.0 * deviation / middle.replace(0.0, np.nan)

    widths = width.to_numpy(dtype=float)
    inclusive = np.full(len(widths), np.nan, dtype=float)
    previous_only = np.full(len(widths), np.nan, dtype=float)
    minimum = max(10, rank_window // 3)

    for index, current in enumerate(widths):
        if not np.isfinite(current):
            continue

        start_inclusive = max(0, index - rank_window + 1)
        window_inclusive = widths[start_inclusive : index + 1]
        window_inclusive = window_inclusive[np.isfinite(window_inclusive)]
        if len(window_inclusive) >= minimum:
            inclusive[index] = float(np.sum(window_inclusive <= current) / len(window_inclusive) * 100.0)

        start_previous = max(0, index - rank_window)
        window_previous = widths[start_previous:index]
        window_previous = window_previous[np.isfinite(window_previous)]
        if len(window_previous) >= minimum:
            previous_only[index] = float(np.sum(window_previous <= current) / len(window_previous) * 100.0)

    return (
        width,
        pd.Series(inclusive, index=close.index),
        pd.Series(previous_only, index=close.index),
    )


def forward_max(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).max().iloc[::-1]


def forward_min(series: pd.Series, horizon: int) -> pd.Series:
    return series.shift(-1).iloc[::-1].rolling(horizon, min_periods=horizon).min().iloc[::-1]


def enrich(frame: pd.DataFrame, period: str, window: int = 20, min_history: int = 5) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype(float)
    volume = result["volume"].astype(float)
    turnover = close * volume

    result["baseline_volume"] = volume.shift(1).rolling(window, min_periods=min_history).mean()
    result["rvol"] = volume / result["baseline_volume"].replace(0.0, np.nan)
    result["turnover_current_inclusive"] = turnover.rolling(window, min_periods=1).mean()
    result["turnover_previous_only"] = turnover.shift(1).rolling(window, min_periods=min_history).mean()
    result["atr14"] = atr14(result)
    (
        result["bb_width"],
        result["bb_rank_inclusive"],
        result["bb_rank_previous_only"],
    ) = bollinger_context(close, 20, 100)

    result["quarter"] = result.index.to_period("Q").astype(str)
    if period in INTRADAY:
        result["slot"] = result.index.strftime("%H:%M")
        result["slot_baseline_volume"] = (
            result.groupby("slot", sort=False)["volume"]
            .transform(lambda s: s.shift(1).rolling(window, min_periods=min_history).mean())
        )
        result["slot_rvol"] = volume / result["slot_baseline_volume"].replace(0.0, np.nan)
    else:
        result["slot"] = "ALL"
        result["slot_rvol"] = result["rvol"]

    log_turn = np.log10(result["turnover_previous_only"].where(result["turnover_previous_only"] > 0))
    result["turnover_bucket"] = np.floor(log_turn * 4.0) / 4.0
    result["bb_rank_bucket"] = np.floor(result["bb_rank_inclusive"] / 5.0) * 5.0

    result["prior20_high"] = result["high"].shift(1).rolling(20, min_periods=5).max()
    result["prior20_low"] = result["low"].shift(1).rolling(20, min_periods=5).min()

    for horizon in HORIZONS:
        future_close = close.shift(-horizon)
        future_high = forward_max(result["high"].astype(float), horizon)
        future_low = forward_min(result["low"].astype(float), horizon)
        future_max_width = forward_max(result["bb_width"], horizon)
        future_max_rank = forward_max(result["bb_rank_inclusive"], horizon)

        result[f"h{horizon}_return_pct"] = (future_close / close - 1.0) * 100.0
        result[f"h{horizon}_abs_return_pct"] = result[f"h{horizon}_return_pct"].abs()
        result[f"h{horizon}_mfe_pct"] = (future_high / close - 1.0) * 100.0
        result[f"h{horizon}_mae_pct"] = (future_low / close - 1.0) * 100.0
        result[f"h{horizon}_range_atr"] = (future_high - future_low) / result["atr14"].replace(0.0, np.nan)
        result[f"h{horizon}_width_expansion_ratio"] = future_max_width / result["bb_width"].replace(0.0, np.nan)
        result[f"h{horizon}_rank_gain"] = future_max_rank - result["bb_rank_inclusive"]
        result[f"h{horizon}_width_expand_125"] = result[f"h{horizon}_width_expansion_ratio"] >= 1.25
        result[f"h{horizon}_width_expand_150"] = result[f"h{horizon}_width_expansion_ratio"] >= 1.50
        result[f"h{horizon}_rank_gain_20"] = result[f"h{horizon}_rank_gain"] >= 20.0
        result[f"h{horizon}_up_break"] = future_high > result["prior20_high"]
        result[f"h{horizon}_down_break"] = future_low < result["prior20_low"]

    return result


def state_masks(data: pd.DataFrame, min_price: float, min_turnover: float) -> dict[str, pd.Series]:
    warm = np.arange(len(data)) >= WARMUP - 1
    price = data["close"] >= min_price
    production_liquid = data["turnover_current_inclusive"] >= min_turnover
    previous_liquid = data["turnover_previous_only"] >= min_turnover

    base_valid = warm & price & data["bb_rank_inclusive"].notna() & data["rvol"].notna()
    squeeze = base_valid & (data["bb_rank_inclusive"] <= PRODUCTION_BB_RANK_MAX)
    prod = squeeze & production_liquid & (data["rvol"] >= PRODUCTION_RVOL_MIN)
    previous = squeeze & previous_liquid & (data["rvol"] >= PRODUCTION_RVOL_MIN)
    squeeze_only = squeeze & previous_liquid
    low_volume_control = squeeze & previous_liquid & (data["rvol"] < 1.0)
    slot = squeeze & previous_liquid & (data["slot_rvol"] >= PRODUCTION_RVOL_MIN)

    return {
        "production": prod,
        "previous_turnover": previous,
        "squeeze_only": squeeze_only,
        "low_volume_control": low_volume_control,
        "slot_rvol": slot,
    }


def append_group_rows(
    rows: list[dict],
    data: pd.DataFrame,
    mask: pd.Series,
    group_name: str,
    sample: str,
) -> None:
    group = data.loc[mask].copy()
    if group.empty:
        return

    base = {
        "group": group_name,
        "sample": sample,
        "events": int(len(group)),
        "symbols": int(group["symbol"].nunique()),
        "median_bb_rank": float(group["bb_rank_inclusive"].median()),
        "median_rvol": float(group["rvol"].median()),
    }

    for horizon in HORIZONS:
        valid = group[group[f"h{horizon}_abs_return_pct"].notna()]
        row = dict(base)
        row["horizon"] = horizon
        row["n"] = int(len(valid))
        if not valid.empty:
            for metric in (
                "return_pct",
                "abs_return_pct",
                "mfe_pct",
                "mae_pct",
                "range_atr",
                "width_expansion_ratio",
                "rank_gain",
            ):
                row[f"median_{metric}"] = float(valid[f"h{horizon}_{metric}"].median())
            for flag in ("width_expand_125", "width_expand_150", "rank_gain_20", "up_break", "down_break"):
                row[f"{flag}_rate_pct"] = float(valid[f"h{horizon}_{flag}"].mean() * 100.0)
        rows.append(row)


def chronological_sample_mask(
    all_times: pd.Series,
    reference_times: pd.Series,
    holdout_fraction: float,
) -> tuple[pd.Series, pd.Series]:
    valid = reference_times.dropna().sort_values()
    if valid.empty:
        empty = pd.Series(False, index=all_times.index)
        return empty, empty
    cut_index = max(0, min(len(valid) - 1, int(math.floor(len(valid) * (1.0 - holdout_fraction)))))
    cutoff = valid.iloc[cut_index]
    research = all_times < cutoff
    holdout = all_times >= cutoff
    return research, holdout


def matched_control_rows(
    all_rows: pd.DataFrame,
    event_mask: pd.Series,
    control_mask: pd.Series,
    label: str,
) -> list[dict]:
    events = all_rows.loc[event_mask].copy()
    controls = all_rows.loc[control_mask].copy()

    keys = ["symbol", "quarter", "slot", "turnover_bucket", "bb_rank_bucket"]
    metrics = []
    for horizon in HORIZONS:
        metrics += [
            f"h{horizon}_abs_return_pct",
            f"h{horizon}_range_atr",
            f"h{horizon}_width_expansion_ratio",
            f"h{horizon}_rank_gain",
        ]

    control_med = controls.groupby(keys, dropna=False)[metrics].median().reset_index()
    matched = events.merge(control_med, on=keys, how="inner", suffixes=("_event", "_control"))

    out = []
    for horizon in HORIZONS:
        row = {
            "comparison": label,
            "horizon": horizon,
            "events": int(len(events)),
            "matched_events": int(len(matched)),
            "match_rate_pct": float(len(matched) / len(events) * 100.0) if len(events) else np.nan,
        }
        for metric in ("abs_return_pct", "range_atr", "width_expansion_ratio", "rank_gain"):
            e = matched[f"h{horizon}_{metric}_event"]
            c = matched[f"h{horizon}_{metric}_control"]
            valid = e.notna() & c.notna()
            row[f"event_median_{metric}"] = float(e[valid].median()) if valid.any() else np.nan
            row[f"control_median_{metric}"] = float(c[valid].median()) if valid.any() else np.nan
            row[f"median_edge_{metric}"] = float((e[valid] - c[valid]).median()) if valid.any() else np.nan
        out.append(row)
    return out


def variant_overlap(a: pd.Series, b: pd.Series, label: str) -> dict:
    overlap = a & b
    union = a | b
    return {
        "comparison": label,
        "a_events": int(a.sum()),
        "b_events": int(b.sum()),
        "overlap_events": int(overlap.sum()),
        "jaccard_pct": float(overlap.sum() / union.sum() * 100.0) if union.sum() else np.nan,
        "a_only": int((a & ~b).sum()),
        "b_only": int((b & ~a).sum()),
    }


def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(f"file:{Path(args.db).resolve().as_posix()}?mode=ro", uri=True)

    try:
        symbols = load_symbols(connection, args.exchange, args.period)
        frames = []
        for symbol in symbols:
            raw = load_frame(connection, symbol, args.exchange, args.period)
            if len(raw) < WARMUP + max(HORIZONS):
                continue
            data = enrich(raw, args.period, args.window, args.min_history)
            data["symbol"] = symbol
            data["signal_time"] = data.index
            frames.append(data.reset_index(drop=True))

        if not frames:
            raise RuntimeError("No usable data")

        all_rows = pd.concat(frames, ignore_index=True)
        masks = state_masks(all_rows, args.min_price, args.min_turnover)

        event_times = all_rows.loc[masks["production"], "signal_time"]
        research_mask, holdout_mask = chronological_sample_mask(
            all_rows["signal_time"], event_times, args.holdout_fraction
        )

        for key, mask in list(masks.items()):
            shifted = (
                pd.Series(mask.to_numpy(), index=all_rows.index)
                .groupby(all_rows["symbol"], sort=False)
                .shift(1, fill_value=False)
                .astype(bool)
            )
            masks[f"{key}_fresh"] = mask & ~shifted

        summary_rows: list[dict] = []
        for group_name in (
            "production",
            "production_fresh",
            "previous_turnover",
            "previous_turnover_fresh",
            "squeeze_only",
            "squeeze_only_fresh",
            "slot_rvol",
            "slot_rvol_fresh",
        ):
            for sample_name, sample_mask in (("research", research_mask), ("holdout", holdout_mask)):
                append_group_rows(
                    summary_rows,
                    all_rows,
                    masks[group_name] & sample_mask,
                    group_name,
                    sample_name,
                )
        pd.DataFrame(summary_rows).to_csv(
            out_dir / f"squeeze_robustness_summary_{args.period}.csv", index=False
        )

        matched_rows = []
        matched_rows.extend(
            matched_control_rows(
                all_rows,
                masks["previous_turnover"],
                masks["low_volume_control"],
                "production_rvol_vs_same_squeeze_low_volume",
            )
        )
        if args.period in INTRADAY:
            matched_rows.extend(
                matched_control_rows(
                    all_rows,
                    masks["slot_rvol"],
                    masks["low_volume_control"],
                    "slot_rvol_vs_same_squeeze_low_volume",
                )
            )
        pd.DataFrame(matched_rows).to_csv(
            out_dir / f"squeeze_matched_control_{args.period}.csv", index=False
        )

        overlap_rows = [
            variant_overlap(masks["production"], masks["previous_turnover"], "turnover_current_vs_previous"),
            variant_overlap(masks["production"], masks["slot_rvol"], "standard_vs_slot_rvol"),
        ]
        pd.DataFrame(overlap_rows).to_csv(
            out_dir / f"squeeze_variant_overlap_{args.period}.csv", index=False
        )

        rank_variant = pd.DataFrame(
            {
                "inclusive_hit": masks["previous_turnover"],
                "previous_rank_hit": (
                    (np.arange(len(all_rows)) >= WARMUP - 1)
                    & (all_rows["close"] >= args.min_price)
                    & (all_rows["turnover_previous_only"] >= args.min_turnover)
                    & (all_rows["bb_rank_previous_only"] <= PRODUCTION_BB_RANK_MAX)
                    & (all_rows["rvol"] >= PRODUCTION_RVOL_MIN)
                ),
            }
        )
        rank_overlap = variant_overlap(
            rank_variant["inclusive_hit"],
            rank_variant["previous_rank_hit"],
            "bb_rank_inclusive_vs_previous_only",
        )
        pd.DataFrame([rank_overlap]).to_csv(
            out_dir / f"squeeze_rank_variant_{args.period}.csv", index=False
        )

        manifest = {
            "scanner": "technical.squeeze_volume",
            "stage": "robustness",
            "period": args.period,
            "symbols_in_db": len(symbols),
            "symbols_usable": int(all_rows["symbol"].nunique()),
            "rows": int(len(all_rows)),
            "production_rule": {
                "bb_rank_max": PRODUCTION_BB_RANK_MAX,
                "rvol_min": PRODUCTION_RVOL_MIN,
                "minimum_turnover": args.min_turnover,
                "minimum_price": args.min_price,
            },
            "comparisons": [
                "production all-state vs fresh-only",
                "current-inclusive turnover vs previous-only turnover",
                "production RVOL vs same-squeeze low-volume matched controls",
                "intraday same-slot RVOL variant",
                "inclusive BB rank vs previous-only BB rank",
            ],
            "matched_control_keys": [
                "symbol",
                "quarter",
                "slot",
                "0.25-log10 previous turnover bucket",
                "5-point BB-rank bucket",
            ],
        }
        (out_dir / f"squeeze_robustness_manifest_{args.period}.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research-only squeeze-volume robustness audit")
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
    run(args)
