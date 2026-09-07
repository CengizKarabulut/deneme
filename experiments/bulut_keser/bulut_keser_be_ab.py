"""TP1 break-even A/B for BulutKeser final candidates."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from bulut_keser_sat_robustness import load_frames
from bulut_keser_cloud_stage import initial_stop,metrics,bounds_for
from bb_squeeze_entry_stage import COMMISSION_BPS,SLIPPAGE_BPS

FINAL={
 '4H':('4H','inside__adx_gt20__bb_inside__rv12','ichi_tighten',dict(stop_mode='swing',stop_atr=1.2,swing=9,buffer=.25,trail=1.8,tight=1.2,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3)),
 '1D':('1D','below__adx_20_35__bb_positive_half__rv15','structural',dict(stop_mode='swing',stop_atr=1.25,swing=9,buffer=.20,trail=2.0,tight=1.4,max_hold=40,tp1=1.1,tp2=2.2,tp3=3.3)),
 '1W':('1W','above__adx_20_35__bb_none__rv15','structural',dict(stop_mode='swing',stop_atr=1.3,swing=9,buffer=.15,trail=2.3,tight=1.7,max_hold=60,tp1=1.,tp2=2.,tp3=3.)),
}

def bep(e,mode):
    if mode=='entry': return e
    if mode=='cost':
        c=COMMISSION_BPS/10000.;s=SLIPPAGE_BPS/10000.
        return e*(1+s)*(1+c)/((1-s)*(1-c))
    return None

def sim(d,sp,p,fam,period,mode):
    ep=sp+1
    if ep>=len(d):return None
    e=float(d['open'].iloc[ep])
    if not np.isfinite(e) or e<=0:return None
    st,r=initial_stop(d,sp,e,p);t1=e+r*p['tp1'];t2=e+r*p['tp2'];t3=e+r*p['tp3'];bp=bep(e,mode)
    rem=1.;cash=0.;h1=h2=h3=False;tr=False;tight=False;high=e;lo0=e;hi0=e;why='TIME';xp=ep;last=min(len(d)-1,ep+int(p['max_hold'])-1)
    for pos in range(ep,last+1):
        row=d.iloc[pos];hi=float(row['high']);lo=float(row['low']);cl=float(row['close']);high=max(high,hi);hi0=max(hi0,hi);lo0=min(lo0,lo)
        if lo<=st:
            cash+=rem*st;rem=0.;why='TRAIL' if tr or tight or(h1 and mode!='none') else 'STOP';xp=pos;break
        if not h1 and hi>=t1:
            q=min(rem,.3);cash+=q*t1;rem-=q;h1=True
            if mode!='none':st=max(st,float(bp))
        if rem>1e-12 and not h2 and hi>=t2:q=min(rem,.3);cash+=q*t2;rem-=q;h2=True;tr=True
        if rem>1e-12 and not h3 and hi>=t3:q=min(rem,.2);cash+=q*t3;rem-=q;h3=True
        if fam=='ichi_tighten':
            kij=float(row['kijun']) if pd.notna(row['kijun']) else np.nan;top=float(row['cloud_top']) if pd.notna(row['cloud_top']) else np.nan
            kij_loss=np.isfinite(kij) and cl<kij; cloud_top_loss=np.isfinite(top) and cl<top
            tight=tight or kij_loss or (period=='1W' and cloud_top_loss)
        if rem>1e-12 and(tr or tight):
            a=float(row['atr14'])
            if np.isfinite(a) and a>0:st=max(st,high-float(p['tight'] if tight else p['trail'])*a)
        if pos==last and rem>1e-12:cash+=rem*cl;rem=0.;why='TIME';xp=pos;break
    return dict(signal_time=pd.Timestamp(d.index[sp]),entry_time=pd.Timestamp(d.index[ep]),exit_time=pd.Timestamp(d.index[xp]),entry=e,risk=r,realized_r=(cash-e)/r,mfe_r=(hi0-e)/r,mae_r=(lo0-e)/r,tp1_hit=h1,tp2_hit=h2,tp3_hit=h3,exit_reason=why,exit_pos=xp)

def collect(frames,n,p,fam,period,a,b,mode):
    out=[]
    for sym,d,pbe in frames:
        last=-1
        for sp in pbe.get(n,[]):
            ts=pd.Timestamp(d.index[sp])
            if ts<a:continue
            if ts>=b:break
            if sp<=last:continue
            t=sim(d,sp,p,fam,period,mode)
            if t is None or pd.Timestamp(t['exit_time'])>=b:continue
            t['symbol']=sym;out.append(t);last=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']);return out

def ev(frames,n,p,fam,period,b,mode):
    fs=[];alltr=[]
    for i in range(4):
        tr=collect(frames,n,p,fam,period,b[i],b[i+1],mode);alltr+=tr;fs.append({'fold':i+1,'metrics':metrics(tr)})
    sm=metrics(alltr);ex=[float(x['metrics'].get('expectancy_r',0)) for x in fs]
    return {'mode':mode,'folds':fs,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':float(min(ex))}

def analyze(db,c):
    per,n,fam,p=FINAL[c];fr,times,count=load_frames(db,per,n);b=bounds_for(times);rows=[ev(fr,n,p,fam,per,b,m) for m in('none','entry','cost')]
    no=rows[0];ne=float(no['stitched'].get('expectancy_r',0));best=max(rows,key=lambda x:(x['positive_folds'],x['worst_fold_expectancy_r'],float(x['stitched'].get('expectancy_r',0))));be=float(best['stitched'].get('expectancy_r',0));dec='NO_BE' if best['mode']=='none' or be<ne-.005 else 'USE_'+best['mode'].upper()+'_BE'
    return {'version':'bulut-keser-be-ab-v1','candidate':c,'period':per,'entry_frozen':n,'family':fam,'profile':p,'signal_count':count,'rows':rows,'decision':dec}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--candidate',choices=FINAL,required=True);ap.add_argument('--output',required=True);a=ap.parse_args();d=analyze(a.db,a.candidate);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
