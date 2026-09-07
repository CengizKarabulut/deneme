"""Final tight-trail plateau check for Scan 11 B on 4H and 1D."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from scan11_sat_robustness import load_frames,bounds_for,evaluate

PROFILES={
 '4H':dict(stop_mode='swing',stop_atr=1.2,swing=9,buffer=.25,trail=1.8,max_hold=40,tp1=1.1,tp2=2.2,tp3=3.3,tight=1.3),
 '1D':dict(stop_mode='swing',stop_atr=1.25,swing=7,buffer=.25,trail=2.0,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3,tight=1.4),
}
VALUES=[1.0,1.1,1.2,1.3,1.4,1.5,1.6]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--period',choices=['4H','1D'],required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
 frames,times,count=load_frames(a.db,a.period);b=bounds_for(times);rows=[]
 for x in VALUES:
  p=dict(PROFILES[a.period]);p['tight']=x;rows.append(evaluate(frames,b,p,'bb_tighten',a.period))
 d={'version':'scan11-tight-plateau-v1','period':a.period,'signal_count':count,'rows':rows,'warning':'Observed historical data; future unseen bars are true forward validation.'}
 p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
