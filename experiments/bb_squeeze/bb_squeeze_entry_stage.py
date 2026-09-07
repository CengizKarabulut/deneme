"""BB squeeze entry-quality research.

All entry variants are tested with the SAME structural exit profile per timeframe.
This separates entry quality from exit optimization.

Rules:
- BB(20,2) width = 100*(upper-lower)/basis
- squeeze modes: abs10, abs5, relative20, release20
- MACD modes: fresh bullish crossover or fresh two-bar histogram-rise episode
- MACD level > 0 in every entry
- Volume[t] > mean(previous 10 same-timeframe bars), current bar excluded
- completed bar only, execution reference t+1 open
- 10 bps commission + 10 bps slippage each side
- entry-specific four chronological windows
"""
from __future__ import annotations

import argparse, json, sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SHARED = Path(__file__).resolve().parents[1] / "stoch_rsi_momentum_volume"
sys.path.insert(0, str(_SHARED))
from market_data_store import MarketDataStore  # noqa: E402

PERIODS=("15m","30m","45m","1H","2H","4H","1D","1W","1M")
BOUNDARIES=(0.45,0.60,0.75,0.90,1.00)
COMMISSION_BPS=10.0
SLIPPAGE_BPS=10.0
WARMUP=260


def ema(s:pd.Series,span:int)->pd.Series:
    return s.ewm(span=span,adjust=False,min_periods=span).mean()


def atr(frame:pd.DataFrame,length:int=14)->pd.Series:
    h=pd.to_numeric(frame['high'],errors='coerce'); l=pd.to_numeric(frame['low'],errors='coerce'); c=pd.to_numeric(frame['close'],errors='coerce')
    pc=c.shift(1)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/length,adjust=False,min_periods=length).mean()


def indicators(frame:pd.DataFrame)->pd.DataFrame:
    out=frame.copy()
    c=pd.to_numeric(out['close'],errors='coerce'); v=pd.to_numeric(out['volume'],errors='coerce')
    basis=c.rolling(20,min_periods=20).mean(); sd=c.rolling(20,min_periods=20).std(ddof=0)
    upper=basis+2.0*sd; lower=basis-2.0*sd
    width=100.0*(upper-lower)/basis.replace(0.0,np.nan)
    e12,e26=ema(c,12),ema(c,26); macd=e12-e26; sig=ema(macd,9); hist=macd-sig
    out['bb_basis']=basis; out['bb_upper']=upper; out['bb_lower']=lower; out['bb_width_pct']=width
    # Current width never contributes to its own relative threshold.
    out['bb_width_q20_prev120']=width.shift(1).rolling(120,min_periods=60).quantile(.20)
    out['macd']=macd; out['macd_signal']=sig; out['hist']=hist
    out['macd_cross_up']=((macd>sig)&(macd.shift(1)<=sig.shift(1))).fillna(False)
    out['macd_cross_down']=((macd<sig)&(macd.shift(1)>=sig.shift(1))).fillna(False)
    out['atr14']=atr(out,14)
    out['vol_prev10_avg']=v.shift(1).rolling(10,min_periods=10).mean()
    out['vol_ok']=(v>out['vol_prev10_avg']).fillna(False)
    return out


def entry_variants()->list[dict[str,Any]]:
    rows=[]
    for squeeze in ('abs10','abs5','relative20','release20'):
        for macd_mode in ('cross','hist_rise2'):
            rows.append({'name':f'{squeeze}__{macd_mode}','squeeze':squeeze,'macd_mode':macd_mode})
    return rows


def squeeze_condition(d:pd.DataFrame,mode:str)->pd.Series:
    w=pd.to_numeric(d['bb_width_pct'],errors='coerce'); q=pd.to_numeric(d['bb_width_q20_prev120'],errors='coerce')
    if mode=='abs10': return (w<=10.0).fillna(False)
    if mode=='abs5': return (w<=5.0).fillna(False)
    if mode=='relative20': return (w<=q).fillna(False)
    if mode=='release20':
        prev_squeeze=(w.shift(1)<=q.shift(1)).fillna(False)
        return (prev_squeeze & (w>w.shift(1))).fillna(False)
    raise ValueError(mode)


def entry_events(d:pd.DataFrame,v:dict[str,Any])->pd.Series:
    h=pd.to_numeric(d['hist'],errors='coerce'); m=pd.to_numeric(d['macd'],errors='coerce')
    common=squeeze_condition(d,v['squeeze']) & d['vol_ok'] & (m>0.0)
    if v['macd_mode']=='cross':
        return (common & d['macd_cross_up']).fillna(False)
    trig=(h>h.shift(1))&(h.shift(1)>h.shift(2))
    cond=(common&trig).fillna(False)
    return (cond & ~cond.shift(1).fillna(False)).fillna(False)


