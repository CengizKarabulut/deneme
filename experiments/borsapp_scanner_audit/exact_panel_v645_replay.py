from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import numpy as np

from exact_replay_common import (
    add_forward_metrics,
    finalize_events,
    fresh_from_mask,
    load_symbol,
    load_symbols,
    wilder_atr,
)


def build_frame(df, symbol: str):
    from market_intelligence.core.enums import PriceBasis
    from market_intelligence.core.timeframes import Timeframe
    from market_intelligence.market_data.bars import CanonicalBar, CanonicalFrame

    bars = tuple(
        CanonicalBar(
            open_time=row.candle_time.to_pydatetime() - timedelta(days=1),
            close_time=row.candle_time.to_pydatetime(),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            volume=float(row.volume),
        )
        for row in df.itertuples(index=False)
    )
    return CanonicalFrame(
        instrument_id=f"BIST:{symbol}",
        symbol_at_snapshot=symbol,
        market="BIST",
        timeframe=Timeframe.D1,
        snapshot_id=f"exact-panel:{symbol}",
        series_revision=0,
        price_basis=PriceBasis.RAW,
        source="historical-sqlite-exact-replay",
        bars=bars,
        is_partial=False,
        quality="complete",
    )


def audit(db: Path, period: str, exchange: str, out_dir: Path, holdout: float) -> None:
    scanner = "decision.panel_v645"
    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    symbols = load_symbols(conn, exchange, period)

    if period.casefold() not in {"1d", "d"}:
        conn.close()
        manifest = {
            "scanner": scanner,
            "period": period,
            "exchange": exchange,
            "symbols_in_db": len(symbols),
            "symbols_with_min_history": 0,
            "raw_matches_before_forward_horizon": 0,
            "parity_note": "unsupported_timeframe_by_production_contract",
            "production_supported_timeframes": ["1D"],
        }
        events, summaries = finalize_events([], out_dir, manifest, holdout)
        print(json.dumps({**manifest, "events": len(events), "summary": summaries}, ensure_ascii=False))
        return

    from market_intelligence.features.decision import decision_v645_frame
    from market_intelligence.features.volatility import wilder_atr_series

    rows: list[dict] = []
    eligible = 0
    raw_events = 0
    setup_counts: dict[str, int] = {}
    for symbol in symbols:
        df = load_symbol(conn, symbol, exchange, period)
        if len(df) < 252:
            continue
        eligible += 1
        frame = build_frame(df, symbol)
        atr_series = wilder_atr_series(frame, 14)
        if atr_series is None:
            continue
        panel = decision_v645_frame(frame, atr_series, minimum_score=75)
        mask = (panel["entry"].fillna(False).astype(bool) & (panel["score"] >= 75)).to_numpy(dtype=bool)
        raw_events += int(mask.sum())
        if "new_setup" in panel.columns:
            for value, count in panel.loc[mask, "new_setup"].value_counts().items():
                setup_counts[str(value)] = setup_counts.get(str(value), 0) + int(count)
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
        "setup_counts": setup_counts,
        "parity_note": "exact_production_decision_v645_frame",
        "production_supported_timeframes": ["1D"],
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
    args = parser.parse_args()
    audit(Path(args.db), args.period, args.exchange, Path(args.out_dir), args.holdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
