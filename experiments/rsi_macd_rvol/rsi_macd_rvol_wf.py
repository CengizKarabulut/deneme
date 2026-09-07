"""RSI & MACD - RVOL scan research.

Entry dimensions (held fixed inside each evaluated combination):
- RSI band: 50-65, 50-70, 55-70
- MACD trigger:
  A_cross: MACD(12,26,9) crosses above signal
  B_hist_rise2: histogram rises two consecutive bars
  C_hist_rise2_neg: same while histogram < 0
  D_hist_pos_rise: histogram > 0 and rises vs previous bar
- RVOL20 > 1.50, where current volume is divided by the mean of the
  previous 20 bars of the same timeframe; current bar is excluded.

Exit families:
- structural control
- RSI < 50 hard exit
- histogram < 0 and falling hard exit
- MACD bearish crossover hard exit
- RSI < 50 AND histogram < 0/falling hard exit
- adaptive: RSI < 50 or two-bar histogram fade tightens ATR trail;
  RSI < 50 AND histogram < 0/falling closes remaining position.

All signals use completed bars; entry reference is t+1 open. Costs are included.
For robustness, every entry+exit combination is held fixed across four
chronological validation windows derived from that entry rule's own event
timeline. This avoids common-boundary artifacts across different signal families.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_SHARED = Path(__file__).resolve().parents[1] / "stoch_rsi_momentum_volume"
sys.path.insert(0, str(_SHARED))
from market_data_store import MarketDataStore  # noqa: E402

PERIODS = ("15m","30m","45m","1H","2H","4H","1D","1W","1M")
BOUNDARIES = (0.45,0.60,0.75,0.90,1.00)
COMMISSION_BPS = 10.0
SLIPPAGE_BPS = 10.0
WARMUP = 240


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def rsi_wilder(close: pd.Series, length: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0.0)
    dn = (-d.clip(upper=0.0))
    au = up.ewm(alpha=1.0/length, adjust=False, min_periods=length).mean()
    ad = dn.ewm(alpha=1.0/length, adjust=False, min_periods=length).mean()
    rs = au / ad.replace(0.0, np.nan)
    rsi = 100.0 - 100.0/(1.0+rs)
    return rsi.where(ad != 0.0, 100.0)


def atr(frame: pd.DataFrame, length: int = 14) -> pd.Series:
    h = pd.to_numeric(frame["high"], errors="coerce")
    l = pd.to_numeric(frame["low"], errors="coerce")
    c = pd.to_numeric(frame["close"], errors="coerce")
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/length, adjust=False, min_periods=length).mean()


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    c = pd.to_numeric(out["close"], errors="coerce")
    v = pd.to_numeric(out["volume"], errors="coerce")
    e12, e26 = ema(c,12), ema(c,26)
    macd = e12-e26
    sig = ema(macd,9)
    hist = macd-sig
    out["rsi14"] = rsi_wilder(c,14)
    out["macd"] = macd
    out["macd_signal"] = sig
    out["hist"] = hist
    out["atr14"] = atr(out,14)
    out["vol_prev20_avg"] = v.shift(1).rolling(20,min_periods=20).mean()
    out["rvol20"] = v / out["vol_prev20_avg"].replace(0.0,np.nan)
    out["macd_cross_up"] = ((macd > sig) & (macd.shift(1) <= sig.shift(1))).fillna(False)
    out["macd_cross_down"] = ((macd < sig) & (macd.shift(1) >= sig.shift(1))).fillna(False)
    return out


def entry_variants() -> list[dict[str,Any]]:
    rows=[]
    bands=[("r50_65",50.0,65.0),("r50_70",50.0,70.0),("r55_70",55.0,70.0)]
    modes=[
        ("A_cross","MACD crosses above signal"),
        ("B_hist_rise2","Histogram H[t] > H[t-1] > H[t-2]"),
        ("C_hist_rise2_neg","Histogram rises 2 bars and H[t] < 0"),
        ("D_hist_pos_rise","Histogram H[t] > 0 and H[t] > H[t-1]"),
    ]
    for bn,lo,hi in bands:
        for mn,desc in modes:
            rows.append({"name":f"{bn}__{mn}","rsi_lo":lo,"rsi_hi":hi,"macd_mode":mn,"description":desc})
    return rows


def entry_events(data: pd.DataFrame, v: dict[str,Any]) -> pd.Series:
    r = pd.to_numeric(data["rsi14"], errors="coerce")
    h = pd.to_numeric(data["hist"], errors="coerce")
    common = (r >= float(v["rsi_lo"])) & (r < float(v["rsi_hi"])) & (data["rvol20"] > 1.50)
    mode=v["macd_mode"]
    if mode=="A_cross":
        cond = common & data["macd_cross_up"]
        return cond.fillna(False)
    if mode=="B_hist_rise2":
        trig=(h > h.shift(1)) & (h.shift(1) > h.shift(2))
    elif mode=="C_hist_rise2_neg":
        trig=(h > h.shift(1)) & (h.shift(1) > h.shift(2)) & (h < 0.0)
    elif mode=="D_hist_pos_rise":
        trig=(h > 0.0) & (h > h.shift(1))
    else:
        raise ValueError(mode)
    cond=(common & trig).fillna(False)
    return (cond & ~cond.shift(1).fillna(False)).fillna(False)


def structure(period: str) -> dict[str,Any]:
    table={
        "15m":dict(stop_mode="atr",stop_atr=.90,swing=5,buffer=.10,trail=1.50,tight=1.00,max_hold=24),
        "30m":dict(stop_mode="atr",stop_atr=1.00,swing=5,buffer=.15,trail=1.60,tight=1.15,max_hold=24),
        "45m":dict(stop_mode="atr",stop_atr=1.10,swing=5,buffer=.15,trail=1.70,tight=1.25,max_hold=24),
        "1H":dict(stop_mode="atr",stop_atr=1.15,swing=7,buffer=.20,trail=1.80,tight=1.35,max_hold=32),
        "2H":dict(stop_mode="atr",stop_atr=1.20,swing=7,buffer=.20,trail=2.10,tight=1.55,max_hold=40),
        "4H":dict(stop_mode="swing",stop_atr=1.20,swing=7,buffer=.20,trail=2.00,tight=1.50,max_hold=40),
        "1D":dict(stop_mode="swing",stop_atr=1.25,swing=7,buffer=.20,trail=2.20,tight=1.65,max_hold=40),
        "1W":dict(stop_mode="swing",stop_atr=1.30,swing=9,buffer=.15,trail=2.30,tight=1.75,max_hold=60),
        "1M":dict(stop_mode="swing",stop_atr=1.30,swing=9,buffer=.15,trail=2.50,tight=1.90,max_hold=36),
    }
    return dict(table[period])


def exit_variants(period: str) -> list[dict[str,Any]]:
    s=structure(period)
    defs=[
        ("structural_control","none"),
        ("rsi_below50","rsi_below50"),
        ("hist_neg_falling","hist_neg_falling"),
        ("macd_bear_cross","macd_bear_cross"),
        ("rsi_and_hist","rsi_and_hist"),
        ("adaptive","adaptive"),
    ]
    rows=[]
    for name,rule in defs:
        p=dict(s)
        p.update({"name":name,"rule":rule,"tp1":1.0,"tp2":2.0,"tp3":3.0,
                  "alloc":(0.30,0.30,0.20),"runner":0.20})
        rows.append(p)
    return rows


def initial_stop(data: pd.DataFrame, signal_pos: int, entry: float, p: dict[str,Any]) -> tuple[float,float]:
    a=float(data["atr14"].iloc[signal_pos])
    if not np.isfinite(a) or a<=0:
        a=max(entry*.02,1e-6)
    atr_stop=entry-float(p["stop_atr"])*a
    if p["stop_mode"]=="atr":
        raw=atr_stop
    else:
        start=max(0,signal_pos-int(p["swing"])+1)
        sw=float(pd.to_numeric(data["low"].iloc[start:signal_pos+1],errors="coerce").min())
        swing_stop=sw-float(p["buffer"])*a
        raw=swing_stop if np.isfinite(swing_stop) and swing_stop<entry else atr_stop
    risk=entry-raw
    risk=min(max(risk,.60*a),2.60*a)
    return entry-risk,risk


def hist_flags(data: pd.DataFrame,pos:int)->tuple[bool,bool]:
    if pos<2:
        return False,False
    h0=float(data["hist"].iloc[pos]); h1=float(data["hist"].iloc[pos-1]); h2=float(data["hist"].iloc[pos-2])
    if not all(np.isfinite(x) for x in (h0,h1,h2)):
        return False,False
    return (h0<h1<h2),(h0<0.0 and h0<h1)


def simulate(data:pd.DataFrame, signal_pos:int, p:dict[str,Any])->dict[str,Any]|None:
    ep=signal_pos+1
    if ep>=len(data):
        return None
    entry=float(data["open"].iloc[ep])
    if not np.isfinite(entry) or entry<=0:
        return None
    stop,risk=initial_stop(data,signal_pos,entry,p)
    if risk<=0:
        return None
    tp1=entry+risk*float(p["tp1"]); tp2=entry+risk*float(p["tp2"]); tp3=entry+risk*float(p["tp3"])
    remaining=1.0; cash=0.0
    tp1h=tp2h=tp3h=False
    trail_active=False; tight=False
    highest=entry; min_low=entry; max_high=entry
    exit_reason="TIME"; exit_pos=ep
    last=min(len(data)-1,ep+int(p["max_hold"])-1)
    for pos in range(ep,last+1):
        row=data.iloc[pos]
        high=float(row["high"]); low=float(row["low"]); close=float(row["close"])
        highest=max(highest,high); max_high=max(max_high,high); min_low=min(min_low,low)

        if low<=stop:
            cash+=remaining*stop; remaining=0.0
            exit_reason="TRAIL" if trail_active or tight else "STOP"; exit_pos=pos; break

        if not tp1h and high>=tp1:
            q=min(remaining,.30); cash+=q*tp1; remaining-=q; tp1h=True
        if remaining>1e-12 and not tp2h and high>=tp2:
            q=min(remaining,.30); cash+=q*tp2; remaining-=q; tp2h=True; trail_active=True
        if remaining>1e-12 and not tp3h and high>=tp3:
            q=min(remaining,.20); cash+=q*tp3; remaining-=q; tp3h=True

        fade2,negfall=hist_flags(data,pos)
        rv=row["rsi14"]
        rsi=float(rv) if np.isfinite(rv) else 50.0
        rule=p["rule"]; full=False
        if rule=="rsi_below50":
            full=rsi<50.0
        elif rule=="hist_neg_falling":
            full=negfall
        elif rule=="macd_bear_cross":
            full=bool(row["macd_cross_down"])
        elif rule=="rsi_and_hist":
            full=(rsi<50.0 and negfall)
        elif rule=="adaptive":
            if rsi<50.0 or fade2:
                tight=True
            full=(rsi<50.0 and negfall)

        if full and remaining>1e-12:
            cash+=remaining*close; remaining=0.0; exit_reason="TECH"; exit_pos=pos; break

        if remaining>1e-12 and (trail_active or tight):
            a=float(row["atr14"])
            if np.isfinite(a) and a>0:
                mult=float(p["tight"] if tight else p["trail"])
                stop=max(stop,highest-mult*a)

        if pos==last and remaining>1e-12:
            cash+=remaining*close; remaining=0.0; exit_reason="TIME"; exit_pos=pos; break

    pnl=cash-entry
    return {
        "signal_time":pd.Timestamp(data.index[signal_pos]),"entry_time":pd.Timestamp(data.index[ep]),
        "exit_time":pd.Timestamp(data.index[exit_pos]),"entry":entry,"risk":risk,
        "realized_r":pnl/risk,"return_pct":pnl/entry*100.0,
        "mfe_r":(max_high-entry)/risk,"mae_r":(min_low-entry)/risk,
        "tp1_hit":tp1h,"tp2_hit":tp2h,"tp3_hit":tp3h,"exit_reason":exit_reason,"exit_pos":exit_pos,
    }


def net_r(t:dict[str,Any])->float:
    entry=float(t["entry"]); risk=float(t["risk"]); gross=float(t["realized_r"])
    weighted_exit=entry+gross*risk
    c=COMMISSION_BPS/10000.0; s=SLIPPAGE_BPS/10000.0
    buy=entry*(1+s); sell=weighted_exit*(1-s)
    return (sell*(1-c)-buy*(1+c))/risk


def metrics(trades:list[dict[str,Any]])->dict[str,Any]:
    if not trades:
        return {"trades":0,"profit_factor":None,"expectancy_r":0.0,"win_rate_pct":0.0}
    r=np.array([net_r(t) for t in trades],dtype=float)
    gp=float(r[r>0].sum()); gl=float(-r[r<0].sum())
    return {
        "trades":len(trades),"win_rate_pct":float((r>0).mean()*100.0),
        "expectancy_r":float(r.mean()),"median_r":float(np.median(r)),
        "profit_factor":gp/gl if gl>0 else None,
        "avg_mfe_r":float(np.mean([t["mfe_r"] for t in trades])),
        "avg_mae_r":float(np.mean([t["mae_r"] for t in trades])),
        "tp1_rate_pct":float(np.mean([t["tp1_hit"] for t in trades])*100.0),
        "tp2_rate_pct":float(np.mean([t["tp2_hit"] for t in trades])*100.0),
        "tp3_rate_pct":float(np.mean([t["tp3_hit"] for t in trades])*100.0),
        "exit_reasons":dict(sorted(Counter(t["exit_reason"] for t in trades).items())),
    }


def bounds_for(times:list[pd.Timestamp])->list[pd.Timestamp]:
    if len(times)<80:
        return []
    b=[pd.Timestamp(times[min(len(times)-1,int(len(times)*q))]) for q in BOUNDARIES[:-1]]
    b.append(pd.Timestamp(times[-1])+pd.Timedelta(days=3700))
    return b


def collect(frames, entry_name:str, p:dict[str,Any], start, end)->list[dict[str,Any]]:
    trades=[]
    for symbol,data,pbe in frames:
        last_exit=-1
        for signal_pos in pbe.get(entry_name,[]):
            st=pd.Timestamp(data.index[signal_pos])
            if st<start:
                continue
            if st>=end:
                break
            if signal_pos<=last_exit:
                continue
            t=simulate(data,signal_pos,p)
            if t is None:
                continue
            if pd.Timestamp(t["exit_time"])>=end:
                continue
            t["symbol"]=symbol
            trades.append(t); last_exit=int(t["exit_pos"])
    trades.sort(key=lambda x:x["entry_time"])
    return trades


def classify(row:dict[str,Any])->str:
    m=row["stitched"]; trades=int(m.get("trades",0)); pf=float(m.get("profit_factor") or 0.0); exp=float(m.get("expectancy_r",0.0))
    pos=int(row["positive_folds"]); worst=float(row["worst_fold_expectancy_r"])
    if trades<30:
        return "INSUFFICIENT_SAMPLE"
    if pos==4 and pf>1.20 and exp>0.08 and worst>0:
        return "ROBUST_STRONG"
    if pos>=3 and pf>1.10 and exp>0:
        return "ROBUST_PROMISING"
    if pf>1.0 and exp>0:
        return "POSITIVE_UNSTABLE"
    return "REJECT"


def analyze(db:str,period:str)->dict[str,Any]:
    entries=entry_variants(); exits=exit_variants(period)
    frames=[]; times_by_entry={e["name"]:[] for e in entries}; signal_counts=Counter()
    with MarketDataStore(db,read_only=True) as store:
        symbols=store.list_symbols("BIST",period)
        for i,symbol in enumerate(symbols,1):
            frame=store.load_dataframe(symbol,"BIST",period,limit=0)
            if frame is None or len(frame)<=WARMUP+22:
                continue
            data=indicators(frame); pbe={}
            for e in entries:
                ev=entry_events(data,e)
                ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
                pbe[e["name"]]=ps; signal_counts[e["name"]]+=len(ps)
                times_by_entry[e["name"]].extend(pd.Timestamp(data.index[x]) for x in ps)
            if any(pbe.values()):
                frames.append((symbol,data,pbe))
            if i%100==0 or i==len(symbols):
                print(f"[{period}] {i}/{len(symbols)}",flush=True)

    for k in times_by_entry:
        times_by_entry[k].sort()

    rows=[]
    for e in entries:
        bounds=bounds_for(times_by_entry[e["name"]])
        if not bounds:
            continue
        for x in exits:
            folds=[]; stitched=[]
            for fi in range(4):
                tr=collect(frames,e["name"],x,bounds[fi],bounds[fi+1])
                m=metrics(tr); stitched.extend(tr)
                folds.append({"fold":fi+1,"start":bounds[fi].isoformat(),"end":bounds[fi+1].isoformat(),"metrics":m})
            sm=metrics(stitched)
            exps=[float(f["metrics"].get("expectancy_r",0.0)) for f in folds]
            pfs=[float(f["metrics"].get("profit_factor") or 0.0) for f in folds]
            row={"entry":e,"exit":x,"folds":folds,"stitched":sm,
                 "positive_folds":sum(v>0 for v in exps),"pf_above_1_folds":sum(v>1 for v in pfs),
                 "worst_fold_expectancy_r":float(min(exps)),"median_fold_expectancy_r":float(np.median(exps)),
                 "best_fold_expectancy_r":float(max(exps))}
            row["classification"]=classify(row); rows.append(row)

    rank={"ROBUST_STRONG":4,"ROBUST_PROMISING":3,"POSITIVE_UNSTABLE":2,"REJECT":1,"INSUFFICIENT_SAMPLE":0}
    rows.sort(key=lambda r:(rank.get(r["classification"],0),r["positive_folds"],r["worst_fold_expectancy_r"],
                            r["median_fold_expectancy_r"],float(r["stitched"].get("expectancy_r",0.0)),
                            float(r["stitched"].get("profit_factor") or 0.0)),reverse=True)

    best_by_entry={}
    for e in entries:
        subset=[r for r in rows if r["entry"]["name"]==e["name"]]
        if subset:
            best_by_entry[e["name"]]=subset[0]

    return {
        "version":"rsi-macd-rvol-fixed-robustness-v1","period":period,
        "method":"12 fixed entry variants x 6 fixed exits; each entry uses its own four chronological validation windows; t+1 open; costs included; no per-fold re-selection",
        "rvol_rule":"Volume[t] / mean(previous 20 same-TF bars) > 1.50; current bar excluded",
        "signal_counts":dict(signal_counts),"best":rows[0] if rows else None,
        "best_by_entry":best_by_entry,"ranked_combinations":rows,
        "warning":"Historical robustness on observed history; future bars remain true forward validation."
    }


def main()->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",required=True); ap.add_argument("--period",choices=PERIODS,required=True); ap.add_argument("--output",required=True)
    a=ap.parse_args()
    payload=analyze(a.db,a.period)
    path=Path(a.output); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2,default=str))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