def structure(period:str)->dict[str,Any]:
    return {
      '15m':dict(stop_mode='atr',stop_atr=.90,swing=5,buffer=.10,trail=1.50,max_hold=24),
      '30m':dict(stop_mode='atr',stop_atr=1.00,swing=5,buffer=.15,trail=1.60,max_hold=24),
      '45m':dict(stop_mode='atr',stop_atr=1.10,swing=5,buffer=.15,trail=1.70,max_hold=24),
      '1H':dict(stop_mode='atr',stop_atr=1.15,swing=7,buffer=.20,trail=1.80,max_hold=32),
      '2H':dict(stop_mode='atr',stop_atr=1.20,swing=7,buffer=.20,trail=2.00,max_hold=40),
      '4H':dict(stop_mode='swing',stop_atr=1.20,swing=7,buffer=.20,trail=2.00,max_hold=40),
      '1D':dict(stop_mode='swing',stop_atr=1.25,swing=7,buffer=.20,trail=2.20,max_hold=40),
      '1W':dict(stop_mode='swing',stop_atr=1.30,swing=9,buffer=.15,trail=2.30,max_hold=60),
      '1M':dict(stop_mode='swing',stop_atr=1.30,swing=9,buffer=.15,trail=2.50,max_hold=36),
    }[period].copy()


def initial_stop(d:pd.DataFrame,sp:int,entry:float,p:dict[str,Any])->tuple[float,float]:
    a=float(d['atr14'].iloc[sp])
    if not np.isfinite(a) or a<=0: a=max(entry*.02,1e-6)
    atr_stop=entry-float(p['stop_atr'])*a
    if p['stop_mode']=='atr': raw=atr_stop
    else:
        start=max(0,sp-int(p['swing'])+1)
        sw=float(pd.to_numeric(d['low'].iloc[start:sp+1],errors='coerce').min())
        ss=sw-float(p['buffer'])*a
        raw=ss if np.isfinite(ss) and ss<entry else atr_stop
    risk=entry-raw; risk=min(max(risk,.60*a),2.60*a)
    return entry-risk,risk


def simulate(d:pd.DataFrame,sp:int,p:dict[str,Any])->dict[str,Any]|None:
    ep=sp+1
    if ep>=len(d): return None
    entry=float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry<=0: return None
    stop,risk=initial_stop(d,sp,entry,p)
    tp1,tp2,tp3=entry+risk,entry+2*risk,entry+3*risk
    remaining=1.0; cash=0.0; h1=h2=h3=False; trail=False; highest=entry; minlow=entry; maxhigh=entry
    last=min(len(d)-1,ep+int(p['max_hold'])-1); exit_pos=ep; reason='TIME'
    for pos in range(ep,last+1):
        row=d.iloc[pos]; hi=float(row['high']); lo=float(row['low']); cl=float(row['close'])
        highest=max(highest,hi); maxhigh=max(maxhigh,hi); minlow=min(minlow,lo)
        # Conservative intrabar ambiguity: stop before target.
        if lo<=stop:
            cash+=remaining*stop; remaining=0.0; exit_pos=pos; reason='TRAIL' if trail else 'STOP'; break
        if not h1 and hi>=tp1:
            q=min(remaining,.30); cash+=q*tp1; remaining-=q; h1=True
        if remaining>1e-12 and not h2 and hi>=tp2:
            q=min(remaining,.30); cash+=q*tp2; remaining-=q; h2=True; trail=True
        if remaining>1e-12 and not h3 and hi>=tp3:
            q=min(remaining,.20); cash+=q*tp3; remaining-=q; h3=True
        if remaining>1e-12 and trail:
            a=float(row['atr14'])
            if np.isfinite(a) and a>0: stop=max(stop,highest-float(p['trail'])*a)
        if pos==last and remaining>1e-12:
            cash+=remaining*cl; remaining=0.0; exit_pos=pos; reason='TIME'; break
    pnl=cash-entry
    return {'signal_time':pd.Timestamp(d.index[sp]),'entry_time':pd.Timestamp(d.index[ep]),'exit_time':pd.Timestamp(d.index[exit_pos]),
            'entry':entry,'risk':risk,'realized_r':pnl/risk,'mfe_r':(maxhigh-entry)/risk,'mae_r':(minlow-entry)/risk,
            'tp1_hit':h1,'tp2_hit':h2,'tp3_hit':h3,'exit_reason':reason,'exit_pos':exit_pos}


def net_r(t:dict[str,Any])->float:
    entry=float(t['entry']); risk=float(t['risk']); gross=float(t['realized_r']); weighted=entry+gross*risk
    c=COMMISSION_BPS/10000.0; s=SLIPPAGE_BPS/10000.0
    buy=entry*(1+s); sell=weighted*(1-s)
    return (sell*(1-c)-buy*(1+c))/risk


