"""Fixed-entry robustness for the StochRSI/Momentum/Volume scan.

A/B/C entry definitions are never re-selected inside folds. Each rule is held
constant across four chronological windows with the same structural_control
exit. This checks whether the adaptive walk-forward winner is a stable rule.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd

from market_data_store import MarketDataStore
from stoch_momentum_volume_wf import (
    WARMUP, BOUNDARIES, indicators, entry_variants, entry_events,
    exit_variants, collect, metrics,
)

PERIODS=("4H","1D","1W","1M")


def fixed_exit(period):
    rows=[x for x in exit_variants(period) if x["name"]=="structural_control"]
    if not rows: raise RuntimeError("structural_control missing")
    return dict(rows[0])


def classify(r):
    m=r["stitched"]; t=int(m.get("trades",0)); pf=float(m.get("profit_factor") or 0); e=float(m.get("expectancy_r",0)); pos=r["positive_folds"]
    if t<80: return "INSUFFICIENT_SAMPLE"
    if pos==4 and pf>1.20 and e>0.08 and r["worst_fold_expectancy_r"]>0: return "ROBUST_STRONG"
    if pos>=3 and pf>1.10 and e>0: return "ROBUST_PROMISING"
    if pf>1 and e>0: return "POSITIVE_UNSTABLE"
    return "REJECT"


def analyze(db,period):
    entries=entry_variants(); frames=[]; all_times=[]; counts=Counter()
    with MarketDataStore(db,read_only=True) as store:
        symbols=store.list_symbols("BIST",period)
        for i,symbol in enumerate(symbols,1):
            frame=store.load_dataframe(symbol,"BIST",period,limit=0)
            if frame is None or len(frame)<=WARMUP+22: continue
            data=indicators(frame); pbe={}
            for e in entries:
                ev=entry_events(data,e["name"])
                ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
                pbe[e["name"]]=ps; counts[e["name"]]+=len(ps); all_times.extend(pd.Timestamp(data.index[x]) for x in ps)
            if any(pbe.values()): frames.append((symbol,data,pbe))
            if i%100==0 or i==len(symbols): print(f"[{period}] {i}/{len(symbols)}",flush=True)
    all_times.sort()
    if len(all_times)<80: return {"period":period,"classification":"INSUFFICIENT_SAMPLE"}
    bounds=[pd.Timestamp(all_times[min(len(all_times)-1,int(len(all_times)*q))]) for q in BOUNDARIES[:-1]]
    bounds.append(pd.Timestamp(all_times[-1])+pd.Timedelta(days=3700))
    p=fixed_exit(period); results=[]
    for e in entries:
        folds=[]; stitched=[]
        for fi in range(4):
            tr=collect(frames,e["name"],p,start=bounds[fi],end=bounds[fi+1]); m=metrics(tr); stitched.extend(tr)
            folds.append({"fold":fi+1,"start":bounds[fi].isoformat(),"end":bounds[fi+1].isoformat(),"metrics":m})
        sm=metrics(stitched); exps=[float(f["metrics"].get("expectancy_r",0)) for f in folds]; pfs=[float(f["metrics"].get("profit_factor") or 0) for f in folds]
        row={"entry":e,"signal_count_full_history":counts[e["name"]],"folds":folds,"stitched":sm,"positive_folds":sum(x>0 for x in exps),"pf_above_1_folds":sum(x>1 for x in pfs),"median_fold_expectancy_r":float(np.median(exps)),"worst_fold_expectancy_r":float(min(exps))}
        row["classification"]=classify(row); results.append(row)
    results.sort(key=lambda r:(r["positive_folds"],r["median_fold_expectancy_r"],float(r["stitched"].get("expectancy_r",0)),float(r["stitched"].get("profit_factor") or 0)),reverse=True)
    return {"version":"stoch-mom-vol-fixed-robustness-v1","period":period,"method":"A/B/C held fixed across 4 chronological windows; structural_control fixed; current volume > previous 10 same-TF bar average; costs included","fixed_exit":p,"ranked_entries":results,"best":results[0],"warning":"Historical robustness on already-observed history, not fresh untouched holdout."}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--db",required=True); ap.add_argument("--period",choices=PERIODS,required=True); ap.add_argument("--output",required=True); a=ap.parse_args()
    d=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8"); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=="__main__": main()
