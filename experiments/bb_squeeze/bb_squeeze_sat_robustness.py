"""SAT family + narrow robustness for frozen BB squeeze entries."""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from bb_squeeze_entry_stage import (MarketDataStore,WARMUP,BOUNDARIES,indicators,entry_variants,entry_events,initial_stop,net_r,metrics)

PERIODS=('4H','1D','1W','1M')
ENTRY={'4H':'relative20__cross','1D':'abs10__hist_rise2','1W':'release20__hist_rise2','1M':'release20__hist_rise2'}

def base_structure(period):
    return {
      '4H':dict(stop_mode='swing',stop_atr=1.20,swing=7,buffer=.20,trail=2.00,tight=1.50,max_hold=40),
      '1D':dict(stop_mode='swing',stop_atr=1.25,swing=7,buffer=.20,trail=2.20,tight=1.65,max_hold=40),
      '1W':dict(stop_mode='swing',stop_atr=1.30,swing=9,buffer=.15,trail=2.30,tight=1.75,max_hold=60),
      '1M':dict(stop_mode='swing',stop_atr=1.30,swing=9,buffer=.15,trail=2.50,tight=1.90,max_hold=36),
    }[period].copy()

def exit_families(period):
    b=base_structure(period); rows=[]
    for name,rule in [('structural','none'),('basis_loss','basis_loss'),('basis_loss_2bar','basis_loss_2bar'),('macd_bear','macd_bear'),('basis_and_macd','basis_and_macd'),('adaptive','adaptive')]:
        p=dict(b);p.update({'name':name,'rule':rule,'tp1':1.0,'tp2':2.0,'tp3':3.0});rows.append(p)
    return rows

