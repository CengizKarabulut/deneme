"""TavanTarama entry-quality research.

Two DMI trigger families are compared under the same structural exit:
A original: +DI > -DI and +DI fresh-crosses ADX.
B alternative: +DI fresh-crosses -DI and ADX is rising.

Controlled filters: RSI bands, StochRSI cross/confirmation, RVOL 1.2/1.5.
Each variant uses its own four chronological windows.
"""
from __future__ import annotations

import argparse, json, sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_BB = Path(__file__).resolve().parents[1] / "bb_squeeze"
sys.path.insert(0, str(_BB))
from bb_squeeze_entry_stage import (  # noqa: E402
    MarketDataStore, PERIODS, WARMUP, structure, simulate, metrics, bounds_for, collect
)


def wilder(s: pd.Series, length: int) -> pd.Series:
    return s.ewm(alpha=1.0/length, adjust=False, min_periods=length).mean()


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d).clip(lower=0.0)
    au = wilder(up, length)
    ad = wilder(dn, length)
    rs = au / ad.replace(0.0, np.nan)
    out = 100.0 - 100.0/(1.0 + rs)
    out = out.where(ad != 0.0, 100.0)
    return out


def dmi(frame: pd.DataFrame, length: int = 14):
    h = pd.to_numeric(frame['high'], errors='coerce')
    l = pd.to_numeric(frame['low'], errors='coerce')
    c = pd.to_numeric(frame['close'], errors='coerce')
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=frame.index)
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr = wilder(tr, length)
    pdi = 100.0 * wilder(plus_dm, length) / atr.replace(0.0, np.nan)
    mdi = 100.0 * wilder(minus_dm, length) / atr.replace(0.0, np.nan)
    dx = 100.0 * (pdi-mdi).abs() / (pdi+mdi).replace(0.0, np.nan)
    adx = wilder(dx, length)
    return pdi, mdi, adx, atr


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    c = pd.to_numeric(out['close'], errors='coerce')
    v = pd.to_numeric(out['volume'], errors='coerce')
    pdi, mdi, adx, atr14 = dmi(out, 14)
    r = rsi(c, 14)
    lo = r.rolling(14, min_periods=14).min()
    hi = r.rolling(14, min_periods=14).max()
    raw = 100.0 * (r-lo) / (hi-lo).replace(0.0, np.nan)
    k = raw.rolling(3, min_periods=3).mean()
    sd = k.rolling(3, min_periods=3).mean()
    rvavg = v.shift(1).rolling(20, min_periods=20).mean()
    out['plus_di'] = pdi
    out['minus_di'] = mdi
    out['adx14'] = adx
    out['atr14'] = atr14
    out['rsi14'] = r
    out['stoch_k'] = k
    out['stoch_d'] = sd
    out['stoch_cross_up'] = ((k > sd) & (k.shift(1) <= sd.shift(1))).fillna(False)
    out['rvol20'] = v / rvavg.replace(0.0, np.nan)
    return out


def entry_variants() -> list[dict[str, Any]]:
    rows=[]
    for dmi_mode in ('orig_pdi_cross_adx','alt_pdi_cross_mdi_adx_rise'):
        for rsi_low in (30,40,50):
            for stoch_mode in ('cross','confirm'):
                for rvol in (1.2,1.5):
                    rows.append({
                        'name': f"{dmi_mode}__rsi{rsi_low}_70__stoch_{stoch_mode}__rv{str(rvol).replace('.','')}",
                        'dmi_mode': dmi_mode, 'rsi_low': rsi_low, 'rsi_high': 70,
                        'stoch_mode': stoch_mode, 'rvol': rvol,
                    })
    return rows


def entry_events(d: pd.DataFrame, v: dict[str, Any]) -> pd.Series:
    p = pd.to_numeric(d['plus_di'], errors='coerce')
    m = pd.to_numeric(d['minus_di'], errors='coerce')
    a = pd.to_numeric(d['adx14'], errors='coerce')
    r = pd.to_numeric(d['rsi14'], errors='coerce')
    k = pd.to_numeric(d['stoch_k'], errors='coerce')
    sd = pd.to_numeric(d['stoch_d'], errors='coerce')
    rv = pd.to_numeric(d['rvol20'], errors='coerce')
    if v['dmi_mode']=='orig_pdi_cross_adx':
        trig = (p > m) & (p > a) & (p.shift(1) <= a.shift(1))
    else:
        trig = (p > m) & (p.shift(1) <= m.shift(1)) & (a > a.shift(1))
    rsi_ok = (r >= float(v['rsi_low'])) & (r < float(v['rsi_high']))
    stoch_ok = d['stoch_cross_up'] if v['stoch_mode']=='cross' else (k > sd)
    return (trig & rsi_ok & stoch_ok & (rv > float(v['rvol']))).fillna(False)


def classify(row):
    m=row['stitched']; n=int(m.get('trades',0)); pf=float(m.get('profit_factor') or 0); e=float(m.get('expectancy_r',0)); pos=row['positive_folds']; worst=row['worst_fold_expectancy_r']
    if n<30:return 'INSUFFICIENT_SAMPLE'
    if pos==4 and pf>1.20 and e>0.08 and worst>0:return 'ROBUST_STRONG'
    if pos>=3 and pf>1.10 and e>0:return 'ROBUST_PROMISING'
    if pf>1 and e>0:return 'POSITIVE_UNSTABLE'
    return 'REJECT'


def analyze(db: str, period: str):
    entries=entry_variants(); p=structure(period); frames=[]
    times={e['name']:[] for e in entries}; counts=Counter()
    with MarketDataStore(db, read_only=True) as store:
        syms=store.list_symbols('BIST', period)
        for i,sym in enumerate(syms,1):
            fr=store.load_dataframe(sym,'BIST',period,limit=0)
            if fr is None or len(fr)<=WARMUP+22: continue
            d=indicators(fr); pbe={}
            for e in entries:
                ev=entry_events(d,e)
                ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(d)]
                pbe[e['name']]=ps; counts[e['name']]+=len(ps); times[e['name']].extend(pd.Timestamp(d.index[x]) for x in ps)
            if any(pbe.values()): frames.append((sym,d,pbe))
            if i%100==0 or i==len(syms): print(f'[{period}] {i}/{len(syms)}', flush=True)
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
    rows.sort(key=lambda x:(rank[x['classification']],x['positive_folds'],x['worst_fold_expectancy_r'],x['median_fold_expectancy_r'],float(x['stitched'].get('expectancy_r',0))), reverse=True)
    # Direct baseline comparison isolates the user's two requested DMI rules.
    baseline=[r for r in rows if r['entry']['rsi_low']==30 and r['entry']['stoch_mode']=='cross' and abs(float(r['entry']['rvol'])-1.2)<1e-9]
    baseline.sort(key=lambda x:x['entry']['dmi_mode'])
    return {'version':'tavan-entry-stage-v1','period':period,'method':'24 frozen entry variants; same structural exit; entry-specific four chronological windows; costs included','baseline_dmi_head_to_head':baseline,'rows':rows,'best':rows[0] if rows else None,'warning':'Historical research on observed data; future unseen bars are true forward validation.'}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--period',choices=PERIODS,required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    d=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))

if __name__=='__main__': main()
