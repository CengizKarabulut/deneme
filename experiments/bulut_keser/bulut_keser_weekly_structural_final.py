"""Final narrow structural-only optimization for frozen 1W BulutKeser entry.

This exists because the broad SAT stage preferred Ichimoku tightening by worst-fold
while sacrificing too much total expectancy. Here only the already-strong structural
family is searched, and any accepted profile must preserve total expectancy.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from bulut_keser_sat_robustness import load_frames,evaluate,BASE
from bulut_keser_cloud_stage import bounds_for

ENTRY='above__adx_20_35__bb_none__rv15'
PERIOD='1W'

def profiles():
    base=dict(BASE['1W']); out=[]
    for swing in (7,9,11):
        for buffer in (.10,.15,.20):
            for trail in (2.1,2.3,2.5):
                for targets in ((1.,2.,3.),(1.1,2.2,3.3)):
                    for hold in (60,80):
                        p=dict(base);p.update(swing=swing,buffer=buffer,trail=trail,tight=max(1.2,trail-.6),tp1=targets[0],tp2=targets[1],tp3=targets[2],max_hold=hold);out.append(p)
    return out

def analyze(db):
    frames,times,count=load_frames(db,PERIOD,ENTRY); b=bounds_for(times); base=dict(BASE['1W']); baseline=evaluate(frames,ENTRY,base,'structural',PERIOD,b)
    rows=[evaluate(frames,ENTRY,p,'structural',PERIOD,b) for p in profiles()]
    be=float(baseline['stitched'].get('expectancy_r',0)); bw=float(baseline['worst_fold_expectancy_r'])
    # Preserve total edge: candidate cannot lose >0.01R expectancy versus baseline.
    eligible=[r for r in rows if r['positive_folds']==4 and float(r['stitched'].get('expectancy_r',0))>=be-.01]
    eligible.sort(key=lambda r:(r['worst_fold_expectancy_r'],float(r['stitched'].get('expectancy_r',0)),float(r['stitched'].get('profit_factor') or 0)),reverse=True)
    best=eligible[0] if eligible else baseline
    oe=float(best['stitched'].get('expectancy_r',0)); ow=float(best['worst_fold_expectancy_r'])
    material=((oe-be)>=.03 or (ow-bw)>=.025) and oe>=be-.01
    final=best if material else baseline
    rows.sort(key=lambda r:(r['positive_folds'],r['worst_fold_expectancy_r'],float(r['stitched'].get('expectancy_r',0))),reverse=True)
    return {'version':'bulut-keser-1w-structural-final-v1','period':PERIOD,'entry_frozen':ENTRY,'signal_count':count,'baseline':baseline,'top10':rows[:10],'best_eligible':best,'material_change_accepted':material,'final':final}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();d=analyze(a.db);p=Path(a.output);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(d,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
