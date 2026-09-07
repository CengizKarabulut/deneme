"""TP1 break-even A/B for final TavanTarama candidates."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import numpy as np,pandas as pd
_H=Path(__file__).resolve().parent;_B=_H.parents[0]/'bb_squeeze';sys.path[:0]=[str(_H),str(_B)]
from tavan_sat_robustness import load_frames
from bb_squeeze_entry_stage import initial_stop,metrics,bounds_for,COMMISSION_BPS,SLIPPAGE_BPS
FINAL={
'4H_orig':('4H','orig_pdi_cross_adx__rsi50_70__stoch_confirm__rv12','adx_tighten',dict(stop_mode='swing',stop_atr=1.2,swing=9,buffer=.25,trail=1.8,tight=1.3,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3)),
'1D':('1D','orig_pdi_cross_adx__rsi50_70__stoch_cross__rv15','adx_tighten',dict(stop_mode='swing',stop_atr=1.25,swing=9,buffer=.25,trail=2.0,tight=1.5,max_hold=40,tp1=1.1,tp2=2.2,tp3=3.3)),
'1W':('1W','orig_pdi_cross_adx__rsi40_70__stoch_confirm__rv15','structural',dict(stop_mode='swing',stop_atr=1.3,swing=11,buffer=.15,trail=2.1,tight=1.6,max_hold=80,tp1=1.1,tp2=2.2,tp3=3.3))}
def bep(e,m):
 if m=='entry':return e
 if m=='cost':
  c=COMMISSION_BPS/10000.;s=SLIPPAGE_BPS/10000.;return e*(1+s)*(1+c)/((1-s)*(1-c))
def sim(d,sp,p,fam,mode):
 ep=sp+1
 if ep>=len(d):return None
 e=float(d.open.iloc[ep])
 if not np.isfinite(e) or e<=0:return None
 st,r=initial_stop(d,sp,e,p);t1=e+r*p['tp1'];t2=e+r*p['tp2'];t3=e+r*p['tp3'];bp=bep(e,mode)
 rem=1.;cash=0.;h1=h2=h3=tr=tight=False;high=e;lo0=e;hi0=e;why='TIME';xp=ep;last=min(len(d)-1,ep+int(p['max_hold'])-1)
 for pos in range(ep,last+1):
  row=d.iloc[pos];hi=float(row.high);lo=float(row.low);cl=float(row.close);high=max(high,hi);hi0=max(hi0,hi);lo0=min(lo0,lo)
  if lo<=st:cash+=rem*st;rem=0.;why='TRAIL' if tr or tight or(h1 and mode!='none') else 'STOP';xp=pos;break
  if not h1 and hi>=t1:
   q=min(rem,.3);cash+=q*t1;rem-=q;h1=True
   if mode!='none':st=max(st,bp)
  if rem>1e-12 and not h2 and hi>=t2:q=min(rem,.3);cash+=q*t2;rem-=q;h2=True;tr=True
  if rem>1e-12 and not h3 and hi>=t3:q=min(rem,.2);cash+=q*t3;rem-=q;h3=True
  if fam=='adx_tighten' and pos>=2:
   a=float(row.adx14);a1=float(d.adx14.iloc[pos-1]);a2=float(d.adx14.iloc[pos-2]);tight=tight or (np.isfinite(a) and np.isfinite(a1) and np.isfinite(a2) and a<a1<a2)
  if rem>1e-12 and(tr or tight):
   a=float(row.atr14)
   if np.isfinite(a) and a>0:st=max(st,high-float(p['tight'] if tight else p['trail'])*a)
  if pos==last and rem>1e-12:cash+=rem*cl;rem=0.;why='TIME';xp=pos;break
 return dict(signal_time=pd.Timestamp(d.index[sp]),entry_time=pd.Timestamp(d.index[ep]),exit_time=pd.Timestamp(d.index[xp]),entry=e,risk=r,realized_r=(cash-e)/r,mfe_r=(hi0-e)/r,mae_r=(lo0-e)/r,tp1_hit=h1,tp2_hit=h2,tp3_hit=h3,exit_reason=why,exit_pos=xp)
def collect(frames,n,p,fam,a,b,mode):
 out=[]
 for sym,d,pbe in frames:
  last=-1
  for sp in pbe.get(n,[]):
   ts=pd.Timestamp(d.index[sp])
   if ts<a:continue
   if ts>=b:break
   if sp<=last:continue
   t=sim(d,sp,p,fam,mode)
   if t is None or pd.Timestamp(t['exit_time'])>=b:continue
   t['symbol']=sym;out.append(t);last=int(t['exit_pos'])
 out.sort(key=lambda x:x['entry_time']);return out
def ev(frames,n,p,fam,b,mode):
 fs=[];all=[]
 for i in range(4):
  tr=collect(frames,n,p,fam,b[i],b[i+1],mode);all+=tr;fs.append({'fold':i+1,'metrics':metrics(tr)})
 sm=metrics(all);ex=[float(x['metrics'].get('expectancy_r',0)) for x in fs];return {'mode':mode,'folds':fs,'stitched':sm,'positive_folds':sum(x>0 for x in ex),'worst_fold_expectancy_r':min(ex)}
def analyze(db,c):
 per,n,fam,p=FINAL[c];fr,times,count=load_frames(db,per,n);b=bounds_for(times);rows=[ev(fr,n,p,fam,b,m) for m in('none','entry','cost')];ne=float(rows[0]['stitched'].get('expectancy_r',0));best=max(rows,key=lambda x:(x['positive_folds'],x['worst_fold_expectancy_r'],float(x['stitched'].get('expectancy_r',0))));be=float(best['stitched'].get('expectancy_r',0));dec='NO_BE' if best['mode']=='none' or be<ne-.005 else 'USE_'+best['mode'].upper()+'_BE';return {'version':'tavan-be-ab-v1','candidate':c,'period':per,'entry_frozen':n,'family':fam,'profile':p,'signal_count':count,'rows':rows,'decision':dec}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--candidate',choices=FINAL,required=True);ap.add_argument('--output',required=True);a=ap.parse_args();d=analyze(a.db,a.candidate);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
