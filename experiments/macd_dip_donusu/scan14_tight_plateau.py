"""Tight-trail plateau for final Scan 14 candidates."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

_HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(_HERE))
from scan14_sat_robustness import load_frames, evaluate  # noqa: E402
from bb_squeeze_entry_stage import bounds_for  # noqa: E402

PERIODS=("4H","1D","1W")
ENTRY={
 "4H":[{"name":"C_strong_rvol_1_50","mode":"C","rvol_min":1.50}],
 "1D":[{"name":"A_no_rvol","mode":"A","rvol_min":None},{"name":"C_strong_rvol_1_50","mode":"C","rvol_min":1.50}],
 "1W":[{"name":"A_no_rvol","mode":"A","rvol_min":None},{"name":"C_strong_rvol_1_50","mode":"C","rvol_min":1.50}],
}
BASE={
 "4H":dict(stop_mode='swing',stop_atr=1.2,swing=7,buffer=.20,trail=2.0,max_hold=40,tp1=1.0,tp2=2.0,tp3=3.0),
 "1D":dict(stop_mode='swing',stop_atr=1.25,swing=7,buffer=.20,trail=2.2,max_hold=40,tp1=1.0,tp2=2.0,tp3=3.0),
 "1W":dict(stop_mode='swing',stop_atr=1.3,swing=11,buffer=.15,trail=2.3,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3),
}
TIGHT={
 "4H":[0.6,0.8,1.0,1.1,1.2,1.3,1.4,1.5,1.6],
 "1D":[0.6,0.8,1.0,1.2,1.4,1.6,1.8],
 "1W":[1.0,1.2,1.4,1.6,1.8,2.0,2.2],
}

def score(r):
    m=r['stitched']
    return (r['positive_folds'],r['worst_fold_expectancy_r'],m.get('expectancy_r',0),m.get('profit_factor') or 0)

def analyze(db:str,period:str)->dict[str,Any]:
    out=[]
    for entry in ENTRY[period]:
        frames,times,count=load_frames(db,period,entry)
        b=bounds_for(times)
        rows=[]
        for x in TIGHT[period]:
            p=dict(BASE[period]);p['tight']=float(x)
            r=evaluate(frames,b,p,'fail_tighten')
            rows.append(r)
        rows.sort(key=score,reverse=True)
        out.append({'entry':entry,'signal_count':count,'rows':rows,'best':rows[0] if rows else None})
    return {'version':'scan14-tight-plateau-v1','period':period,'family':'fail_tighten','entries':out,'note':'Final choice uses plateau/materiality and sample-size judgement, not boundary optimum alone.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--period',choices=PERIODS,required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    d=analyze(a.db,a.period);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
