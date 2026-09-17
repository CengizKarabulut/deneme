from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from exact_replay_common import HORIZONS, finalize_events, load_symbol, load_symbols, wilder_atr

CONFIGURED_SHADOW = {"1h", "4h", "1d", "1w", "1wk", "1mo"}
SCHEDULED_RESEARCH = {"4h", "1d"}


def period_delta(period: str) -> timedelta:
    value = period.casefold()
    if value.endswith("m") and value != "1mo":
        return timedelta(minutes=int(value[:-1]))
    if value.endswith("h"):
        return timedelta(hours=int(value[:-1]))
    if value in {"1d", "d"}:
        return timedelta(days=1)
    if value in {"1w", "1wk", "w"}:
        return timedelta(days=7)
    return timedelta(days=1)


def build_frame(df: pd.DataFrame, symbol: str, period: str, start: int, end: int):
    from market_intelligence.core.enums import PriceBasis
    from market_intelligence.core.timeframes import parse_timeframe
    from market_intelligence.market_data.bars import CanonicalBar, CanonicalFrame

    delta = period_delta(period)
    view = df.iloc[start:end]
    bars = tuple(
        CanonicalBar(
            open_time=row.candle_time.to_pydatetime() - delta,
            close_time=row.candle_time.to_pydatetime(),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in view.itertuples(index=False)
    )
    return CanonicalFrame(
        instrument_id=f"BIST:{symbol}",
        symbol_at_snapshot=symbol,
        market="BIST",
        timeframe=parse_timeframe(period),
        snapshot_id=f"ma-oos:{symbol}:{period}:{end}",
        series_revision=0,
        price_basis=PriceBasis.RAW,
        source="historical-sqlite-causal-oos",
        bars=bars,
        is_partial=False,
        quality="complete",
    )


def append_event(
    rows: list[dict],
    df: pd.DataFrame,
    i: int,
    direction: int,
    atr: float,
    fresh: bool,
    symbol: str,
    qualification,
    ma_value: float,
    distance_atr: float,
) -> None:
    if i + max(HORIZONS) >= len(df) or not np.isfinite(atr) or atr <= 0:
        return
    entry = float(df.close.iloc[i])
    row: dict[str, object] = {
        "symbol": symbol,
        "time": df.candle_time.iloc[i],
        "direction": direction,
        "fresh": fresh,
        "ma_type": qualification.ma_type,
        "period": int(qualification.period),
        "qualification_side": qualification.qualification_side,
        "level_class": qualification.level_class,
        "touches": int(qualification.touches),
        "quality_score": float(qualification.quality_score),
        "ma_value": ma_value,
        "distance_atr": distance_atr,
    }
    for h in HORIZONS:
        future = df.iloc[i + 1 : i + h + 1]
        row[f"ret_{h}"] = float(df.close.iloc[i + h] / entry - 1.0)
        if direction >= 0:
            row[f"mfe_{h}"] = float(future.high.max() / entry - 1.0)
            row[f"mae_{h}"] = float(future.low.min() / entry - 1.0)
        else:
            row[f"mfe_{h}"] = float(entry / future.low.min() - 1.0)
            row[f"mae_{h}"] = float(entry / future.high.max() - 1.0)
        row[f"range_atr_{h}"] = float((future.high.max() - future.low.min()) / atr)
    rows.append(row)


def audit(
    db: Path,
    period: str,
    exchange: str,
    out_dir: Path,
    holdout: float,
    qualification_fraction: float,
    research_bars: int,
) -> None:
    from market_intelligence.features.ma import ma_series
    from market_intelligence.research.ma_levels import MaResearchConfig, research_ma_levels

    scanner = "ma.near_zone"
    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    symbols = load_symbols(conn, exchange, period)
    rows: list[dict] = []
    eligible = 0
    qualified_symbols = 0
    qualification_count = 0
    accepted_count = 0
    level_class_counts: dict[str, int] = {}

    config = MaResearchConfig()
    minimum_training = max(config.periods) + config.independence_bars + config.reaction_bars + 20

    for symbol in symbols:
        df = load_symbol(conn, symbol, exchange, period)
        if len(df) < minimum_training + max(HORIZONS) + 50:
            continue
        cutoff = int(math.floor(len(df) * qualification_fraction))
        if cutoff < minimum_training or len(df) - cutoff <= max(HORIZONS):
            continue
        eligible += 1
        research_start = max(0, cutoff - research_bars)
        frame = build_frame(df, symbol, period, research_start, cutoff)
        qualifications = research_ma_levels(frame, config)
        qualification_count += len(qualifications)
        accepted = tuple(q for q in qualifications if q.level_class in {"strong_level", "level"})
        for q in qualifications:
            level_class_counts[q.level_class] = level_class_counts.get(q.level_class, 0) + 1
        accepted_count += len(accepted)
        if not accepted:
            continue
        qualified_symbols += 1

        close = df.close.to_list()
        volume = df.volume.to_list()
        atr = wilder_atr(df, 14)
        series = {
            (q.ma_type, q.period): ma_series(q.ma_type, close, volume, q.period)
            for q in accepted
        }
        previous_selected: set[str] = set()
        for i in range(cutoff, len(df) - max(HORIZONS)):
            if not np.isfinite(atr[i]) or atr[i] <= 0:
                previous_selected = set()
                continue
            current_price = float(df.close.iloc[i])
            candidates: list[tuple[object, float, str, float]] = []
            for q in accepted:
                value = series[(q.ma_type, q.period)][i]
                if value is None or not math.isfinite(value):
                    continue
                side = "support" if value <= current_price else "resistance"
                if q.qualification_side not in {"both", side}:
                    continue
                distance = (float(value) - current_price) / float(atr[i])
                if abs(distance) > 1.0:
                    continue
                candidates.append((q, float(value), side, distance))

            selected: list[tuple[object, float, str, float]] = []
            for side in ("support", "resistance"):
                matching = sorted(
                    (item for item in candidates if item[2] == side),
                    key=lambda item: (-float(item[0].quality_score), abs(float(item[3]))),
                )
                selected.extend(matching[:2])

            current_selected: set[str] = set()
            for q, value, side, distance in selected:
                level_id = f"{q.ma_type.upper()}:{q.period}:{side}"
                current_selected.add(level_id)
                direction = 1 if side == "support" else -1
                append_event(
                    rows,
                    df,
                    i,
                    direction,
                    float(atr[i]),
                    level_id not in previous_selected,
                    symbol,
                    q,
                    value,
                    distance,
                )
            previous_selected = current_selected

    conn.close()
    key = period.casefold()
    operation_status = (
        "scheduled_research_supported"
        if key in SCHEDULED_RESEARCH
        else "manual_registry_supported"
        if key in CONFIGURED_SHADOW
        else "research_extension_not_in_production_shadow_config"
    )
    manifest = {
        "scanner": scanner,
        "period": period,
        "exchange": exchange,
        "symbols_in_db": len(symbols),
        "symbols_with_min_history": eligible,
        "symbols_with_accepted_qualification": qualified_symbols,
        "qualification_records": qualification_count,
        "accepted_qualification_records": accepted_count,
        "qualification_level_classes": level_class_counts,
        "qualification_fraction": qualification_fraction,
        "research_bars": research_bars,
        "operation_status": operation_status,
        "parity_note": "causal_frozen_qualification_oos_using_exact_production_ma_research",
        "limitation": "Production PostgreSQL qualification-state history is unavailable in candle SQLite; qualifications are frozen at the 60% history cutoff and tested only afterward.",
    }
    events, summaries = finalize_events(rows, out_dir, manifest, holdout)
    print(json.dumps({**manifest, "events": len(events), "summary": summaries}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--exchange", default="BIST")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--holdout", type=float, default=0.20)
    parser.add_argument("--qualification-fraction", type=float, default=0.60)
    parser.add_argument("--research-bars", type=int, default=1000)
    args = parser.parse_args()
    audit(
        Path(args.db),
        args.period,
        args.exchange,
        Path(args.out_dir),
        args.holdout,
        args.qualification_fraction,
        args.research_bars,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
