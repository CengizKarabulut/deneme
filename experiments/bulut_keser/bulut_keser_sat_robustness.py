"""SAT robustness for frozen BulutKeser entries.

Frozen entries after Kumo + filter stages:
- 4H research: cloud-inside reference
- 1D active candidate: below cloud + ADX20-35 + BB positive half + RVOL1.5
- 1W active candidate: above cloud + ADX20-35 + no BB filter + RVOL1.5

Ichimoku exits are compared against the same structural control. Entry rules are not retuned here.
"""
from __future__ import annotations

import argparse, json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bulut_keser_cloud_stage import MarketDataStore, WARMUP, indicators, metrics, bounds_for, initial_stop
from bulut_keser_filter_stage import variants, entry_events

CANDIDATES = {
    '4H': ('4H', 'inside__adx_gt20__bb_inside__rv12'),
    '1D': ('1D', 'below__adx_20_35__bb_positive_half__rv15'),
    '1W': ('1W', 'above__adx_20_35__bb_none__rv15'),
}

BASE = {
    '4H': dict(stop_mode='swing', stop_atr=1.20, swing=7, buffer=.20, trail=2.0, tight=1.5, max_hold=40, tp1=1., tp2=2., tp3=3.),
    '1D': dict(stop_mode='swing', stop_atr=1.25, swing=7, buffer=.20, trail=2.2, tight=1.6, max_hold=40, tp1=1., tp2=2., tp3=3.),
    '1W': dict(stop_mode='swing', stop_atr=1.30, swing=9, buffer=.15, trail=2.3, tight=1.7, max_hold=60, tp1=1., tp2=2., tp3=3.),
}


def families(period: str) -> tuple[str, ...]:
    if period == '1W':
        return ('structural','tk_exit','kijun_exit','cloud_bottom_exit','ichi_tighten','adaptive')
    return ('structural','tk_exit','kijun_exit','ichi_tighten','adaptive')


def find_entry(period: str, name: str) -> dict[str, Any]:
    return next(v for v in variants(period) if v['name'] == name)