def load_frames(db,period,entry_name):
    e=next(x for x in entry_variants() if x['name']==entry_name);frames=[];times=[];count=0
    with MarketDataStore(db,read_only=True) as store:
        syms=store.list_symbols('BIST',period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22:continue
            d=indicators(fr);ev=entry_events(d,e);ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
            if ps:frames.append((sym,d,{entry_name:ps}));count+=len(ps);times.extend(pd.Timestamp(d.index[x]) for x in ps)
            if i%100==0 or i==len(syms):print(f'[{period}] {i}/{len(syms)}',flush=True)
    times.sort();return frames,times,count

def bounds_for(times):
    if len(times)<80:return []
    b=[pd.Timestamp(times[min(len(times)-1,int(len(times)*q))]) for q in BOUNDARIES[:-1]];b.append(pd.Timestamp(times[-1])+pd.Timedelta(days=3700));return b

def simulate(d,sp,p):
    ep=sp+1
    if ep>=len(d):return None
    entry=float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry<=0:return None
    stop,risk=initial_stop(d,sp,entry,p);tp1=entry+risk*float(p['tp1']);tp2=entry+risk*float(p['tp2']);tp3=entry+risk*float(p['tp3'])
    rem=1.0;cash=0.0;h1=h2=h3=False;trail=False;tight=False;highest=entry;minlow=entry;maxhigh=entry;reason='TIME';xp=ep
    last=min(len(d)-1,ep+int(p['max_hold'])-1)
    for pos in range(ep,last+1):
        row=d.iloc[pos];hi=float(row['high']);lo=float(row['low']);cl=float(row['close']);highest=max(highest,hi);maxhigh=max(maxhigh,hi);minlow=min(minlow,lo)
        if lo<=stop:
            cash+=rem*stop;rem=0;reason='TRAIL' if trail or tight else 'STOP';xp=pos;break
        if not h1 and hi>=tp1:q=min(rem,.30);cash+=q*tp1;rem-=q;h1=True
        if rem>1e-12 and not h2 and hi>=tp2:q=min(rem,.30);cash+=q*tp2;rem-=q;h2=True;trail=True
        if rem>1e-12 and not h3 and hi>=tp3:q=min(rem,.20);cash+=q*tp3;rem-=q;h3=True
        basis=float(row['bb_basis']) if np.isfinite(row['bb_basis']) else np.nan
        below=np.isfinite(basis) and cl<basis
        prev_below=False
        if pos>0:
            pc=float(d['close'].iloc[pos-1]);pb=float(d['bb_basis'].iloc[pos-1]) if np.isfinite(d['bb_basis'].iloc[pos-1]) else np.nan;prev_below=np.isfinite(pb) and pc<pb
        macd_bear=bool(row['macd_cross_down']); macd_under=float(row['macd'])<float(row['macd_signal']) if np.isfinite(row['macd']) and np.isfinite(row['macd_signal']) else False
        rule=p['rule'];full=False
        if rule=='basis_loss':full=below
        elif rule=='basis_loss_2bar':full=below and prev_below
        elif rule=='macd_bear':full=macd_bear
        elif rule=='basis_and_macd':full=below and macd_under
        elif rule=='adaptive':
            if below:tight=True
            full=below and macd_under
        if full and rem>1e-12:
            cash+=rem*cl;rem=0;reason='TECH';xp=pos;break
        if rem>1e-12 and (trail or tight):
            a=float(row['atr14'])
            if np.isfinite(a) and a>0:stop=max(stop,highest-float(p['tight'] if tight else p['trail'])*a)
        if pos==last and rem>1e-12:cash+=rem*cl;rem=0;reason='TIME';xp=pos;break
    pnl=cash-entry
    return {'signal_time':pd.Timestamp(d.index[sp]),'entry_time':pd.Timestamp(d.index[ep]),'exit_time':pd.Timestamp(d.index[xp]),'entry':entry,'risk':risk,'realized_r':pnl/risk,'mfe_r':(maxhigh-entry)/risk,'mae_r':(minlow-entry)/risk,'tp1_hit':h1,'tp2_hit':h2,'tp3_hit':h3,'exit_reason':reason,'exit_pos':xp}

def collect(frames,entry,p,start,end):
    out=[]
    for sym,d,pbe in frames:
        last=-1
        for sp in pbe.get(entry,[]):
            st=pd.Timestamp(d.index[sp])
            if st<start:continue
            if st>=end:break
            if sp<=last:continue
            t=simulate(d,sp,p)
            if t is None:continue
            if pd.Timestamp(t['exit_time'])>=end:continue
            t['symbol']=sym;out.append(t);last=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']);return out

def evaluate(frames,entry,p,bounds):
    folds=[];stitched=[]
    for fi in range(4):
        tr=collect(frames,entry,p,bounds[fi],bounds[fi+1]);stitched.extend(tr);folds.append({'fold':fi+1,'metrics':metrics(tr)})
    sm=metrics(stitched);ex=[float(f['metrics'].get('expectancy_r',0)) for f in folds]
    return {'params':{k:p.get(k) for k in ('name','rule','swing','buffer','trail','tight','max_hold','tp1','tp2','tp3')},'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':float(min(ex)),'median_fold_expectancy_r':float(np.median(ex))}

def rank(rows):
    return sorted(rows,key=lambda r:(r['positive_folds'],r['worst_fold_expectancy_r'],r['median_fold_expectancy_r'],float(r['stitched'].get('expectancy_r',0)),float(r['stitched'].get('profit_factor') or 0)),reverse=True)

def plateau_pick(rows,keys):
    rr=rank(rows);eligible=[r for r in rr if r['positive_folds']==4 and r['worst_fold_expectancy_r']>0];pool=eligible or rr;n=max(3,min(9,int(math.ceil(len(pool)*.25))));top=pool[:n]
    centers={k:float(np.median([float(r['params'][k]) for r in top])) for k in keys};scales={}
    for k in keys:
        u=sorted(set(float(r['params'][k]) for r in rows));ds=[b-a for a,b in zip(u[:-1],u[1:]) if b>a];scales[k]=float(np.median(ds)) if ds else 1.0
    def dist(r):return sum(abs(float(r['params'][k])-centers[k])/max(scales[k],1e-9) for k in keys)
    return sorted(top,key=lambda r:(dist(r),-r['worst_fold_expectancy_r'],-r['median_fold_expectancy_r'],-float(r['stitched'].get('expectancy_r',0))))[0],centers,top

def analyze(db,period):
    entry=ENTRY[period];frames,times,count=load_frames(db,period,entry);bounds=bounds_for(times)
    if not bounds:return {'period':period,'classification':'INSUFFICIENT_SAMPLE','signal_count':count}
    fam=[evaluate(frames,entry,p,bounds) for p in exit_families(period)];bestfam=rank(fam)[0];base=next(p for p in exit_families(period) if p['name']==bestfam['params']['name'])
    swings=sorted(set([max(3,int(base['swing'])-2),int(base['swing']),int(base['swing'])+2]));buffers=sorted(set([round(max(0,float(base['buffer'])-.05),2),round(float(base['buffer']),2),round(float(base['buffer'])+.05,2)]));trails=sorted(set([round(max(.8,float(base['trail'])-.2),2),round(float(base['trail']),2),round(float(base['trail'])+.2,2)]))
    geom=[]
    for sw in swings:
      for bu in buffers:
       for tr in trails:
        p=dict(base);p.update({'swing':sw,'buffer':bu,'trail':tr});geom.append(evaluate(frames,entry,p,bounds))
    gp,gc,gt=plateau_pick(geom,('swing','buffer','trail'));chosen=gp['params']
    tight_rows=[]
    if base['rule']=='adaptive':
        for ti in sorted(set([round(max(.7,float(base['tight'])-.15),2),round(float(base['tight']),2),round(float(base['tight'])+.15,2)])):
            p=dict(base);p.update({'swing':int(chosen['swing']),'buffer':float(chosen['buffer']),'trail':float(chosen['trail']),'tight':ti});tight_rows.append(evaluate(frames,entry,p,bounds))
        tp,_,_=plateau_pick(tight_rows,('tight',));chosen=tp['params']
    holds=sorted(set([max(8,int(round(base['max_hold']*.8))),int(base['max_hold']),int(round(base['max_hold']*1.2))]));stage=[]
    for tps in ((.9,1.8,2.7),(1.,2.,3.),(1.1,2.2,3.3)):
      for hold in holds:
        p=dict(base);p.update({'swing':int(chosen['swing']),'buffer':float(chosen['buffer']),'trail':float(chosen['trail']),'tight':float(chosen['tight']),'max_hold':hold,'tp1':tps[0],'tp2':tps[1],'tp3':tps[2]});stage.append(evaluate(frames,entry,p,bounds))
    final,bc,bt=plateau_pick(stage,('tp1','tp2','tp3','max_hold'))
    return {'version':'bb-squeeze-sat-robustness-v1','period':period,'entry_frozen':entry,'signal_count':count,'exit_family_rows':rank(fam),'selected_exit_family':bestfam,'geometry':{'chosen':gp,'center':gc,'top':gt},'tight_rows':tight_rows,'tp_hold':{'chosen':final,'center':bc,'top':bt},'final_profile':final,'warning':'Observed historical data; future unseen bars are true forward validation.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--period',choices=PERIODS,required=True);ap.add_argument('--output',required=True);a=ap.parse_args();d=analyze(a.db,a.period);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
