"""TP1 break-even A/B for final BB squeeze profiles."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from bb_squeeze_entry_stage import MarketDataStore,WARMUP,COMMISSION_BPS,SLIPPAGE_BPS,indicators,entry_variants,entry_events,initial_stop,net_r,metrics
from bb_squeeze_sat_robustness import bounds_for

PERIODS=('4H','1D','1W','1M')
ENTRY={'4H':'relative20__cross','1D':'abs10__hist_rise2','1W':'release20__hist_rise2','1M':'release20__hist_rise2'}
FINAL={
 '4H':dict(name='adaptive',rule='adaptive',stop_mode='swing',stop_atr=1.2,swing=9,buffer=.25,trail=1.8,tight=1.5,max_hold=40,tp1=1.,tp2=2.,tp3=3.),
 '1D':dict(name='structural',rule='none',stop_mode='swing',stop_atr=1.25,swing=7,buffer=.25,trail=2.2,tight=1.65,max_hold=40,tp1=1.1,tp2=2.2,tp3=3.3),
 '1W':dict(name='structural',rule='none',stop_mode='swing',stop_atr=1.3,swing=9,buffer=.20,trail=2.3,tight=1.75,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3),
 '1M':dict(name='structural',rule='none',stop_mode='swing',stop_atr=1.3,swing=7,buffer=.15,trail=2.5,tight=1.9,max_hold=36,tp1=.9,tp2=1.8,tp3=2.7),
}

def load_frames(db,period):
    en=ENTRY[period];e=next(x for x in entry_variants() if x['name']==en);frames=[];times=[];count=0
    with MarketDataStore(db,read_only=True) as store:
        syms=store.list_symbols('BIST',period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22:continue
            d=indicators(fr);ev=entry_events(d,e);ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
            if ps:frames.append((sym,d,{en:ps}));count+=len(ps);times.extend(pd.Timestamp(d.index[x]) for x in ps)
            if i%100==0 or i==len(syms):print(f'[{period}] {i}/{len(syms)}',flush=True)
    times.sort();return frames,times,count

def be_price(entry,mode):
    if mode=='entry':return entry
    if mode=='cost':
        c=COMMISSION_BPS/10000.0;s=SLIPPAGE_BPS/10000.0
        return entry*(1+s)*(1+c)/((1-s)*(1-c))
    return None

def simulate(d,sp,p,mode):
    ep=sp+1
    if ep>=len(d):return None
    entry=float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry<=0:return None
    stop,risk=initial_stop(d,sp,entry,p);tp1=entry+risk*p['tp1'];tp2=entry+risk*p['tp2'];tp3=entry+risk*p['tp3'];bp=be_price(entry,mode)
    rem=1.;cash=0.;h1=h2=h3=False;trail=False;tight=False;highest=entry;minlow=entry;maxhigh=entry;reason='TIME';xp=ep
    last=min(len(d)-1,ep+int(p['max_hold'])-1)
    for pos in range(ep,last+1):
        row=d.iloc[pos];hi=float(row['high']);lo=float(row['low']);cl=float(row['close']);highest=max(highest,hi);maxhigh=max(maxhigh,hi);minlow=min(minlow,lo)
        if lo<=stop:
            cash+=rem*stop;rem=0.;reason='TRAIL' if trail or tight or (h1 and mode!='none') else 'STOP';xp=pos;break
        if not h1 and hi>=tp1:
            q=min(rem,.30);cash+=q*tp1;rem-=q;h1=True
            if mode!='none' and bp is not None:stop=max(stop,bp)
        if rem>1e-12 and not h2 and hi>=tp2:q=min(rem,.30);cash+=q*tp2;rem-=q;h2=True;trail=True
        if rem>1e-12 and not h3 and hi>=tp3:q=min(rem,.20);cash+=q*tp3;rem-=q;h3=True
        basis=float(row['bb_basis']) if np.isfinite(row['bb_basis']) else np.nan;below=np.isfinite(basis) and cl<basis
        macd_under=float(row['macd'])<float(row['macd_signal']) if np.isfinite(row['macd']) and np.isfinite(row['macd_signal']) else False
        if p['rule']=='adaptive':
            if below:tight=True
            if below and macd_under and rem>1e-12:cash+=rem*cl;rem=0.;reason='TECH';xp=pos;break
        if rem>1e-12 and (trail or tight):
            a=float(row['atr14'])
            if np.isfinite(a) and a>0:stop=max(stop,highest-float(p['tight'] if tight else p['trail'])*a)
        if pos==last and rem>1e-12:cash+=rem*cl;rem=0.;reason='TIME';xp=pos;break
    pnl=cash-entry
    return {'signal_time':pd.Timestamp(d.index[sp]),'entry_time':pd.Timestamp(d.index[ep]),'exit_time':pd.Timestamp(d.index[xp]),'entry':entry,'risk':risk,'realized_r':pnl/risk,'mfe_r':(maxhigh-entry)/risk,'mae_r':(minlow-entry)/risk,'tp1_hit':h1,'tp2_hit':h2,'tp3_hit':h3,'exit_reason':reason,'exit_pos':xp}

def collect(frames,p,start,end,mode,entry_name):
    out=[]
    for sym,d,pbe in frames:
        last=-1
        for sp in pbe.get(entry_name,[]):
            st=pd.Timestamp(d.index[sp])
            if st<start:continue
            if st>=end:break
            if sp<=last:continue
            t=simulate(d,sp,p,mode)
            if t is None:continue
            if pd.Timestamp(t['exit_time'])>=end:continue
            t['symbol']=sym;out.append(t);last=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']);return out

def evaluate(frames,p,bounds,mode,entry_name):
    folds=[];stitched=[]
    for fi in range(4):
        tr=collect(frames,p,bounds[fi],bounds[fi+1],mode,entry_name);stitched.extend(tr);folds.append({'fold':fi+1,'metrics':metrics(tr)})
    sm=metrics(stitched);ex=[float(f['metrics'].get('expectancy_r',0)) for f in folds]
    return {'mode':mode,'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':float(min(ex)),'median_fold_expectancy_r':float(np.median(ex))}

def analyze(db,period):
    frames,times,count=load_frames(db,period);bounds=bounds_for(times)
    if not bounds:return {'period':period,'classification':'INSUFFICIENT_SAMPLE','signal_count':count}
    p=dict(FINAL[period]);rows=[evaluate(frames,p,bounds,m,ENTRY[period]) for m in ('none','entry','cost')]
    none=rows[0];best=max(rows,key=lambda r:(r['positive_folds'],r['worst_fold_expectancy_r'],float(r['stitched'].get('expectancy_r',0)),float(r['stitched'].get('profit_factor') or 0)))
    # Preserve total edge: BE is accepted only if it does not reduce expectancy materially.
    none_e=float(none['stitched'].get('expectancy_r',0));best_e=float(best['stitched'].get('expectancy_r',0))
    decision='NO_BE' if best['mode']=='none' or best_e<none_e-.005 else f"USE_{best['mode'].upper()}_BE"
    return {'version':'bb-squeeze-be-ab-v1','period':period,'entry_frozen':ENTRY[period],'profile':p,'signal_count':count,'rows':rows,'decision':decision,'warning':'Observed historical data; future unseen bars are true forward validation.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--period',choices=PERIODS,required=True);ap.add_argument('--output',required=True);a=ap.parse_args();d=analyze(a.db,a.period);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