def load_frames(db: str, period: str, entry_name: str):
    ent = find_entry(period, entry_name); frames=[]; times=[]; count=0
    with MarketDataStore(db, read_only=True) as store:
        syms=store.list_symbols('BIST',period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22: continue
            d=indicators(fr); ev=entry_events(d,ent)
            ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
            if ps:
                frames.append((sym,d,{entry_name:ps})); count+=len(ps); times.extend(pd.Timestamp(d.index[x]) for x in ps)
            if i%100==0 or i==len(syms): print(f'[{period}] {i}/{len(syms)}',flush=True)
    times.sort(); return frames,times,count


def simulate(d: pd.DataFrame, sp: int, p: dict[str,Any], family: str, period: str):
    ep=sp+1
    if ep>=len(d): return None
    entry=float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry<=0: return None
    stop,risk=initial_stop(d,sp,entry,p)
    tp1=entry+risk*p['tp1']; tp2=entry+risk*p['tp2']; tp3=entry+risk*p['tp3']
    rem=1.; cash=0.; h1=h2=h3=False; trail=False; tight=False; highest=entry; minlow=entry; maxhigh=entry; reason='TIME'; xp=ep
    last=min(len(d)-1,ep+int(p['max_hold'])-1)

    for pos in range(ep,last+1):
        row=d.iloc[pos]; hi=float(row['high']); lo=float(row['low']); cl=float(row['close'])
        highest=max(highest,hi); maxhigh=max(maxhigh,hi); minlow=min(minlow,lo)
        if lo<=stop:
            cash+=rem*stop; rem=0.; reason='TRAIL' if trail or tight else 'STOP'; xp=pos; break
        if not h1 and hi>=tp1:
            q=min(rem,.30); cash+=q*tp1; rem-=q; h1=True
        if rem>1e-12 and not h2 and hi>=tp2:
            q=min(rem,.30); cash+=q*tp2; rem-=q; h2=True; trail=True
        if rem>1e-12 and not h3 and hi>=tp3:
            q=min(rem,.20); cash+=q*tp3; rem-=q; h3=True

        ten=float(row['tenkan']); kij=float(row['kijun']); top=float(row['cloud_top']) if pd.notna(row['cloud_top']) else np.nan; bot=float(row['cloud_bottom']) if pd.notna(row['cloud_bottom']) else np.nan
        prev_ten=float(d['tenkan'].iloc[pos-1]) if pos>=1 and pd.notna(d['tenkan'].iloc[pos-1]) else np.nan
        prev_kij=float(d['kijun'].iloc[pos-1]) if pos>=1 and pd.notna(d['kijun'].iloc[pos-1]) else np.nan
        tk_down=np.isfinite(ten) and np.isfinite(kij) and np.isfinite(prev_ten) and np.isfinite(prev_kij) and ten<kij and prev_ten>=prev_kij
        kij_loss=np.isfinite(kij) and cl<kij
        cloud_top_loss=np.isfinite(top) and cl<top
        cloud_bottom_loss=np.isfinite(bot) and cl<bot
        hard=False

        if family=='tk_exit':
            hard=tk_down
        elif family=='kijun_exit':
            hard=kij_loss
        elif family=='cloud_bottom_exit':
            hard=cloud_bottom_loss
        elif family=='ichi_tighten':
            tight=tight or kij_loss or (period=='1W' and cloud_top_loss)
        elif family=='adaptive':
            tight=tight or kij_loss or (period=='1W' and cloud_top_loss)
            if period=='1W':
                hard=cloud_bottom_loss and np.isfinite(ten) and np.isfinite(kij) and ten<kij
            else:
                hard=tk_down

        if hard and rem>1e-12:
            cash+=rem*cl; rem=0.; reason='TECH'; xp=pos; break

        if rem>1e-12 and (trail or tight):
            a=float(row['atr14'])
            if np.isfinite(a) and a>0:
                stop=max(stop, highest-float(p['tight'] if tight else p['trail'])*a)

        if pos==last and rem>1e-12:
            cash+=rem*cl; rem=0.; reason='TIME'; xp=pos; break

    pnl=cash-entry
    return {'signal_time':pd.Timestamp(d.index[sp]),'entry_time':pd.Timestamp(d.index[ep]),'exit_time':pd.Timestamp(d.index[xp]),'entry':entry,'risk':risk,'realized_r':pnl/risk,'mfe_r':(maxhigh-entry)/risk,'mae_r':(minlow-entry)/risk,'tp1_hit':h1,'tp2_hit':h2,'tp3_hit':h3,'exit_reason':reason,'exit_pos':xp}


def collect(frames,entry_name,p,family,period,start,end):
    out=[]
    for sym,d,pbe in frames:
        last=-1
        for sp in pbe.get(entry_name,[]):
            st=pd.Timestamp(d.index[sp])
            if st<start: continue
            if st>=end: break
            if sp<=last: continue
            t=simulate(d,sp,p,family,period)
            if t is None: continue
            if pd.Timestamp(t['exit_time'])>=end: continue
            t['symbol']=sym; out.append(t); last=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']); return out


def evaluate(frames,entry_name,p,family,period,b):
    folds=[]; stitched=[]
    for fi in range(4):
        tr=collect(frames,entry_name,p,family,period,b[fi],b[fi+1]); stitched.extend(tr); folds.append({'fold':fi+1,'metrics':metrics(tr)})
    sm=metrics(stitched); ex=[float(x['metrics'].get('expectancy_r',0)) for x in folds]
    return {'family':family,'profile':dict(p),'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':float(min(ex)),'median_fold_expectancy_r':float(np.median(ex))}


def score(r):
    m=r['stitched']; return (r['positive_folds'],r['worst_fold_expectancy_r'],r['median_fold_expectancy_r'],float(m.get('expectancy_r',0)),float(m.get('profit_factor') or 0))


def narrow_profiles(period,base):
    swings={'4H':[5,7,9],'1D':[5,7,9],'1W':[7,9,11]}[period]
    bufs={'4H':[.15,.20,.25],'1D':[.15,.20,.25],'1W':[.10,.15,.20]}[period]
    trails={'4H':[1.8,2.0,2.2],'1D':[2.0,2.2,2.4],'1W':[2.1,2.3,2.5]}[period]
    rows=[]
    for s in swings:
        for buf in bufs:
            for tr in trails:
                p=dict(base); p.update(swing=s,buffer=buf,trail=tr,tight=max(1.2,tr-.6)); rows.append(p)
    return rows


def analyze(db: str, candidate: str):
    period,entry=CANDIDATES[candidate]; frames,times,count=load_frames(db,period,entry); b=bounds_for(times)
    if not b: return {'candidate':candidate,'classification':'INSUFFICIENT_SAMPLE','signal_count':count}
    base=dict(BASE[period])
    fam=[evaluate(frames,entry,base,f,period,b) for f in families(period)]; fam.sort(key=score,reverse=True); chosen=fam[0]['family']
    geom=[evaluate(frames,entry,p,chosen,period,b) for p in narrow_profiles(period,base)]; geom.sort(key=score,reverse=True); g=geom[0]
    p0=dict(g['profile']); stage3=[]
    holds=sorted(set([int(base['max_hold']),int(base['max_hold']+20)]))
    for targets in [(1.,2.,3.),(1.1,2.2,3.3)]:
        for h in holds:
            p=dict(p0); p.update(tp1=targets[0],tp2=targets[1],tp3=targets[2],max_hold=h); stage3.append(evaluate(frames,entry,p,chosen,period,b))
    stage3.sort(key=score,reverse=True); opt=stage3[0]
    baseline=next(x for x in fam if x['family']=='structural')
    be=float(baseline['stitched'].get('expectancy_r',0)); oe=float(opt['stitched'].get('expectancy_r',0)); bw=baseline['worst_fold_expectancy_r']; ow=opt['worst_fold_expectancy_r']
    material=(opt['positive_folds']>=baseline['positive_folds'] and ((oe-be)>=.03 or (ow-bw)>=.025))
    final=opt if material else baseline
    return {'version':'bulut-keser-sat-robustness-v1','candidate':candidate,'period':period,'entry_frozen':entry,'signal_count':count,'family_stage':fam,'chosen_family_for_search':chosen,'geometry_top5':geom[:5],'stage3':stage3,'baseline_structural':baseline,'optimized_candidate':opt,'material_change_accepted':material,'final':final,'warning':'Observed historical data; future unseen bars are true forward validation.'}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--candidate',choices=tuple(CANDIDATES),required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    result=analyze(a.db,a.candidate); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__': main()
