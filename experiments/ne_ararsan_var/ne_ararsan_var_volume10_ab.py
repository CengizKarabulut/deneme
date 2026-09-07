"""A/B robustness: NE ARARSAN VAR final entry with vs without same-TF 10-bar volume filter.

Baseline final entry (1D/1W):
- Close > EMA5 > EMA8 > EMA13
- 30 < RSI14 < 60
- RVOL20 > 1.50
- MACD histogram rises for two consecutive steps
- no CCI / no StochRSI / histogram sign unrestricted

Candidate extra filter:
- Volume[t] > mean(Volume[t-1] ... Volume[t-10])

Current bar is deliberately excluded from the 10-bar reference mean.
Fixed structural exits are used; no fold-by-fold parameter selection.
"""
from __future__ import annotations

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

from market_data_store import MarketDataStore
from ne_ararsan_var_research import WARMUP, build_indicator_frame
from ne_ararsan_var_histogram_wf import add_histogram, build_entry_events, collect, exit_variants, metrics

PERIODS = ("1D", "1W")
BOUNDARIES = (0.45, 0.60, 0.75, 0.90, 1.00)


def fixed_exit(period: str):
    rows = [x for x in exit_variants(period) if x["name"] == "control_123"]
    if not rows:
        raise RuntimeError("control_123 not found")
    return dict(rows[0])


def analyze(db: str, period: str):
    if period not in PERIODS:
        raise ValueError(period)
    frames = []
    base_times = []
    counts = {"baseline": 0, "plus_volume10": 0}
    base_variant = {"name": "baseline", "sign": "any", "cci": False}

    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", period)
        for i, symbol in enumerate(symbols, 1):
            raw = store.load_dataframe(symbol, "BIST", period, limit=0)
            if raw is None or len(raw) <= WARMUP + 5:
                continue
            data = add_histogram(build_indicator_frame(raw))
            base_events = build_entry_events(data, base_variant)
            volume = pd.to_numeric(data["volume"], errors="coerce")
            prev10_mean = volume.shift(1).rolling(10, min_periods=10).mean()
            vol10 = (volume > prev10_mean).fillna(False)
            plus_events = (base_events & vol10).fillna(False)

            pos_base = [int(x) for x in np.flatnonzero(base_events.to_numpy(bool)) if x >= WARMUP and x + 1 < len(data)]
            pos_plus = [int(x) for x in np.flatnonzero(plus_events.to_numpy(bool)) if x >= WARMUP and x + 1 < len(data)]
            if pos_base or pos_plus:
                frames.append((symbol, data, {"baseline": pos_base, "plus_volume10": pos_plus}))
            counts["baseline"] += len(pos_base)
            counts["plus_volume10"] += len(pos_plus)
            base_times.extend(pd.Timestamp(data.index[x]) for x in pos_base)
            if i % 100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)}", flush=True)

    base_times.sort()
    if len(base_times) < 100:
        raise RuntimeError(f"insufficient events: {len(base_times)}")
    bounds = [pd.Timestamp(base_times[min(len(base_times)-1, int(len(base_times)*q))]) for q in BOUNDARIES[:-1]]
    bounds.append(pd.Timestamp(base_times[-1]) + pd.Timedelta(days=3700))
    exit_p = fixed_exit(period)

    results = {}
    for name in ("baseline", "plus_volume10"):
        folds, stitched = [], []
        for idx in range(4):
            trades = collect(frames, name, exit_p, start=bounds[idx], end=bounds[idx+1])
            m = metrics(trades)
            stitched.extend(trades)
            folds.append({"fold": idx+1, "start": bounds[idx].isoformat(), "end": bounds[idx+1].isoformat(), "metrics": m})
        sm = metrics(stitched)
        exps = [float(f["metrics"].get("expectancy_r", 0)) for f in folds]
        pfs = [float(f["metrics"].get("profit_factor") or 0) for f in folds]
        results[name] = {
            "signal_count_full_history": counts[name],
            "folds": folds,
            "stitched": sm,
            "positive_expectancy_folds": sum(x > 0 for x in exps),
            "pf_above_1_folds": sum(x > 1 for x in pfs),
            "worst_fold_expectancy_r": min(exps),
            "median_fold_expectancy_r": float(np.median(exps)),
        }

    b = results["baseline"]["stitched"]
    v = results["plus_volume10"]["stitched"]
    return {
        "version": "ne-ararsan-var-volume10-ab-v1",
        "period": period,
        "volume10_rule": "Volume[t] > mean(Volume[t-1]..Volume[t-10]); same timeframe; current bar excluded",
        "fixed_exit": exit_p,
        "results": results,
        "delta_plus_minus_base": {
            "trades": int(v.get("trades",0)) - int(b.get("trades",0)),
            "profit_factor": float(v.get("profit_factor") or 0) - float(b.get("profit_factor") or 0),
            "expectancy_r": float(v.get("expectancy_r",0)) - float(b.get("expectancy_r",0)),
            "win_rate_pct": float(v.get("win_rate_pct",0)) - float(b.get("win_rate_pct",0)),
        },
        "decision_rule": "Add volume10 only if edge/stability improves materially without collapsing sample size.",
        "warning": "Historical A/B robustness on already-observed history; not a fresh untouched holdout."
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    payload = analyze(args.db, args.period)
    p = Path(args.output); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
