"""Final TP1 BE check after the material-improvement gate.

4H and 1D keep their simpler SAT baselines; 1W adopts the materially
improved narrow profile; 1M remains baseline research-only.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import bb_squeeze_be_ab as core

core.FINAL.update({
    '4H': dict(name='adaptive',rule='adaptive',stop_mode='swing',stop_atr=1.2,swing=7,buffer=.20,trail=2.0,tight=1.5,max_hold=40,tp1=1.,tp2=2.,tp3=3.),
    '1D': dict(name='structural',rule='none',stop_mode='swing',stop_atr=1.25,swing=7,buffer=.20,trail=2.2,tight=1.65,max_hold=40,tp1=1.,tp2=2.,tp3=3.),
    '1W': dict(name='structural',rule='none',stop_mode='swing',stop_atr=1.3,swing=9,buffer=.20,trail=2.3,tight=1.75,max_hold=60,tp1=1.1,tp2=2.2,tp3=3.3),
    '1M': dict(name='structural',rule='none',stop_mode='swing',stop_atr=1.3,swing=9,buffer=.15,trail=2.5,tight=1.9,max_hold=36,tp1=1.,tp2=2.,tp3=3.),
})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--db',required=True); ap.add_argument('--period',choices=core.PERIODS,required=True); ap.add_argument('--output',required=True); a=ap.parse_args()
    d=core.analyze(a.db,a.period); d['version']='bb-squeeze-be-final-v1'; d['profile_gate']='4H/1D keep baseline; 1W adopts material improvement; 1M baseline research-only'
    p=Path(a.output); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__': main()
