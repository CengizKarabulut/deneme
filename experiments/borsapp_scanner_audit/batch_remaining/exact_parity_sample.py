from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class Reservoir:
    limit: int
    rng: random.Random
    seen: int = 0
    items: list[tuple[str, int, int]] | None = None

    def __post_init__(self) -> None:
        self.items = []

    def add(self, item: tuple[str, int, int]) -> None:
        self.seen += 1
        assert self.items is not None
        if len(self.items) < self.limit:
            self.items.append(item)
            return
        j = self.rng.randrange(self.seen)
        if j < self.limit:
            self.items[j] = item


def add_paths(borsapp_root: Path, audit_root: Path) -> None:
    sys.path.insert(0, str((borsapp_root / "src").resolve()))
    sys.path.insert(0, str(audit_root.resolve()))


def period_delta(period: str) -> timedelta:
    p = period.casefold()
    if p.endswith("m"):
        return timedelta(minutes=int(p[:-1]))
    if p.endswith("h"):
        return timedelta(hours=int(p[:-1]))
    if p in {"1d", "d"}:
        return timedelta(days=1)
    if p in {"1w", "1wk", "w"}:
        return timedelta(days=7)
    raise ValueError(period)


def load_symbol(conn: sqlite3.Connection, symbol: str, exchange: str, period: str) -> pd.DataFrame:
    q = """
    SELECT candle_time, open, high, low, close, volume
    FROM candles WHERE symbol=? AND exchange=? AND period=? ORDER BY candle_time
    """
    df = pd.read_sql_query(q, conn, params=(symbol, exchange, period))
    if df.empty:
        return df
    df["candle_time"] = pd.to_datetime(df["candle_time"], errors="coerce", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna().reset_index(drop=True)


def build_feature_engine():
    from market_intelligence.features.decision import DecisionPanelV645Provider
    from market_intelligence.features.momentum import (
        LegacyRsi7Provider,
        LegacyRsi14Provider,
        MacdProvider,
        RsiProvider,
        SmiProvider,
    )
    from market_intelligence.features.registry import FeatureEngine, FeatureRegistry
    from market_intelligence.features.research import ResearchTechnicalSnapshotProvider
    from market_intelligence.features.technical import TechnicalMarketContextProvider
    from market_intelligence.features.trend import (
        InclusiveVolumeSma10Provider,
        InclusiveVolumeSma20Provider,
        LegacyTrendMaProvider,
    )
    from market_intelligence.features.volatility import WilderAtr14Provider
    from market_intelligence.features.volume import RelativeVolume20Provider

    registry = FeatureRegistry()
    for provider in (
        RelativeVolume20Provider(),
        MacdProvider(),
        RsiProvider(),
        SmiProvider(),
        LegacyRsi7Provider(),
        LegacyRsi14Provider(),
        LegacyTrendMaProvider(),
        InclusiveVolumeSma10Provider(),
        InclusiveVolumeSma20Provider(),
        WilderAtr14Provider(),
        DecisionPanelV645Provider(),
        TechnicalMarketContextProvider(),
        ResearchTechnicalSnapshotProvider(),
    ):
        registry.register(provider)
    return FeatureEngine(registry)


def build_frame(df: pd.DataFrame, symbol: str, period: str, end_idx: int, max_bars: int):
    from market_intelligence.core.enums import PriceBasis
    from market_intelligence.core.timeframes import parse_timeframe
    from market_intelligence.market_data.bars import CanonicalBar, CanonicalFrame

    start = max(0, end_idx - max_bars + 1)
    view = df.iloc[start : end_idx + 1]
    delta = period_delta(period)
    bars = []
    for row in view.itertuples(index=False):
        close_time = row.candle_time.to_pydatetime()
        bars.append(
            CanonicalBar(
                open_time=close_time - delta,
                close_time=close_time,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
        )
    return CanonicalFrame(
        instrument_id=f"BIST:{symbol}",
        symbol_at_snapshot=symbol,
        market="BIST",
        timeframe=parse_timeframe(period),
        snapshot_id=f"parity:{symbol}:{period}:{end_idx}",
        series_revision=0,
        price_basis=PriceBasis.RAW,
        source="historical-sqlite-parity",
        bars=tuple(bars),
        is_partial=False,
        quality="complete",
    )


def direction_code(findings) -> int:
    from market_intelligence.core.enums import Direction

    if not findings:
        return 0
    values = {f.direction for f in findings}
    if Direction.BULLISH in values and Direction.BEARISH not in values:
        return 1
    if Direction.BEARISH in values and Direction.BULLISH not in values:
        return -1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--scanner", required=True)
    parser.add_argument("--period", required=True)
    parser.add_argument("--borsapp-root", type=Path, required=True)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exchange", default="BIST")
    parser.add_argument("--positive-sample", type=int, default=800)
    parser.add_argument("--negative-sample", type=int, default=1600)
    parser.add_argument("--zero-positive-negative-sample", type=int, default=3200)
    parser.add_argument("--minimum-index", type=int, default=300)
    parser.add_argument("--max-bars", type=int, default=420)
    args = parser.parse_args()

    if args.scanner == "ma.near_zone":
        raise SystemExit("ma.near_zone requires persistent MA qualification history")

    add_paths(args.borsapp_root, args.audit_root)

    import remaining_scanners_batch as proxy
    from market_intelligence.core.enums import EvaluationStatus
    from market_intelligence.scanning.catalog import load_scanner_catalog
    from market_intelligence.scanning.contracts import ScanContext
    from market_intelligence.scanning.pipeline import ScanPipeline

    bindings = {
        binding.scanner.id: binding
        for binding in load_scanner_catalog(args.borsapp_root / "config" / "scanners.toml")
    }
    binding = bindings[args.scanner]
    engine = build_feature_engine()
    pipeline = ScanPipeline(engine)

    seed_text = f"{args.scanner}|{args.period}|production-parity-v1"
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16)
    pos_res = Reservoir(args.positive_sample, random.Random(seed ^ 0xA5A5))
    neg_res = Reservoir(args.zero_positive_negative_sample, random.Random(seed ^ 0x5A5A))

    uri = f"file:{args.db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    symbols = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol",
            (args.exchange, args.period),
        ).fetchall()
    ]

    eligible_bars = 0
    proxy_positive_bars = 0
    for symbol in symbols:
        df = load_symbol(conn, symbol, args.exchange, args.period)
        if len(df) <= args.minimum_index + 20:
            continue
        mask, direction = proxy.signal_mask(df, args.scanner)
        m = np.asarray(mask.fillna(False) if hasattr(mask, "fillna") else mask, dtype=bool)
        d = np.asarray(direction, dtype=int)
        last = len(df) - 20
        for i in range(args.minimum_index, last):
            eligible_bars += 1
            item = (symbol, i, int(d[i]))
            if m[i]:
                proxy_positive_bars += 1
                pos_res.add(item)
            else:
                neg_res.add(item)

    assert pos_res.items is not None and neg_res.items is not None
    neg_limit = args.negative_sample if pos_res.items else args.zero_positive_negative_sample
    negatives = neg_res.items[:neg_limit]
    samples = [(1, x) for x in pos_res.items] + [(0, x) for x in negatives]

    by_symbol: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    for proxy_match, (symbol, idx, proxy_dir) in samples:
        by_symbol[symbol].append((proxy_match, idx, proxy_dir))

    total = resolved = agreement = unknown = 0
    proxy_pos = proxy_neg = exact_pos = 0
    exact_on_proxy_pos = exact_on_proxy_neg = 0
    both_positive = direction_compared = direction_agree = 0
    mismatch_rows: list[dict] = []

    for symbol, symbol_samples in sorted(by_symbol.items()):
        df = load_symbol(conn, symbol, args.exchange, args.period)
        for proxy_match, idx, proxy_dir in sorted(symbol_samples, key=lambda x: x[1]):
            total += 1
            proxy_pos += int(proxy_match == 1)
            proxy_neg += int(proxy_match == 0)
            frame = build_frame(df, symbol, args.period, idx, args.max_bars)
            context = ScanContext(
                evaluation_time=frame.through_bar_time,
                bar_close_time=frame.through_bar_time,
                market_session_id=f"BIST:{frame.through_bar_time.date().isoformat()}",
                calendar_version="bist-session-v1",
                ruleset_hash=binding.ruleset_hash,
            )
            result = pipeline.run(
                cycle_id="production-parity",
                frame=frame,
                scanner=binding.scanner,
                context=context,
            ).scan
            if result.evaluation.status is EvaluationStatus.UNKNOWN:
                unknown += 1
                if len(mismatch_rows) < 100:
                    mismatch_rows.append(
                        {
                            "symbol": symbol,
                            "index": idx,
                            "time": frame.through_bar_time.isoformat(),
                            "proxy_match": proxy_match,
                            "proxy_direction": proxy_dir,
                            "exact_status": "unknown",
                            "exact_direction": 0,
                            "error_code": result.evaluation.error_code or "",
                            "error_detail": result.evaluation.error_detail or "",
                        }
                    )
                continue
            resolved += 1
            exact_match = int(result.evaluation.status is EvaluationStatus.MATCH)
            exact_dir = direction_code(result.findings)
            exact_pos += exact_match
            agreement += int(exact_match == proxy_match)
            if proxy_match:
                exact_on_proxy_pos += exact_match
            else:
                exact_on_proxy_neg += exact_match
            if proxy_match and exact_match:
                both_positive += 1
                if proxy_dir != 0 and exact_dir != 0:
                    direction_compared += 1
                    direction_agree += int(proxy_dir == exact_dir)
            if exact_match != proxy_match or (proxy_match and exact_match and proxy_dir and exact_dir and proxy_dir != exact_dir):
                if len(mismatch_rows) < 100:
                    mismatch_rows.append(
                        {
                            "symbol": symbol,
                            "index": idx,
                            "time": frame.through_bar_time.isoformat(),
                            "proxy_match": proxy_match,
                            "proxy_direction": proxy_dir,
                            "exact_status": "match" if exact_match else "no_match",
                            "exact_direction": exact_dir,
                            "error_code": "",
                            "error_detail": "",
                        }
                    )

    conn.close()

    agreement_rate = agreement / resolved if resolved else None
    precision = exact_on_proxy_pos / proxy_pos if proxy_pos else None
    fn_estimate = exact_on_proxy_neg / proxy_neg if proxy_neg else None
    direction_rate = direction_agree / direction_compared if direction_compared else None

    if resolved < 500:
        gate = "insufficient_resolved_sample"
    elif proxy_pos < 30:
        gate = "insufficient_positive_evidence"
        if exact_on_proxy_neg > 0:
            gate = "fail_proxy_missed_production_positives"
    elif (
        agreement_rate is not None
        and agreement_rate >= 0.995
        and precision is not None
        and precision >= 0.99
        and fn_estimate is not None
        and fn_estimate <= 0.005
        and (direction_rate is None or direction_rate >= 0.995)
    ):
        gate = "pass"
    else:
        gate = "fail"

    payload = {
        "scanner": args.scanner,
        "period": args.period,
        "production_version": binding.scanner.version,
        "symbols": len(symbols),
        "eligible_bars": eligible_bars,
        "proxy_positive_bars": proxy_positive_bars,
        "sample_total": total,
        "sample_resolved": resolved,
        "sample_unknown": unknown,
        "proxy_positive_sample": proxy_pos,
        "proxy_negative_sample": proxy_neg,
        "exact_positive_sample": exact_pos,
        "exact_on_proxy_positive": exact_on_proxy_pos,
        "exact_on_proxy_negative": exact_on_proxy_neg,
        "agreement": agreement_rate,
        "proxy_positive_precision": precision,
        "proxy_negative_exact_positive_rate": fn_estimate,
        "direction_compared": direction_compared,
        "direction_agreement": direction_rate,
        "gate": gate,
        "thresholds": {
            "agreement": 0.995,
            "positive_precision": 0.99,
            "negative_exact_positive_rate": 0.005,
            "direction_agreement": 0.995,
        },
    }

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "parity.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame(mismatch_rows).to_csv(args.out / "mismatches.csv", index=False)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
