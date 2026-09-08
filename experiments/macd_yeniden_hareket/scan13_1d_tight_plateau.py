from __future__ import annotations
import argparse, json
from pathlib import Path
from scan13_sat_robustness import load_frames, bounds_for, baseline_profile, evaluate

ENTRY={"name":"C_positive_hist_reacceleration","mode":"C"}

def analyze(db):
    frames,times,count=load_frames(db,"1D",ENTRY)
    b=bounds_for(times)
    base=baseline_profile("1D")
    rows=[]
    for x in [0.4,0.5,0.6,0.7,0.8,0.9,1.0]:
        p=dict(base); p["tight"]=x
        rows.append(evaluate(frames,b,p,"macd_tighten"))
    return {"version":"scan13-1d-tight-plateau-v2","period":"1D","entry":ENTRY,"signal_count":count,"rows":rows,
            "warning":"Historical observed data; future unseen bars are true forward validation."}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    d=analyze(a.db); p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__': main()
