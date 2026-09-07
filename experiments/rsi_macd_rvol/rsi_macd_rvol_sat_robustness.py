"""Narrow SAT robustness for frozen RSI/MACD/RVOL entries.

Frozen entries come from the separated entry-quality stage. Only exit/risk
parameters are varied in a narrow neighborhood. Baseline changes only when a
candidate is stable in all four entry-specific chronological windows and gives
a material improvement without meaningfully weakening the worst window.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from rsi_macd_rvol_wf import (
    BOUNDARIES,WARMUP,MarketDataStore,indicators,entry_variants,entry_events,
    exit_variants,collect,metrics
)

PERIODS=("4H","1D","1W","1M")
ENTRY_BY_PERIOD={
    "4H":"r55_70__A_cross",
    "1D":"r50_65__B_hist_rise2",
    "1W":"r50_65__A_cross",
    "1M":"r55_70__D_hist_pos_rise",
}
EXIT_BY_PERIOD={"4H":"adaptive","1D":"structural_control","1W":"structural_control","1M":"structural_control"}


def base_profile(period:str)->dict[str,Any]:
    target=EXIT_BY_PERIOD[period]
    return dict(next(x for x in exit_variants(period) if x['name']==target))


def load_frames(db:str,period:str,entry_name:str):
    e=next(x for x in entry_variants() if x['name']==entry_name)
    frames=[]; times=[]; count=0
    with MarketDataStore(db,read_only=True) as store:
        symbols=store.list_symbols('BIST',period)
        for i,symbol in enumerate(symbols,1):
            frame=store.load_dataframe(symbol,'BIST',period,limit=0)
            if frame is None or len(frame)<=WARMUP+22: continue
            data=indicators(frame); ev=entry_events(data,e)
            ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
            if ps:
                frames.append((symbol,data,{entry_name:ps})); count+=len(ps); times.extend(pd.Timestamp(data.index[x]) for x in ps)
            if i%100==0 or i==len(symbols): print(f'[{period}] {i}/{len(symbols)}',flush=True)
    times.sort(); return frames,times,count


def bounds_for(times):
    if len(times)<80: return []
    b=[pd.Timestamp(times[min(len(times)-1,int(len(times)*q))]) for q in BOUNDARIES[:-1]]
    b.append(pd.Timestamp(times[-1])+pd.Timedelta(days=3700)); return b


def evaluate(frames,entry_name,p,bounds):
    folds=[]; stitched=[]
    for fi in range(4):
        tr=collect(frames,entry_name,p,bounds[fi],bounds[fi+1]); m=metrics(tr); stitched.extend(tr)
        folds.append({'fold':fi+1,'start':bounds[fi].isoformat(),'end':bounds[fi+1].isoformat(),'metrics':m})
    sm=metrics(stitched); exps=[float(f['metrics'].get('expectancy_r',0)) for f in folds]
    return {'params':{k:p.get(k) for k in ('name','rule','stop_mode','stop_atr','swing','buffer','trail','tight','max_hold','tp1','tp2','tp3')},
            'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in exps),
            'worst_fold_expectancy_r':float(min(exps)),'median_fold_expectancy_r':float(np.median(exps))}


def rank_rows(rows):
    return sorted(rows,key=lambda r:(int(r['positive_folds']),float(r['worst_fold_expectancy_r']),float(r['median_fold_expectancy_r']),float(r['stitched'].get('expectancy_r',0)),float(r['stitched'].get('profit_factor') or 0)),reverse=True)


def plateau_pick(rows,keys):
    ranked=rank_rows(rows); eligible=[r for r in ranked if r['positive_folds']==4 and r['worst_fold_expectancy_r']>0]; pool=eligible or ranked
    n=max(3,min(9,int(math.ceil(len(pool)*.25)))); top=pool[:n]
    centers={k:float(np.median([float(r['params'][k]) for r in top])) for k in keys}
    scales={}
    for k in keys:
        u=sorted(set(float(r['params'][k]) for r in rows)); dif=[b-a for a,b in zip(u[:-1],u[1:]) if b>a]; scales[k]=float(np.median(dif)) if dif else 1.0
    def dist(r): return sum(abs(float(r['params'][k])-centers[k])/max(scales[k],1e-9) for k in keys)
    chosen=sorted(top,key=lambda r:(dist(r),-r['worst_fold_expectancy_r'],-r['median_fold_expectancy_r'],-float(r['stitched'].get('expectancy_r',0))))[0]
    return chosen,centers,top


def material(candidate,baseline):
    cm,bm=candidate['stitched'],baseline['stitched']
    de=float(cm.get('expectancy_r',0))-float(bm.get('expectancy_r',0)); dpf=float(cm.get('profit_factor') or 0)-float(bm.get('profit_factor') or 0); dw=candidate['worst_fold_expectancy_r']-baseline['worst_fold_expectancy_r']
    stable=candidate['positive_folds']==4 and candidate['worst_fold_expectancy_r']>0
    adopt=stable and dw>=-.02 and (de>=.03 or dpf>=.10)
    return adopt,{'delta_expectancy_r':de,'delta_profit_factor':dpf,'delta_worst_fold_expectancy_r':dw}


def analyze(db,period):
    entry=ENTRY_BY_PERIOD[period]; base=base_profile(period); frames,times,count=load_frames(db,period,entry); bounds=bounds_for(times)
    if not bounds: return {'period':period,'classification':'INSUFFICIENT_SAMPLE','signals':count}
    baseline=evaluate(frames,entry,base,bounds); baseline['label']='baseline'

    swings=sorted(set([max(3,int(base['swing'])-2),int(base['swing']),int(base['swing'])+2]))
    buffers=sorted(set([round(max(0,float(base['buffer'])-.05),2),round(float(base['buffer']),2),round(float(base['buffer'])+.05,2)]))
    trails=sorted(set([round(max(.8,float(base['trail'])-.20),2),round(float(base['trail']),2),round(float(base['trail'])+.20,2)]))
    geom=[]
    for sw in swings:
      for bu in buffers:
       for tr in trails:
        p=dict(base); p.update({'swing':sw,'buffer':bu,'trail':tr}); r=evaluate(frames,entry,p,bounds); r['label']=f'g_s{sw}_b{bu}_t{tr}'; geom.append(r)
    gpick,gcenter,gtop=plateau_pick(geom,('swing','buffer','trail'))

    chosen_params=gpick['params']; tight_rows=[]
    if base['rule']=='adaptive':
        tv=sorted(set([round(max(.7,float(base['tight'])-.15),2),round(float(base['tight']),2),round(float(base['tight'])+.15,2)]))
        for ti in tv:
            p=dict(base); p.update({'swing':int(chosen_params['swing']),'buffer':float(chosen_params['buffer']),'trail':float(chosen_params['trail']),'tight':ti}); r=evaluate(frames,entry,p,bounds); r['label']=f'tight_{ti}'; tight_rows.append(r)
        tpick,_,_=plateau_pick(tight_rows,('tight',)); chosen_params=tpick['params']

    holds=sorted(set([max(8,int(round(base['max_hold']*.8))),int(base['max_hold']),int(round(base['max_hold']*1.2))]))
    tpfams=[('fast',(.9,1.8,2.7)),('base',(1.,2.,3.)),('wide',(1.1,2.2,3.3))]
    stage_b=[]
    for nm,tps in tpfams:
      for hold in holds:
        p=dict(base); p.update({'swing':int(chosen_params['swing']),'buffer':float(chosen_params['buffer']),'trail':float(chosen_params['trail']),'tight':float(chosen_params['tight']),'max_hold':hold,'tp1':tps[0],'tp2':tps[1],'tp3':tps[2]}); r=evaluate(frames,entry,p,bounds); r['label']=f'{nm}_h{hold}'; stage_b.append(r)
    cand,center_b,top_b=plateau_pick(stage_b,('tp1','tp2','tp3','max_hold'))
    adopt,delta=material(cand,baseline); final=cand if adopt else baseline
    return {'version':'rsi-macd-rvol-sat-robustness-v1','period':period,'entry_frozen':entry,'exit_family_frozen':EXIT_BY_PERIOD[period],
            'method':'entry frozen; entry-specific 4 chronological windows; 27 geometry candidates; optional 3 tight-trail candidates; 9 TP/hold candidates; plateau selection; material-improvement gate',
            'signal_count':count,'baseline':baseline,'geometry':{'chosen':gpick,'center':gcenter,'top':gtop},'tight_stage':tight_rows,
            'tp_hold':{'chosen':cand,'center':center_b,'top':top_b},'candidate_vs_baseline':delta,
            'decision':'ADOPT_NARROW_OPTIMIZED' if adopt else 'KEEP_BASELINE','final_profile':final,
            'warning':'Historical research on observed data; future bars are true forward validation.'}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--period',choices=PERIODS,required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    d=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__': main()
