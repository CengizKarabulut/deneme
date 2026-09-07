"""Entry-only robustness stage for RSI/MACD/RVOL.

All 12 entry variants are compared with the SAME structural-control exit.
Each entry uses its own four chronological validation windows. This separates
signal quality from exit management before SAT tuning.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from rsi_macd_rvol_wf import (
    BOUNDARIES, WARMUP, MarketDataStore, indicators, entry_variants, entry_events,
    exit_variants, collect, metrics, classify
)


def bounds_for(times:list[pd.Timestamp])->list[pd.Timestamp]:
    if len(times)<80: return []
    b=[pd.Timestamp(times[min(len(times)-1,int(len(times)*q))]) for q in BOUNDARIES[:-1]]
    b.append(pd.Timestamp(times[-1])+pd.Timedelta(days=3700))
    return b


def analyze(db:str,period:str)->dict[str,Any]:
    entries=entry_variants()
    control=next(x for x in exit_variants(period) if x['name']=='structural_control')
    frames=[]; times={e['name']:[] for e in entries}; counts={e['name']:0 for e in entries}
    with MarketDataStore(db,read_only=True) as store:
        symbols=store.list_symbols('BIST',period)
        for i,symbol in enumerate(symbols,1):
            frame=store.load_dataframe(symbol,'BIST',period,limit=0)
            if frame is None or len(frame)<=WARMUP+22: continue
            data=indicators(frame); pbe={}
            for e in entries:
                ev=entry_events(data,e)
                ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
                pbe[e['name']]=ps; counts[e['name']]+=len(ps)
                times[e['name']].extend(pd.Timestamp(data.index[x]) for x in ps)
            if any(pbe.values()): frames.append((symbol,data,pbe))
            if i%100==0 or i==len(symbols): print(f'[{period}] {i}/{len(symbols)}',flush=True)
    rows=[]
    for e in entries:
        ts=sorted(times[e['name']]); b=bounds_for(ts)
        if not b: continue
        folds=[]; stitched=[]
        for fi in range(4):
            tr=collect(frames,e['name'],control,b[fi],b[fi+1]); m=metrics(tr); stitched.extend(tr)
            folds.append({'fold':fi+1,'start':b[fi].isoformat(),'end':b[fi+1].isoformat(),'metrics':m})
        sm=metrics(stitched); exps=[float(f['metrics'].get('expectancy_r',0)) for f in folds]; pfs=[float(f['metrics'].get('profit_factor') or 0) for f in folds]
        r={'entry':e,'exit':control,'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in exps),
           'pf_above_1_folds':sum(x>1 for x in pfs),'worst_fold_expectancy_r':float(min(exps)),
           'median_fold_expectancy_r':float(np.median(exps)),'best_fold_expectancy_r':float(max(exps))}
        r['classification']=classify(r); rows.append(r)
    rank={'ROBUST_STRONG':4,'ROBUST_PROMISING':3,'POSITIVE_UNSTABLE':2,'REJECT':1,'INSUFFICIENT_SAMPLE':0}
    rows.sort(key=lambda r:(rank.get(r['classification'],0),r['positive_folds'],r['worst_fold_expectancy_r'],r['median_fold_expectancy_r'],float(r['stitched'].get('expectancy_r',0)),float(r['stitched'].get('profit_factor') or 0)),reverse=True)
    return {'version':'rsi-macd-rvol-entry-stage-v1','period':period,
            'method':'12 frozen entries; identical structural-control exit; entry-specific four chronological validation windows; costs included',
            'signal_counts':counts,'best':rows[0] if rows else None,'ranked_entries':rows,
            'warning':'Historical research; future data remains true forward validation.'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--period',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    d=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__': main()
