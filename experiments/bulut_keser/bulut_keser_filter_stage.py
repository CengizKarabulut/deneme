"""BulutKeser second-stage filter robustness.

Kumo findings are frozen first:
- 4H: inside cloud (research candidate)
- 1D: below cloud
- 1W: compare no cloud filter vs above cloud

Then only ADX/BB/RVOL filters are varied under the SAME structural exit.
"""
from __future__ import annotations

import argparse, json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bulut_keser_cloud_stage import (
    MarketDataStore, WARMUP, structure, metrics, bounds_for, collect,
    indicators, simulate,
)

PERIODS = ('4H','1D','1W')


def candidate_clouds(period: str) -> tuple[str, ...]:
    return {'4H': ('inside',), '1D': ('below',), '1W': ('all','above')}[period]


def variants(period: str) -> list[dict[str, Any]]:
    rows=[]
    for cloud in candidate_clouds(period):
        for adx_mode in ('20_40','gt20','20_35'):
            for bb_mode in ('inside','positive_half','none'):
                for rvol in (1.2,1.5):
                    rows.append({
                        'name': f'{cloud}__adx_{adx_mode}__bb_{bb_mode}__rv{str(rvol).replace(".","")}',
                        'cloud': cloud, 'adx_mode': adx_mode, 'bb_mode': bb_mode, 'rvol': rvol,
                    })
    return rows


def cloud_ok(d: pd.DataFrame, mode: str) -> pd.Series:
    c=pd.to_numeric(d['close'],errors='coerce')
    top=pd.to_numeric(d['cloud_top'],errors='coerce'); bot=pd.to_numeric(d['cloud_bottom'],errors='coerce')
    if mode=='all': return pd.Series(True,index=d.index)
    if mode=='above': return (top.notna() & (c>top)).fillna(False)
    if mode=='inside': return (top.notna() & bot.notna() & (c>=bot) & (c<=top)).fillna(False)
    if mode=='below': return (bot.notna() & (c<bot)).fillna(False)
    raise ValueError(mode)


def adx_ok(adx: pd.Series, mode: str) -> pd.Series:
    if mode=='20_40': return ((adx>=20)&(adx<=40)).fillna(False)
    if mode=='gt20': return (adx>20).fillna(False)
    if mode=='20_35': return ((adx>=20)&(adx<=35)).fillna(False)
    raise ValueError(mode)


def bb_ok(d: pd.DataFrame, mode: str) -> pd.Series:
    c=pd.to_numeric(d['close'],errors='coerce'); lo=pd.to_numeric(d['bb_lower'],errors='coerce'); up=pd.to_numeric(d['bb_upper'],errors='coerce'); basis=pd.to_numeric(d['bb_basis'],errors='coerce')
    if mode=='inside': return ((c>lo)&(c<up)).fillna(False)
    if mode=='positive_half': return ((c>basis)&(c<up)).fillna(False)
    if mode=='none': return pd.Series(True,index=d.index)
    raise ValueError(mode)


def entry_events(d: pd.DataFrame, v: dict[str, Any]) -> pd.Series:
    adx=pd.to_numeric(d['adx14'],errors='coerce'); rv=pd.to_numeric(d['rvol20'],errors='coerce')
    return (d['tenkan_cross_up'] & cloud_ok(d,v['cloud']) & adx_ok(adx,v['adx_mode']) & bb_ok(d,v['bb_mode']) & (rv>float(v['rvol']))).fillna(False)


def classify(row: dict[str,Any]) -> str:
    m=row['stitched']; n=int(m.get('trades',0)); pf=float(m.get('profit_factor') or 0); e=float(m.get('expectancy_r',0)); pos=row['positive_folds']; worst=row['worst_fold_expectancy_r']
    if n<30:return 'INSUFFICIENT_SAMPLE'
    if pos==4 and pf>1.20 and e>0.08 and worst>0:return 'ROBUST_STRONG'
    if pos>=3 and pf>1.10 and e>0:return 'ROBUST_PROMISING'
    if pf>1 and e>0:return 'POSITIVE_UNSTABLE'
    return 'REJECT'


def analyze(db: str, period: str) -> dict[str,Any]:
    entries=variants(period); p=structure(period); frames=[]; times={e['name']:[] for e in entries}; counts=Counter()
    with MarketDataStore(db,read_only=True) as store:
        syms=store.list_symbols('BIST',period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22: continue
            d=indicators(fr); pbe={}
            for e in entries:
                ev=entry_events(d,e); ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
                pbe[e['name']]=ps; counts[e['name']]+=len(ps); times[e['name']].extend(pd.Timestamp(d.index[x]) for x in ps)
            if any(pbe.values()): frames.append((sym,d,pbe))
            if i%100==0 or i==len(syms): print(f'[{period}] {i}/{len(syms)}',flush=True)
    for k in times: times[k].sort()
    rows=[]
    for e in entries:
        b=bounds_for(times[e['name']])
        if not b: continue
        folds=[]; stitched=[]
        for fi in range(4):
            tr=collect(frames,e['name'],p,b[fi],b[fi+1]); stitched.extend(tr); folds.append({'fold':fi+1,'metrics':metrics(tr)})
        sm=metrics(stitched); ex=[float(f['metrics'].get('expectancy_r',0)) for f in folds]
        row={'entry':e,'signal_count':counts[e['name']],'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':float(min(ex)),'median_fold_expectancy_r':float(np.median(ex))}
        row['classification']=classify(row); rows.append(row)
    rank={'ROBUST_STRONG':4,'ROBUST_PROMISING':3,'POSITIVE_UNSTABLE':2,'REJECT':1,'INSUFFICIENT_SAMPLE':0}
    rows.sort(key=lambda x:(rank[x['classification']],x['positive_folds'],x['worst_fold_expectancy_r'],x['median_fold_expectancy_r'],float(x['stitched'].get('expectancy_r',0)),int(x['stitched'].get('trades',0))),reverse=True)
    return {'version':'bulut-keser-filter-stage-v1','period':period,'frozen_cloud_candidates':candidate_clouds(period),'method':'Kumo decision frozen; ADX/BB/RVOL only; same structural exit; entry-specific four chronological windows; costs included','rows':rows,'best':rows[0] if rows else None,'warning':'Observed historical data; future unseen bars are true forward validation.'}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--period',choices=PERIODS,required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    result=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__': main()