def metrics(trades:list[dict[str,Any]])->dict[str,Any]:
    if not trades: return {'trades':0,'profit_factor':None,'expectancy_r':0.0,'win_rate_pct':0.0}
    r=np.array([net_r(t) for t in trades],dtype=float); gp=float(r[r>0].sum()); gl=float(-r[r<0].sum())
    return {'trades':len(trades),'profit_factor':gp/gl if gl>0 else None,'expectancy_r':float(r.mean()),
            'median_r':float(np.median(r)),'win_rate_pct':float((r>0).mean()*100),
            'avg_mfe_r':float(np.mean([t['mfe_r'] for t in trades])),'avg_mae_r':float(np.mean([t['mae_r'] for t in trades])),
            'tp1_rate_pct':float(np.mean([t['tp1_hit'] for t in trades])*100),'tp2_rate_pct':float(np.mean([t['tp2_hit'] for t in trades])*100),
            'tp3_rate_pct':float(np.mean([t['tp3_hit'] for t in trades])*100),'exit_reasons':dict(sorted(Counter(t['exit_reason'] for t in trades).items()))}


def bounds_for(times:list[pd.Timestamp])->list[pd.Timestamp]:
    if len(times)<80:return []
    b=[pd.Timestamp(times[min(len(times)-1,int(len(times)*q))]) for q in BOUNDARIES[:-1]]
    b.append(pd.Timestamp(times[-1])+pd.Timedelta(days=3700)); return b


def collect(frames,entry_name,p,start,end):
    out=[]
    for sym,d,pbe in frames:
        last_exit=-1
        for sp in pbe.get(entry_name,[]):
            st=pd.Timestamp(d.index[sp])
            if st<start: continue
            if st>=end: break
            if sp<=last_exit: continue
            t=simulate(d,sp,p)
            if t is None: continue
            if pd.Timestamp(t['exit_time'])>=end: continue
            t['symbol']=sym; out.append(t); last_exit=int(t['exit_pos'])
    out.sort(key=lambda x:x['entry_time']); return out


def classify(row):
    m=row['stitched']; n=int(m.get('trades',0)); pf=float(m.get('profit_factor') or 0); e=float(m.get('expectancy_r',0)); pos=row['positive_folds']; worst=row['worst_fold_expectancy_r']
    if n<30:return 'INSUFFICIENT_SAMPLE'
    if pos==4 and pf>1.20 and e>0.08 and worst>0:return 'ROBUST_STRONG'
    if pos>=3 and pf>1.10 and e>0:return 'ROBUST_PROMISING'
    if pf>1 and e>0:return 'POSITIVE_UNSTABLE'
    return 'REJECT'


def analyze(db,period):
    entries=entry_variants(); p=structure(period); frames=[]; times={e['name']:[] for e in entries}; counts=Counter()
    with MarketDataStore(db,read_only=True) as store:
        syms=store.list_symbols('BIST',period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22: continue
            d=indicators(fr); pbe={}
            for e in entries:
                ev=entry_events(d,e); ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
                pbe[e['name']]=ps; counts[e['name']]+=len(ps); times[e['name']].extend(pd.Timestamp(d.index[x]) for x in ps)
            if any(pbe.values()):frames.append((sym,d,pbe))
            if i%100==0 or i==len(syms):print(f'[{period}] {i}/{len(syms)}',flush=True)
    for k in times:times[k].sort()
    rows=[]
    for e in entries:
        b=bounds_for(times[e['name']])
        if not b: continue
        folds=[]; stitched=[]
        for fi in range(4):
            tr=collect(frames,e['name'],p,b[fi],b[fi+1]); stitched.extend(tr); folds.append({'fold':fi+1,'metrics':metrics(tr)})
        sm=metrics(stitched); ex=[float(f['metrics'].get('expectancy_r',0)) for f in folds]
        r={'entry':e,'signal_count':counts[e['name']],'folds':folds,'stitched':sm,'positive_folds':sum(x>0 for x in ex),
           'worst_fold_expectancy_r':float(min(ex)),'median_fold_expectancy_r':float(np.median(ex))}; r['classification']=classify(r); rows.append(r)
    rank={'ROBUST_STRONG':4,'ROBUST_PROMISING':3,'POSITIVE_UNSTABLE':2,'REJECT':1,'INSUFFICIENT_SAMPLE':0}
    rows.sort(key=lambda r:(rank[r['classification']],r['positive_folds'],r['worst_fold_expectancy_r'],r['median_fold_expectancy_r'],float(r['stitched'].get('expectancy_r',0))),reverse=True)
    return {'version':'bb-squeeze-entry-stage-v1','period':period,'method':'8 frozen entries; same structural exit; entry-specific 4 chronological windows; costs included','rows':rows,'best':rows[0] if rows else None,
            'warning':'Historical research on observed data; future unseen bars are true forward validation.'}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--period',choices=PERIODS,required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    d=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
