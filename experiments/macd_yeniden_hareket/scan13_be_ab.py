"""TP1 break-even A/B for final Scan 13 candidates."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd

from scan13_sat_robustness import load_frames
from bb_squeeze_entry_stage import initial_stop, metrics, bounds_for, COMMISSION_BPS, SLIPPAGE_BPS

ENTRY={
 '4H':{"name":"C_positive_hist_reacceleration","mode":"C"},
 '1D':{"name":"C_positive_hist_reacceleration","mode":"C"},
 '1W':{"name":"A_original_positive_macd_cross","mode":"A"},
 '1M':{"name":"A_original_positive_macd_cross","mode":"A"},
}
FINAL={
 '4H':('macd_tighten',dict(stop_mode='swing',stop_atr=1.2,swing=7,buffer=.20,trail=2.0,max_hold=40,tp1=1.0,tp2=2.0,tp3=3.0,tight=.5)),
 '1D':('macd_tighten',dict(stop_mode='swing',stop_atr=1.25,swing=7,buffer=.20,trail=2.2,max_hold=40,tp1=1.0,tp2=2.0,tp3=3.0,tight=.5)),
 '1W':('structural',dict(stop_mode='swing',stop_atr=1.3,swing=9,buffer=.15,trail=2.3,max_hold=60,tp1=1.0,tp2=2.0,tp3=3.0,tight=1.8)),
 '1M':('structural',dict(stop_mode='swing',stop_atr=1.3,swing=9,buffer=.15,trail=2.5,max_hold=36,tp1=1.0,tp2=2.0,tp3=3.0,tight=2.0)),
}

def bep(entry,mode):
    if mode=='entry': return entry
    if mode=='cost':
        c=COMMISSION_BPS/10000.0; s=SLIPPAGE_BPS/10000.0
        return entry*(1+s)*(1+c)/((1-s)*(1-c))
    return None

def sim(d,sp,p,family,mode):
    ep=sp+1
    if ep>=len(d): return None
    entry=float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry<=0:return None
    stop,risk=initial_stop(d,sp,entry,p)
    t1=entry+risk*p['tp1'];t2=entry+risk*p['tp2'];t3=entry+risk*p['tp3'];bp=bep(entry,mode)
    rem=1.;cash=0.;h1=h2=h3=False;trail=False;tight=False;highest=entry;lo0=entry;hi0=entry;xp=ep;why='TIME'
    last=min(len(d)-1,ep+int(p['max_hold'])-1)
    for pos in range(ep,last+1):
        row=d.iloc[pos];hi=float(row['high']);lo=float(row['low']);cl=float(row['close'])
        highest=max(highest,hi);hi0=max(hi0,hi);lo0=min(lo0,lo)
        if lo<=stop:
            cash+=rem*stop;rem=0.;xp=pos;why='TRAIL' if (trail or tight or (h1 and mode!='none')) else 'STOP';break
        if not h1 and hi>=t1:
            q=min(rem,.30);cash+=q*t1;rem-=q;h1=True
            if mode!='none':stop=max(stop,float(bp))
        if rem>1e-12 and not h2 and hi>=t2:
            q=min(rem,.30);cash+=q*t2;rem-=q;h2=True;trail=True
        if rem>1e-12 and not h3 and hi>=t3:
            q=min(rem,.20);cash+=q*t3;rem-=q;h3=True
        if family=='macd_tighten':
            m=float(row['macd']) if pd.notna(row['macd']) else np.nan
            s=float(row['macd_signal']) if pd.notna(row['macd_signal']) else np.nan
            if np.isfinite(m) and np.isfinite(s) and m<s:tight=True
        if rem>1e-12 and (trail or tight):
            a=float(row['atr14'])
            if np.isfinite(a) and a>0:
                stop=max(stop,highest-float(p['tight'] if tight else p['trail'])*a)
        if pos==last and rem>1e-12:
            cash+=rem*cl;rem=0.;xp=pos;why='TIME';break
    return {'signal_time':pd.Timestamp(d.index[sp]),'entry_time':pd.Timestamp(d.index[ep]),'exit_time':pd.Timestamp(d.index[xp]),'entry':entry,'risk':risk,'realized_r':(cash-entry)/risk,'mfe_r':(hi0-entry)/risk,'mae_r':(lo0-entry)/risk,'tp1_hit':h1,'tp2_hit':h2,'tp3_hit':h3,'exit_reason':why,'exit_pos':xp}

def collect(frames,p,fam,start,end,mode):
    out=[]
    for sym,d,ps in frames:
        last=-1
        for sp in ps:
            ts=pd.Timestamp(d.index[sp])
            if ts<start:continue
            if ts>=end:break
            if sp<=last:continue
            t=sim(d,sp,p,fam,mode)
            if t is None or pd.Timestamp(t['exit_time'])>=end:continue
            t['symbol']=sym;out.append(t);last=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']);return out

def ev(frames,p,fam,b,mode):
    folds=[];alltr=[]
    for i in range(4):
        tr=collect(frames,p,fam,b[i],b[i+1],mode);alltr+=tr;folds.append({'fold':i+1,'metrics':metrics(tr)})
    sm=metrics(alltr);ex=[float(x['metrics'].get('expectancy_r',0)) for x in folds]
    return {'mode':mode,'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':float(min(ex))}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--period',choices=['4H','1D','1W','1M'],required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    fam,p=FINAL[a.period];entry=ENTRY[a.period];frames,times,count=load_frames(a.db,a.period,entry);b=bounds_for(times);rows=[ev(frames,p,fam,b,m) for m in ('none','entry','cost')]
    no=rows[0];ne=float(no['stitched'].get('expectancy_r',0));best=max(rows[1:],key=lambda x:(x['positive_folds'],x['worst_fold_expectancy_r'],float(x['stitched'].get('expectancy_r',0))))
    be=float(best['stitched'].get('expectancy_r',0));decision='NO_BE' if be < ne-0.005 else ('USE_'+best['mode'].upper()+'_BE')
    d={'version':'scan13-be-ab-v2','period':a.period,'entry_frozen':entry,'family':fam,'profile':p,'signal_count':count,'rows':rows,'decision':decision,'note':'Human materiality gate remains authoritative; 1M is research-only.'}
    q=Path(a.output);q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
