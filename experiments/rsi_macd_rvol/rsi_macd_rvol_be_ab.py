"""Final TP1 break-even A/B for frozen RSI/MACD/RVOL candidates.

Compares:
- none: keep original structural/adaptive stop after TP1
- entry: move remaining stop to raw entry after TP1
- cost: move remaining stop to exact round-trip friction break-even after TP1

Uses the same entry-specific chronological windows and rejects trades whose exit
would cross the fold end, matching rsi_macd_rvol_wf.collect methodology.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from rsi_macd_rvol_wf import (
    COMMISSION_BPS, SLIPPAGE_BPS, WARMUP, MarketDataStore, indicators,
    entry_variants, entry_events, initial_stop, hist_flags, metrics, bounds_for,
)

PERIODS=("4H","1D","1W","1M")
ENTRY={
    "4H":"r55_70__A_cross",
    "1D":"r50_65__B_hist_rise2",
    "1W":"r50_65__A_cross",
    "1M":"r55_70__D_hist_pos_rise",
}
FINAL={
    "4H":dict(name="adaptive",rule="adaptive",stop_mode="swing",stop_atr=1.2,swing=7,buffer=.20,trail=2.0,tight=1.5,max_hold=40,tp1=1.0,tp2=2.0,tp3=3.0),
    "1D":dict(name="structural_control",rule="none",stop_mode="swing",stop_atr=1.25,swing=7,buffer=.20,trail=2.2,tight=1.65,max_hold=40,tp1=1.0,tp2=2.0,tp3=3.0),
    "1W":dict(name="structural_control",rule="none",stop_mode="swing",stop_atr=1.3,swing=11,buffer=.15,trail=2.1,tight=1.75,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3),
    "1M":dict(name="structural_control",rule="none",stop_mode="swing",stop_atr=1.3,swing=9,buffer=.15,trail=2.5,tight=1.9,max_hold=36,tp1=1.0,tp2=2.0,tp3=3.0),
}


def cost_be_price(entry:float)->float:
    c=COMMISSION_BPS/10000.0; s=SLIPPAGE_BPS/10000.0
    buy_cash=entry*(1.0+s)*(1.0+c)
    return buy_cash/((1.0-s)*(1.0-c))


def simulate_be(data:pd.DataFrame, signal_pos:int, p:dict[str,Any], be_mode:str)->dict[str,Any]|None:
    ep=signal_pos+1
    if ep>=len(data): return None
    entry=float(data["open"].iloc[ep])
    if not np.isfinite(entry) or entry<=0: return None
    stop,risk=initial_stop(data,signal_pos,entry,p)
    if risk<=0: return None
    tp1=entry+risk*float(p["tp1"]); tp2=entry+risk*float(p["tp2"]); tp3=entry+risk*float(p["tp3"])
    remaining=1.0; cash=0.0
    tp1h=tp2h=tp3h=False; trail_active=False; tight=False; be_armed=False
    highest=entry; min_low=entry; max_high=entry; exit_reason="TIME"; exit_pos=ep
    last=min(len(data)-1,ep+int(p["max_hold"])-1)
    for pos in range(ep,last+1):
        row=data.iloc[pos]; high=float(row["high"]); low=float(row["low"]); close=float(row["close"])
        highest=max(highest,high); max_high=max(max_high,high); min_low=min(min_low,low)
        if low<=stop:
            cash+=remaining*stop; remaining=0.0
            exit_reason="BE" if be_armed else ("TRAIL" if trail_active or tight else "STOP")
            exit_pos=pos; break
        just_tp1=False
        if not tp1h and high>=tp1:
            q=min(remaining,.30); cash+=q*tp1; remaining-=q; tp1h=True; just_tp1=True
        if remaining>1e-12 and not tp2h and high>=tp2:
            q=min(remaining,.30); cash+=q*tp2; remaining-=q; tp2h=True; trail_active=True
        if remaining>1e-12 and not tp3h and high>=tp3:
            q=min(remaining,.20); cash+=q*tp3; remaining-=q; tp3h=True
        if just_tp1 and be_mode!="none":
            target=entry if be_mode=="entry" else cost_be_price(entry)
            if target>stop:
                stop=target; be_armed=True
        fade2,negfall=hist_flags(data,pos)
        rv=row["rsi14"]; rsi=float(rv) if np.isfinite(rv) else 50.0
        rule=p["rule"]; full=False
        if rule=="rsi_below50": full=rsi<50.0
        elif rule=="hist_neg_falling": full=negfall
        elif rule=="macd_bear_cross": full=bool(row["macd_cross_down"])
        elif rule=="rsi_and_hist": full=(rsi<50.0 and negfall)
        elif rule=="adaptive":
            if rsi<50.0 or fade2: tight=True
            full=(rsi<50.0 and negfall)
        if full and remaining>1e-12:
            cash+=remaining*close; remaining=0.0; exit_reason="TECH"; exit_pos=pos; break
        if remaining>1e-12 and (trail_active or tight):
            a=float(row["atr14"])
            if np.isfinite(a) and a>0:
                mult=float(p["tight"] if tight else p["trail"])
                new_stop=highest-mult*a
                if new_stop>stop:
                    stop=new_stop
                    if stop>=(cost_be_price(entry) if be_mode=="cost" else entry): be_armed=False
        if pos==last and remaining>1e-12:
            cash+=remaining*close; remaining=0.0; exit_reason="TIME"; exit_pos=pos; break
    pnl=cash-entry
    return {"signal_time":pd.Timestamp(data.index[signal_pos]),"entry_time":pd.Timestamp(data.index[ep]),
            "exit_time":pd.Timestamp(data.index[exit_pos]),"entry":entry,"risk":risk,
            "realized_r":pnl/risk,"return_pct":pnl/entry*100.0,
            "mfe_r":(max_high-entry)/risk,"mae_r":(min_low-entry)/risk,
            "tp1_hit":tp1h,"tp2_hit":tp2h,"tp3_hit":tp3h,"exit_reason":exit_reason,"exit_pos":exit_pos}


def load_frames(db:str,period:str):
    en=ENTRY[period]; evdef=next(x for x in entry_variants() if x["name"]==en)
    frames=[]; times=[]; count=0
    with MarketDataStore(db,read_only=True) as store:
        symbols=store.list_symbols("BIST",period)
        for i,symbol in enumerate(symbols,1):
            frame=store.load_dataframe(symbol,"BIST",period,limit=0)
            if frame is None or len(frame)<=WARMUP+22: continue
            data=indicators(frame); ev=entry_events(data,evdef)
            ps=[int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
            if ps:
                frames.append((symbol,data,ps)); count+=len(ps); times.extend(pd.Timestamp(data.index[x]) for x in ps)
            if i%100==0 or i==len(symbols): print(f"[{period}] {i}/{len(symbols)}",flush=True)
    times.sort(); return frames,times,count


def collect(frames,p,start,end,mode):
    out=[]
    for symbol,data,ps in frames:
        last_exit=-1
        for signal_pos in ps:
            st=pd.Timestamp(data.index[signal_pos])
            if st<start: continue
            if st>=end: break
            if signal_pos<=last_exit: continue
            t=simulate_be(data,signal_pos,p,mode)
            if t is None: continue
            if pd.Timestamp(t["exit_time"])>=end: continue
            t["symbol"]=symbol; out.append(t); last_exit=int(t["exit_pos"])
    out.sort(key=lambda x:x["entry_time"]); return out


def evaluate(frames,p,bounds,mode):
    folds=[]; stitched=[]
    for fi in range(4):
        tr=collect(frames,p,bounds[fi],bounds[fi+1],mode); stitched.extend(tr)
        folds.append({"fold":fi+1,"start":bounds[fi].isoformat(),"end":bounds[fi+1].isoformat(),"metrics":metrics(tr)})
    sm=metrics(stitched); ex=[float(x["metrics"].get("expectancy_r",0)) for x in folds]
    return {"mode":mode,"folds":folds,"stitched":sm,"positive_folds":sum(x>0 for x in ex),"worst_fold_expectancy_r":min(ex),"median_fold_expectancy_r":float(np.median(ex))}


def analyze(db,period):
    frames,times,count=load_frames(db,period); bounds=bounds_for(times)
    if not bounds: return {"period":period,"classification":"INSUFFICIENT_SAMPLE","signal_count":count}
    p=dict(FINAL[period]); rows=[evaluate(frames,p,bounds,m) for m in ("none","entry","cost")]
    none=rows[0]; winner=max(rows,key=lambda r:(r["positive_folds"],r["worst_fold_expectancy_r"],float(r["stitched"].get("expectancy_r",0)),float(r["stitched"].get("profit_factor") or 0)))
    decision="NO_BE" if winner["mode"]=="none" else f"USE_{winner['mode'].upper()}_BE"
    return {"version":"rsi-macd-rvol-be-ab-v1","period":period,"entry_frozen":ENTRY[period],"profile":p,"signal_count":count,
            "method":"same final entry/profile; entry-specific 4 windows; fold-end crossing trades excluded; 10bps commission + 10bps slippage each side",
            "cost_be_formula":"entry*(1+s)*(1+c)/((1-s)*(1-c))","rows":rows,"decision":decision,
            "warning":"Historical research on observed data; future bars are true forward validation."}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--db",required=True); ap.add_argument("--period",choices=PERIODS,required=True); ap.add_argument("--output",required=True); a=ap.parse_args()
    d=analyze(a.db,a.period); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8"); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=="__main__": main()
