"""Compact SAT robustness for Scan 11 frozen entry B.

Same exit families as scan11_sat_robustness.py, but only a compact and
interpretable neighborhood is explored after the family comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scan11_sat_robustness import (
    load_frames,
    bounds_for,
    baseline_profile,
    evaluate,
    score_key,
)

PERIODS = ("4H", "1D", "1W")


def compact_neighbors(period, base):
    rows = []
    def add(**kw):
        p = dict(base)
        p.update(kw)
        key = tuple(sorted(p.items()))
        if key not in seen:
            seen.add(key); rows.append(p)
    seen=set()
    add()
    add(swing=int(base['swing'])+2)
    add(buffer=round(max(.05,float(base['buffer'])-.05),2))
    add(buffer=round(float(base['buffer'])+.05,2))
    add(trail=round(max(1.0,float(base['trail'])-.2),2))
    add(trail=round(float(base['trail'])+.2,2))
    add(tp1=1.1,tp2=2.2,tp3=3.3)
    add(max_hold=int(base['max_hold'])+20)
    add(swing=int(base['swing'])+2,tp1=1.1,tp2=2.2,tp3=3.3)
    add(swing=int(base['swing'])+2,buffer=round(float(base['buffer'])+.05,2),trail=round(max(1.0,float(base['trail'])-.2),2),tp1=1.1,tp2=2.2,tp3=3.3)
    add(swing=int(base['swing'])+2,buffer=round(max(.05,float(base['buffer'])-.05),2),trail=round(float(base['trail'])+.2,2),tp1=1.1,tp2=2.2,tp3=3.3)
    return rows


def analyze(db,period):
    frames,times,count=load_frames(db,period)
    b=bounds_for(times)
    base=baseline_profile(period)
    fams=['structural','bb_tighten','bb_macd_hard','adaptive']
    fr=[evaluate(frames,b,dict(base),f,period) for f in fams]
    fr.sort(key=score_key,reverse=True)
    winner=fr[0]['family']
    cand=[evaluate(frames,b,p,winner,period) for p in compact_neighbors(period,base)]
    if winner in {'bb_tighten','adaptive'}:
        for delta in (-.2,.2):
            p=dict(base);p['tight']=round(max(.8,float(base['tight'])+delta),2)
            cand.append(evaluate(frames,b,p,winner,period))
    cand.sort(key=score_key,reverse=True)
    return {
      'version':'scan11-sat-fast-v1','period':period,'signal_count':count,
      'family_baselines':fr,'family_winner':winner,'compact_candidates':cand,
      'note':'Final adoption applies materiality and complexity gate; diagnostic rank alone is not final.',
      'warning':'Historical observed data; future unseen bars are true forward validation.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--period',choices=PERIODS,required=True);ap.add_argument('--output',required=True);a=ap.parse_args()
    d=analyze(a.db,a.period);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
