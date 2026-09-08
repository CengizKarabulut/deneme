"""Scan 14 MACD DipDonusu A/B/C entry research."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_BB = Path(__file__).resolve().parents[1] / "bb_squeeze"
sys.path.insert(0, str(_BB))
from bb_squeeze_entry_stage import (  # noqa: E402
    MarketDataStore,
    PERIODS,
    WARMUP,
    structure,
    metrics,
    bounds_for,
    collect,
)


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def atr14(frame: pd.DataFrame) -> pd.Series:
    h = pd.to_numeric(frame["high"], errors="coerce")
    l = pd.to_numeric(frame["low"], errors="coerce")
    c = pd.to_numeric(frame["close"], errors="coerce")
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/14.0, adjust=False, min_periods=14).mean()


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    c = pd.to_numeric(out["close"], errors="coerce")
    v = pd.to_numeric(out["volume"], errors="coerce")
    macd = ema(c, 12) - ema(c, 26)
    sig = ema(macd, 9)
    prev20 = v.shift(1).rolling(20, min_periods=20).mean()
    out["macd"] = macd
    out["macd_signal"] = sig
    out["macd_cross_up"] = ((macd > sig) & (macd.shift(1) <= sig.shift(1))).fillna(False)
    out["rvol20"] = v / prev20.replace(0.0, np.nan)
    out["atr14"] = atr14(out)
    return out


def entry_variants() -> list[dict[str, Any]]:
    return [
        {"name": "A_no_rvol", "mode": "A", "rvol_min": None},
        {"name": "B_original_rvol_1_20", "mode": "B", "rvol_min": 1.20},
        {"name": "C_strong_rvol_1_50", "mode": "C", "rvol_min": 1.50},
    ]


def entry_events(d: pd.DataFrame, variant: dict[str, Any]) -> pd.Series:
    m = pd.to_numeric(d["macd"], errors="coerce")
    base = ((m < 0.0) & d["macd_cross_up"]).fillna(False)
    threshold = variant.get("rvol_min")
    if threshold is None:
        return base
    rvol = pd.to_numeric(d["rvol20"], errors="coerce")
    return (base & (rvol > float(threshold))).fillna(False)


def classify(row: dict[str, Any]) -> str:
    m = row["stitched"]
    n = int(m.get("trades", 0))
    pf = float(m.get("profit_factor") or 0.0)
    e = float(m.get("expectancy_r", 0.0))
    pos = int(row["positive_folds"])
    worst = float(row["worst_fold_expectancy_r"])
    if n < 30:
        return "INSUFFICIENT_SAMPLE"
    if pos == 4 and pf > 1.20 and e > 0.08 and worst > 0:
        return "ROBUST_STRONG"
    if pos >= 3 and pf > 1.10 and e > 0:
        return "ROBUST_PROMISING"
    if pf > 1 and e > 0:
        return "POSITIVE_UNSTABLE"
    return "REJECT"


def analyze(db: str, period: str) -> dict[str, Any]:
    variants = entry_variants()
    p = structure(period)
    frames = []
    times = {v["name"]: [] for v in variants}
    counts = Counter()

    with MarketDataStore(db, read_only=True) as store:
        syms = store.list_symbols("BIST", period)
        for i, sym in enumerate(syms, 1):
            fr = store.load_dataframe(sym, "BIST", period, limit=0)
            if fr is None or len(fr) <= WARMUP + 22:
                continue
            d = indicators(fr)
            pbe = {}
            for variant in variants:
                ev = entry_events(d, variant)
                ps = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x >= WARMUP and x + 1 < len(d)]
                pbe[variant["name"]] = ps
                counts[variant["name"]] += len(ps)
                times[variant["name"]].extend(pd.Timestamp(d.index[x]) for x in ps)
            if any(pbe.values()):
                frames.append((sym, d, pbe))
            if i % 100 == 0 or i == len(syms):
                print(f"[{period}] {i}/{len(syms)}", flush=True)

    for key in times:
        times[key].sort()

    rows = []
    for variant in variants:
        name = variant["name"]
        b = bounds_for(times[name])
        if not b:
            rows.append({
                "entry": variant,
                "signal_count": counts[name],
                "folds": [],
                "stitched": {"trades": 0, "profit_factor": None, "expectancy_r": 0.0, "win_rate_pct": 0.0},
                "positive_folds": 0,
                "worst_fold_expectancy_r": 0.0,
                "median_fold_expectancy_r": 0.0,
                "classification": "INSUFFICIENT_SAMPLE",
            })
            continue

        folds, stitched = [], []
        for fi in range(4):
            tr = collect(frames, name, p, b[fi], b[fi+1])
            stitched.extend(tr)
            folds.append({"fold": fi+1, "metrics": metrics(tr)})
        sm = metrics(stitched)
        ex = [float(f["metrics"].get("expectancy_r", 0.0)) for f in folds]
        row = {
            "entry": variant,
            "signal_count": counts[name],
            "folds": folds,
            "stitched": sm,
            "positive_folds": sum(x > 0 for x in ex),
            "worst_fold_expectancy_r": float(min(ex)),
            "median_fold_expectancy_r": float(np.median(ex)),
        }
        row["classification"] = classify(row)
        rows.append(row)

    rank = {"ROBUST_STRONG": 4, "ROBUST_PROMISING": 3, "POSITIVE_UNSTABLE": 2, "REJECT": 1, "INSUFFICIENT_SAMPLE": 0}
    rows.sort(
        key=lambda x: (
            rank[x["classification"]],
            x["positive_folds"],
            x["worst_fold_expectancy_r"],
            x["median_fold_expectancy_r"],
            float(x["stitched"].get("expectancy_r", 0.0)),
        ),
        reverse=True,
    )
    return {
        "version": "scan14-entry-abc-v1",
        "period": period,
        "method": "A/B/C RVOL isolation; same structural exit; entry-specific four chronological windows; costs included",
        "definitions": {
            "A": "MACD Level<0 + fresh bullish MACD/Signal crossover; no RVOL filter",
            "B": "MACD Level<0 + fresh bullish MACD/Signal crossover + RVOL20>1.20",
            "C": "MACD Level<0 + fresh bullish MACD/Signal crossover + RVOL20>1.50",
            "RVOL20": "Volume[t] / mean(Volume[t-1]...Volume[t-20]); current bar excluded from denominator",
        },
        "rows": rows,
        "best": rows[0] if rows else None,
        "warning": "Historical observed data; future unseen bars are true forward validation.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    result = analyze(a.db, a.period)
    p = Path(a.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
