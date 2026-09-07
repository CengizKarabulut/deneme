"""Fixed-rule robustness test for NE ARARSAN VAR histogram entry on 1D / 1W.

Purpose
-------
Resolve the final production ambiguity without adaptive fold-by-fold selection:
- Is histogram sign (positive/negative) useful as a hard entry filter?
- Does -100 < CCI20 < 100 add robust value?

All six entry variants are held FIXED across four chronological evaluation
windows. Exit logic is also fixed to the previously strongest structural
control_123 profile for each timeframe. This is robustness research on already
observed historical data, NOT a fresh untouched holdout.

Common entry skeleton:
- Close > EMA5 > EMA8 > EMA13
- 30 < RSI14 < 60
- RVOL20 > 1.50
- H[t] > H[t-1] > H[t-2]
- no StochRSI

Variants:
- sign unrestricted / H < 0 / H > 0
- each with CCI off / -100 < CCI20 < 100

Execution:
- fresh False -> True event only
- entry at next-bar open
- 10 bps commission + 10 bps slippage per side
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_data_store import MarketDataStore
from ne_ararsan_var_research import WARMUP, build_indicator_frame
from ne_ararsan_var_histogram_wf import (
    add_histogram,
    build_entry_events,
    collect,
    entry_variants,
    exit_variants,
    metrics,
)

PERIODS = ("1D", "1W")
BOUNDARIES = (0.45, 0.60, 0.75, 0.90, 1.00)


def _fixed_exit(period: str) -> dict[str, Any]:
    controls = [row for row in exit_variants(period) if row["name"] == "control_123"]
    if not controls:
        raise RuntimeError(f"{period}: control_123 exit profile bulunamadı")
    return dict(controls[0])


def _classification(result: dict[str, Any]) -> str:
    m = result["stitched"]
    positive_folds = int(result["positive_expectancy_folds"])
    pf1_folds = int(result["pf_above_1_folds"])
    trades = int(m.get("trades", 0))
    exp = float(m.get("expectancy_r", 0.0))
    pf = float(m.get("profit_factor") or 0.0)
    worst = float(result["worst_fold_expectancy_r"])

    if trades < 80:
        return "INSUFFICIENT_SAMPLE"
    if positive_folds == 4 and pf1_folds == 4 and exp > 0.10 and pf > 1.20 and worst > 0:
        return "ROBUST_STRONG"
    if positive_folds >= 3 and pf1_folds >= 3 and exp > 0 and pf > 1.10:
        return "ROBUST_PROMISING"
    if exp > 0 and pf > 1.0:
        return "POSITIVE_BUT_UNSTABLE"
    return "REJECT"


def _rank_key(result: dict[str, Any]) -> tuple:
    m = result["stitched"]
    # Stability first, then edge. No parameter-count bonus for sign filters.
    return (
        int(result["positive_expectancy_folds"]),
        int(result["pf_above_1_folds"]),
        float(result["median_fold_expectancy_r"]),
        float(m.get("expectancy_r", -99.0)),
        float(m.get("profit_factor") or 0.0),
        int(m.get("trades", 0)),
    )


def analyze(db: str, period: str) -> dict[str, Any]:
    if period not in PERIODS:
        raise ValueError(period)

    variants = entry_variants()
    fixed_exit = _fixed_exit(period)
    frames = []
    all_times: list[pd.Timestamp] = []
    signal_counts: dict[str, int] = {v["name"]: 0 for v in variants}

    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", period)
        for i, symbol in enumerate(symbols, 1):
            frame = store.load_dataframe(symbol, "BIST", period, limit=0)
            if frame is None or len(frame) <= WARMUP + 5:
                continue
            data = add_histogram(build_indicator_frame(frame))
            positions_by_entry = {}
            for variant in variants:
                events = build_entry_events(data, variant)
                positions = [
                    int(x)
                    for x in np.flatnonzero(events.to_numpy(dtype=bool))
                    if x >= WARMUP and x + 1 < len(data)
                ]
                positions_by_entry[variant["name"]] = positions
                signal_counts[variant["name"]] += len(positions)
                all_times.extend(pd.Timestamp(data.index[x]) for x in positions)
            if any(positions_by_entry.values()):
                frames.append((symbol, data, positions_by_entry))
            if i % 100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)} loaded", flush=True)

    all_times.sort()
    if len(all_times) < 100:
        raise RuntimeError(f"{period}: yalnız {len(all_times)} ortak aday olay var")

    bounds = [
        pd.Timestamp(all_times[min(len(all_times) - 1, int(len(all_times) * q))])
        for q in BOUNDARIES[:-1]
    ]
    bounds.append(pd.Timestamp(all_times[-1]) + pd.Timedelta(days=3700))

    results = []
    for variant in variants:
        folds = []
        stitched = []
        for fold_idx in range(4):
            start = bounds[fold_idx]
            end = bounds[fold_idx + 1]
            trades = collect(
                frames,
                variant["name"],
                fixed_exit,
                start=start,
                end=end,
            )
            fm = metrics(trades)
            stitched.extend(trades)
            folds.append(
                {
                    "fold": fold_idx + 1,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "metrics": fm,
                }
            )

        stitched_m = metrics(stitched)
        fold_exp = [float(f["metrics"].get("expectancy_r", 0.0)) for f in folds]
        fold_pf = [float(f["metrics"].get("profit_factor") or 0.0) for f in folds]
        result = {
            "entry": variant,
            "signal_count_full_history": signal_counts[variant["name"]],
            "folds": folds,
            "stitched": stitched_m,
            "positive_expectancy_folds": sum(x > 0 for x in fold_exp),
            "pf_above_1_folds": sum(x > 1 for x in fold_pf),
            "median_fold_expectancy_r": float(np.median(fold_exp)),
            "worst_fold_expectancy_r": float(min(fold_exp)),
            "best_fold_expectancy_r": float(max(fold_exp)),
        }
        result["classification"] = _classification(result)
        results.append(result)

    results.sort(key=_rank_key, reverse=True)

    # Simplicity tie-break interpretation is reported separately rather than
    # silently changing the ranking. 'any' is the simplest histogram rule.
    unrestricted = [r for r in results if r["entry"]["sign"] == "any"]
    unrestricted.sort(key=_rank_key, reverse=True)

    return {
        "version": "ne-ararsan-var-histogram-fixed-robustness-v1",
        "period": period,
        "method": (
            "six fixed entry rules across four chronological windows; no adaptive "
            "fold selection; fixed control_123 structural exit; next-bar-open; "
            "10bps commission + 10bps slippage per side"
        ),
        "warning": "Historical robustness only; earlier research already observed this history.",
        "common_entry": "Close > EMA5 > EMA8 > EMA13; 30<RSI14<60; RVOL20>1.50; H[t]>H[t-1]>H[t-2]",
        "fixed_exit": fixed_exit,
        "ranked_variants": results,
        "best_statistical_variant": results[0],
        "best_sign_unrestricted_variant": unrestricted[0] if unrestricted else None,
        "decision_hint": (
            "Prefer sign-unrestricted if its stability/edge is close to the top variant; "
            "hard-code histogram sign only if it produces a material and stable improvement."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    payload = analyze(args.db, args.period)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
