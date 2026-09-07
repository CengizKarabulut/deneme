"""TP1 BE final check for the optimized weekly BulutKeser structural profile."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import bulut_keser_be_ab as core

core.FINAL['1W']=(
    '1W',
    'above__adx_20_35__bb_none__rv15',
    'structural',
    dict(stop_mode='swing',stop_atr=1.3,swing=11,buffer=.20,trail=2.5,tight=1.9,max_hold=80,tp1=1.1,tp2=2.2,tp3=3.3),
)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    d=core.analyze(a.db,'1W');d['version']='bulut-keser-weekly-be-final-v1'
    p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
