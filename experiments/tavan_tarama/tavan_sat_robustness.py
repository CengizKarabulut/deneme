"""SAT robustness for frozen TavanTarama entries.

4H tests BOTH DMI trigger families. 1D/1W use the stronger original +DI-cross-ADX family.
Stage 1 compares exit families at baseline geometry.
Stage 2 searches a narrow structural/trailing neighborhood for the selected family.
Stage 3 tests small target/max-hold alternatives. Material-gate prevents cosmetic retuning.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

_HERE=Path(__file__).resolve().parent
_BB=_HERE.parents[0]/'bb_squeeze'
sys.path.insert(0,str(_HERE)); sys.path.insert(0,str(_BB))
from tavan_entry_stage import indicators, entry_variants, entry_events  # noqa:E402
from bb_squeeze_entry_stage import MarketDataStore, WARMUP, initial_stop, metrics, bounds_for  # noqa:E402

CANDIDATES={
 '4H_orig':('4H','orig_pdi_cross_adx__rsi50_70__stoch_confirm__rv12'),
 '4H_alt':('4H','alt_pdi_cross_mdi_adx_rise__rsi50_70__stoch_cross__rv15'),
 '1D':('1D','orig_pdi_cross_adx__rsi50_70__stoch_cross__rv15'),
 '1W':('1W','orig_pdi_cross_adx__rsi40_70__stoch_confirm__rv15'),
}

BASE={
 '4H':dict(stop_mode='swing',stop_atr=1.2,swing=7,buffer=.20,trail=2.0,tight=1.5,max_hold=40,tp1=1.,tp2=2.,tp3=3.),
 '1D':dict(stop_mode='swing',stop_atr=1.25,swing=7,buffer=.20,trail=2.2,tight=1.65,max_hold=40,tp1=1.,tp2=2.,tp3=3.),
 '1W':dict(stop_mode='swing',stop_atr=1.3,swing=9,buffer=.15,trail=2.3,tight=1.75,max_hold=60,tp1=1.,tp2=2.,tp3=3.),
}
FAMILIES=('structural','pdi_mdi_exit','pdi_adx_exit','adx_tighten','adaptive')


def load_frames(db,period,entry_name):
    ent=next(e for e in entry_variants() if e['name']==entry_name); frames=[]; times=[]; count=0
    with MarketDataStore(db,read_only=True) as store:
        syms=store.list_symbols('BIST',period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22: continue
            d=indicators(fr); ev=entry_events(d,ent); ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
            if ps: frames.append((sym,d,{entry_name:ps})); count+=len(ps); times.extend(pd.Timestamp(d.index[x]) for x in ps)
            if i%100==0 or i==len(syms): print(f'[{period}] {i}/{len(syms)}',flush=True)
    times.sort(); return frames,times,count


def simulate(d,sp,p,family):
    ep=sp+1
    if ep>=len(d): return None
    entry=float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry<=0:return None
    stop,risk=initial_stop(d,sp,entry,p); tp1=entry+risk*p['tp1']; tp2=entry+risk*p['tp2']; tp3=entry+risk*p['tp3']
    rem=1.; cash=0.; h1=h2=h3=False; trail=False; tight=False; highest=entry; minlow=entry; maxhigh=entry; reason='TIME'; xp=ep
    last=min(len(d)-1,ep+int(p['max_hold'])-1)
    for pos in range(ep,last+1):
        row=d.iloc[pos]; hi=float(row['high']); lo=float(row['low']); cl=float(row['close']); highest=max(highest,hi); maxhigh=max(maxhigh,hi); minlow=min(minlow,lo)
        if lo<=stop:
            cash+=rem*stop; rem=0.; reason='TRAIL' if trail or tight else 'STOP'; xp=pos; break
        if not h1 and hi>=tp1: q=min(rem,.30); cash+=q*tp1; rem-=q; h1=True
        if rem>1e-12 and not h2 and hi>=tp2: q=min(rem,.30); cash+=q*tp2; rem-=q; h2=True; trail=True
        if rem>1e-12 and not h3 and hi>=tp3: q=min(rem,.20); cash+=q*tp3; rem-=q; h3=True
        pdi=float(row['plus_di']); mdi=float(row['minus_di']); adx=float(row['adx14'])
        adx1=float(d['adx14'].iloc[pos-1]) if pos>=1 else np.nan; adx2=float(d['adx14'].iloc[pos-2]) if pos>=2 else np.nan
        dmi_loss=np.isfinite(pdi) and np.isfinite(mdi) and pdi<mdi
        pdi_under_adx=np.isfinite(pdi) and np.isfinite(adx) and pdi<adx
        adx_fade=np.isfinite(adx) and np.isfinite(adx1) and np.isfinite(adx2) and adx<adx1<adx2
        hard=False
        if family=='pdi_mdi_exit': hard=dmi_loss
        elif family=='pdi_adx_exit': hard=pdi_under_adx
        elif family=='adx_tighten': tight=tight or adx_fade
        elif family=='adaptive':
            tight=tight or adx_fade
            hard=dmi_loss and adx_fade
        if hard and rem>1e-12:
            cash+=rem*cl; rem=0.; reason='TECH'; xp=pos; break
        if rem>1e-12 and (trail or tight):
            a=float(row['atr14'])
            if np.isfinite(a) and a>0: stop=max(stop,highest-float(p['tight'] if tight else p['trail'])*a)
        if pos==last and rem>1e-12:
            cash+=rem*cl; rem=0.; reason='TIME'; xp=pos; break
    pnl=cash-entry
    return {'signal_time':pd.Timestamp(d.index[sp]),'entry_time':pd.Timestamp(d.index[ep]),'exit_time':pd.Timestamp(d.index[xp]),'entry':entry,'risk':risk,'realized_r':pnl/risk,'mfe_r':(maxhigh-entry)/risk,'mae_r':(minlow-entry)/risk,'tp1_hit':h1,'tp2_hit':h2,'tp3_hit':h3,'exit_reason':reason,'exit_pos':xp}


def collect(frames,entry_name,p,family,start,end):
    out=[]
    for sym,d,pbe in frames:
        last=-1
        for sp in pbe.get(entry_name,[]):
            st=pd.Timestamp(d.index[sp])
            if st<start:continue
            if st>=end:break
            if sp<=last:continue
            t=simulate(d,sp,p,family)
            if t is None:continue
            if pd.Timestamp(t['exit_time'])>=end:continue
            t['symbol']=sym;out.append(t);last=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']);return out


def evaluate(frames,entry_name,p,family,b):
    folds=[]; stitched=[]
    for fi in range(4):
        tr=collect(frames,entry_name,p,family,b[fi],b[fi+1]); stitched.extend(tr); folds.append({'fold':fi+1,'metrics':metrics(tr)})
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
        for b in bufs:
            for tr in trails:
                p=dict(base);p.update(swing=s,buffer=b,trail=tr,tight=max(1.2,tr-.5));rows.append(p)
    return rows


def analyze(db,candidate):
    period,entry=CANDIDATES[candidate]; frames,times,count=load_frames(db,period,entry); b=bounds_for(times)
    if not b:return {'candidate':candidate,'classification':'INSUFFICIENT_SAMPLE','signal_count':count}
    base=dict(BASE[period])
    fam=[evaluate(frames,entry,base,f,b) for f in FAMILIES]; fam.sort(key=score,reverse=True); chosen=fam[0]['family']
    geom=[evaluate(frames,entry,p,chosen,b) for p in narrow_profiles(period,base)]; geom.sort(key=score,reverse=True); g=geom[0]
    # small target/holding neighborhood around best geometry
    p0=dict(g['profile']); stage3=[]
    holds=sorted(set([int(base['max_hold']), int(base['max_hold']+20)]))
    for targets in [(1.,2.,3.),(1.1,2.2,3.3)]:
        for h in holds:
            p=dict(p0);p.update(tp1=targets[0],tp2=targets[1],tp3=targets[2],max_hold=h);stage3.append(evaluate(frames,entry,p,chosen,b))
    stage3.sort(key=score,reverse=True); opt=stage3[0]
    baseline=next(x for x in fam if x['family']=='structural')
    # Compare optimized result against baseline structural. Accept complexity only for material/stable improvement.
    be=float(baseline['stitched'].get('expectancy_r',0)); oe=float(opt['stitched'].get('expectancy_r',0)); bw=baseline['worst_fold_expectancy_r']; ow=opt['worst_fold_expectancy_r']
    material=(opt['positive_folds']>=baseline['positive_folds'] and ((oe-be)>=.03 or (ow-bw)>=.025))
    final=opt if material else baseline
    return {'version':'tavan-sat-robustness-v1','candidate':candidate,'period':period,'entry_frozen':entry,'signal_count':count,'family_stage':fam,'chosen_family_for_search':chosen,'geometry_top5':geom[:5],'stage3':stage3,'baseline_structural':baseline,'optimized_candidate':opt,'material_change_accepted':material,'final':final,'warning':'Observed historical data; future unseen bars are true forward validation.'}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--candidate',choices=tuple(CANDIDATES),required=True);ap.add_argument('--output',required=True);a=ap.parse_args();d=analyze(a.db,a.candidate);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
