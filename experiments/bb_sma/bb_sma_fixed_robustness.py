"""Fixed-combination robustness for BB/SMA scan.

Every entry/exit combination is held fixed across four chronological windows.
No per-fold re-selection is allowed. This tests whether initial walk-forward
winners are stable rather than adaptive-selection artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bb_sma_wf import (
    BOUNDARIES,
    WARMUP,
    MarketDataStore,
    collect,
    entry_events,
    entry_variants,
    exit_variants,
    indicators,
    metrics,
)

PERIODS = ("2H","4H","1D","1W","1M")


def classify(row: dict[str,Any]) -> str:
    m = row["stitched"]
    trades = int(m.get("trades",0))
    pf = float(m.get("profit_factor") or 0.0)
    exp = float(m.get("expectancy_r",0.0))
    pos = int(row["positive_folds"])
    worst = float(row["worst_fold_expectancy_r"])
    if trades < 30:
        return "INSUFFICIENT_SAMPLE"
    if pos == 4 and pf > 1.20 and exp > 0.08 and worst > 0:
        return "ROBUST_STRONG"
    if pos >= 3 and pf > 1.10 and exp > 0:
        return "ROBUST_PROMISING"
    if pf > 1.0 and exp > 0:
        return "POSITIVE_UNSTABLE"
    return "REJECT"


def analyze(db: str, period: str) -> dict[str,Any]:
    entries = entry_variants()
    exits = exit_variants(period)
    frames = []
    event_times = set()
    signal_counts = {e["name"]:0 for e in entries}

    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", period)
        for i, symbol in enumerate(symbols,1):
            frame = store.load_dataframe(symbol,"BIST",period,limit=0)
            if frame is None or len(frame) <= WARMUP+22:
                continue
            data = indicators(frame)
            pbe = {}
            for e in entries:
                ev = entry_events(data,e["name"])
                ps = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
                pbe[e["name"]] = ps
                signal_counts[e["name"]] += len(ps)
                event_times.update(pd.Timestamp(data.index[x]) for x in ps)
            if any(pbe.values()):
                frames.append((symbol,data,pbe))
            if i%100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)}", flush=True)

    times = sorted(event_times)
    if len(times) < 80:
        return {"period":period,"classification":"INSUFFICIENT_SAMPLE","unique_events":len(times)}

    bounds = [pd.Timestamp(times[min(len(times)-1,int(len(times)*q))]) for q in BOUNDARIES[:-1]]
    bounds.append(pd.Timestamp(times[-1]) + pd.Timedelta(days=3700))

    rows = []
    for e in entries:
        for x in exits:
            folds = []
            stitched = []
            for fi in range(4):
                tr = collect(frames,e["name"],x,start=bounds[fi],end=bounds[fi+1])
                m = metrics(tr)
                stitched.extend(tr)
                folds.append({
                    "fold":fi+1,
                    "start":bounds[fi].isoformat(),
                    "end":bounds[fi+1].isoformat(),
                    "metrics":m,
                })
            sm = metrics(stitched)
            exps = [float(f["metrics"].get("expectancy_r",0.0)) for f in folds]
            pfs = [float(f["metrics"].get("profit_factor") or 0.0) for f in folds]
            row = {
                "entry":e,
                "exit":x,
                "folds":folds,
                "stitched":sm,
                "positive_folds":sum(v>0 for v in exps),
                "pf_above_1_folds":sum(v>1 for v in pfs),
                "median_fold_expectancy_r":float(np.median(exps)),
                "worst_fold_expectancy_r":float(min(exps)),
                "best_fold_expectancy_r":float(max(exps)),
            }
            row["classification"] = classify(row)
            rows.append(row)

    rank = {"ROBUST_STRONG":4,"ROBUST_PROMISING":3,"POSITIVE_UNSTABLE":2,"REJECT":1,"INSUFFICIENT_SAMPLE":0}
    rows.sort(
        key=lambda r:(
            rank.get(r["classification"],0),
            r["positive_folds"],
            r["worst_fold_expectancy_r"],
            r["median_fold_expectancy_r"],
            float(r["stitched"].get("expectancy_r",0.0)),
            float(r["stitched"].get("profit_factor") or 0.0),
        ),
        reverse=True,
    )

    return {
        "version":"bb-sma-fixed-robustness-v1",
        "period":period,
        "method":"All 4 entry x 6 exit combinations held fixed across four chronological windows; costs included; no per-fold re-selection",
        "signal_counts":signal_counts,
        "bounds":[b.isoformat() for b in bounds],
        "ranked_combinations":rows,
        "best":rows[0],
        "warning":"Historical robustness on already-observed history, not fresh untouched holdout.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",required=True)
    ap.add_argument("--period",choices=PERIODS,required=True)
    ap.add_argument("--output",required=True)
    args = ap.parse_args()
    payload = analyze(args.db,args.period)
    path = Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2,default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
