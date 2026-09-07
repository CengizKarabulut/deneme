"""Narrow structural SAT robustness optimization for scan #2.

Entry rules are frozen from the previous fixed-entry robustness study:
- 1D: B_stoch_trigger = StochRSI K crosses above D AND MOM10 > 0
- 1W: C_momentum_trigger = MOM10 crosses above 0 AND StochRSI K > D
- 1M: C_momentum_trigger = MOM10 crosses above 0 AND StochRSI K > D

The volume rule remains frozen:
    Volume[t] > mean(Volume[t-1] ... Volume[t-10])

Only a narrow, interpretable neighborhood of the structural exit is tested.
Selection favors a stable parameter plateau across four chronological windows,
not the single highest historical score. The baseline is retained unless a
candidate improves materially without weakening the worst chronological fold.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_data_store import MarketDataStore
from stoch_momentum_volume_wf import (
    WARMUP,
    BOUNDARIES,
    indicators,
    entry_events,
    exit_variants,
    collect,
    metrics,
)

PERIODS = ("1D", "1W", "1M")
ENTRY_BY_PERIOD = {
    "1D": "B_stoch_trigger",
    "1W": "C_momentum_trigger",
    "1M": "C_momentum_trigger",
}


def structural_control(period: str) -> dict[str, Any]:
    rows = [x for x in exit_variants(period) if x["name"] == "structural_control"]
    if not rows:
        raise RuntimeError("structural_control missing")
    return dict(rows[0])


def grid_values(period: str, base: dict[str, Any]) -> dict[str, list[Any]]:
    swing = int(base["swing"])
    buffer = float(base["buffer"])
    trail = float(base["trail"])
    return {
        "swing": [max(3, swing - 2), swing, swing + 2],
        "buffer": [round(max(0.0, buffer - 0.05), 4), round(buffer, 4), round(buffer + 0.05, 4)],
        "trail": [round(max(0.8, trail - 0.20), 4), round(trail, 4), round(trail + 0.20, 4)],
    }


def tp_families() -> list[tuple[str, tuple[float, float, float]]]:
    return [
        ("near_fast", (0.9, 1.8, 2.7)),
        ("baseline", (1.0, 2.0, 3.0)),
        ("near_wide", (1.1, 2.2, 3.3)),
    ]


def load_frames(db: str, period: str, entry_name: str):
    frames = []
    all_times: list[pd.Timestamp] = []
    count = 0
    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", period)
        for i, symbol in enumerate(symbols, 1):
            frame = store.load_dataframe(symbol, "BIST", period, limit=0)
            if frame is None or len(frame) <= WARMUP + 22:
                continue
            data = indicators(frame)
            ev = entry_events(data, entry_name)
            positions = [
                int(x) for x in np.flatnonzero(ev.to_numpy(bool))
                if x >= WARMUP and x + 1 < len(data)
            ]
            if positions:
                frames.append((symbol, data, {entry_name: positions}))
                count += len(positions)
                all_times.extend(pd.Timestamp(data.index[x]) for x in positions)
            if i % 100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)} loaded", flush=True)
    all_times.sort()
    return frames, all_times, count


def chronological_bounds(all_times: list[pd.Timestamp]) -> list[pd.Timestamp]:
    if len(all_times) < 80:
        return []
    bounds = [
        pd.Timestamp(all_times[min(len(all_times) - 1, int(len(all_times) * q))])
        for q in BOUNDARIES[:-1]
    ]
    bounds.append(pd.Timestamp(all_times[-1]) + pd.Timedelta(days=3700))
    return bounds


def evaluate(frames, entry_name: str, p: dict[str, Any], bounds: list[pd.Timestamp]) -> dict[str, Any]:
    folds = []
    stitched = []
    for fi in range(4):
        tr = collect(frames, entry_name, p, start=bounds[fi], end=bounds[fi + 1])
        m = metrics(tr)
        stitched.extend(tr)
        folds.append({
            "fold": fi + 1,
            "start": bounds[fi].isoformat(),
            "end": bounds[fi + 1].isoformat(),
            "metrics": m,
        })
    sm = metrics(stitched)
    exps = [float(f["metrics"].get("expectancy_r", 0.0)) for f in folds]
    pfs = [float(f["metrics"].get("profit_factor") or 0.0) for f in folds]
    return {
        "params": {k: p[k] for k in ("swing", "buffer", "trail", "max_hold", "tp1", "tp2", "tp3")},
        "folds": folds,
        "stitched": sm,
        "positive_folds": sum(x > 0 for x in exps),
        "pf_above_1_folds": sum(x > 1 for x in pfs),
        "worst_fold_expectancy_r": float(min(exps)),
        "median_fold_expectancy_r": float(np.median(exps)),
    }


def quality(row: dict[str, Any]) -> float:
    m = row["stitched"]
    pf = max(float(m.get("profit_factor") or 0.0), 1e-9)
    exp = float(m.get("expectancy_r", 0.0))
    worst = float(row["worst_fold_expectancy_r"])
    median = float(row["median_fold_expectancy_r"])
    pos = int(row["positive_folds"])
    # Worst/median fold dominate; aggregate PF is intentionally low-weight.
    return 4.0 * pos + 2.5 * worst + 1.5 * median + 0.75 * exp + 0.20 * math.log(pf)


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for r in rows:
        r["quality_score"] = quality(r)
    return sorted(
        rows,
        key=lambda r=(None): 0,
    )


def sorted_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for r in rows:
        r["quality_score"] = quality(r)
    return sorted(
        rows,
        key=lambda r: (
            int(r["positive_folds"]),
            float(r["worst_fold_expectancy_r"]),
            float(r["median_fold_expectancy_r"]),
            float(r["stitched"].get("expectancy_r", 0.0)),
            float(r["stitched"].get("profit_factor") or 0.0),
        ),
        reverse=True,
    )


def plateau_pick(rows: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    ranked = sorted_rows(rows)
    eligible = [r for r in ranked if int(r["positive_folds"]) == 4 and float(r["worst_fold_expectancy_r"]) > 0]
    pool = eligible if eligible else ranked
    n = max(3, min(9, int(math.ceil(len(pool) * 0.25))))
    top = pool[:n]

    centers: dict[str, float] = {}
    scales: dict[str, float] = {}
    for k in keys:
        vals = np.array([float(r["params"][k]) for r in top], dtype=float)
        centers[k] = float(np.median(vals))
        uniq = sorted(set(float(r["params"][k]) for r in rows))
        if len(uniq) >= 2:
            diffs = [b - a for a, b in zip(uniq[:-1], uniq[1:]) if b > a]
            scales[k] = float(np.median(diffs)) if diffs else 1.0
        else:
            scales[k] = 1.0

    def distance(r):
        d = 0.0
        for k in keys:
            d += abs(float(r["params"][k]) - centers[k]) / max(scales[k], 1e-9)
        return d

    chosen = sorted(
        top,
        key=lambda r: (
            distance(r),
            -float(r["worst_fold_expectancy_r"]),
            -float(r["median_fold_expectancy_r"]),
            -float(r["stitched"].get("expectancy_r", 0.0)),
        ),
    )[0]
    return {
        "chosen": chosen,
        "plateau_center": centers,
        "top_plateau_rows": top,
    }


def material_improvement(candidate: dict[str, Any], baseline: dict[str, Any]) -> tuple[bool, dict[str, float]]:
    cm, bm = candidate["stitched"], baseline["stitched"]
    de = float(cm.get("expectancy_r", 0.0)) - float(bm.get("expectancy_r", 0.0))
    dpf = float(cm.get("profit_factor") or 0.0) - float(bm.get("profit_factor") or 0.0)
    dworst = float(candidate["worst_fold_expectancy_r"]) - float(baseline["worst_fold_expectancy_r"])
    stable = int(candidate["positive_folds"]) == 4 and float(candidate["worst_fold_expectancy_r"]) > 0
    not_weaker = dworst >= -0.02
    material = de >= 0.03 or dpf >= 0.10
    return bool(stable and not_weaker and material), {
        "delta_expectancy_r": de,
        "delta_profit_factor": dpf,
        "delta_worst_fold_expectancy_r": dworst,
    }


def analyze(db: str, period: str) -> dict[str, Any]:
    entry_name = ENTRY_BY_PERIOD[period]
    base = structural_control(period)
    frames, all_times, signal_count = load_frames(db, period, entry_name)
    bounds = chronological_bounds(all_times)
    if not bounds:
        return {"period": period, "classification": "INSUFFICIENT_SAMPLE", "signal_count": signal_count}

    baseline = evaluate(frames, entry_name, base, bounds)
    baseline["label"] = "baseline"

    # Stage A: geometry only, 3 x 3 x 3 = 27 candidates.
    gv = grid_values(period, base)
    stage_a_rows = []
    for swing in gv["swing"]:
        for buffer in gv["buffer"]:
            for trail in gv["trail"]:
                p = dict(base)
                p.update({"swing": int(swing), "buffer": float(buffer), "trail": float(trail)})
                row = evaluate(frames, entry_name, p, bounds)
                row["label"] = f"geom_s{swing}_b{buffer:.2f}_t{trail:.2f}"
                stage_a_rows.append(row)
    stage_a = plateau_pick(stage_a_rows, ("swing", "buffer", "trail"))
    geom = stage_a["chosen"]

    # Stage B: only 9 candidates around the chosen geometry.
    geom_params = geom["params"]
    holds = sorted(set([
        max(8, int(round(float(base["max_hold"]) * 0.80))),
        int(base["max_hold"]),
        int(round(float(base["max_hold"]) * 1.20)),
    ]))
    stage_b_rows = []
    for tp_name, tps in tp_families():
        for hold in holds:
            p = dict(base)
            p.update({
                "swing": int(geom_params["swing"]),
                "buffer": float(geom_params["buffer"]),
                "trail": float(geom_params["trail"]),
                "max_hold": int(hold),
                "tp1": float(tps[0]),
                "tp2": float(tps[1]),
                "tp3": float(tps[2]),
            })
            row = evaluate(frames, entry_name, p, bounds)
            row["label"] = f"{tp_name}_hold{hold}"
            row["tp_family"] = tp_name
            stage_b_rows.append(row)
    stage_b = plateau_pick(stage_b_rows, ("tp1", "tp2", "tp3", "max_hold"))
    candidate = stage_b["chosen"]

    adopt, delta = material_improvement(candidate, baseline)
    final = candidate if adopt else baseline
    decision = "ADOPT_NARROW_OPTIMIZED" if adopt else "KEEP_BASELINE"

    return {
        "version": "stoch-mom-vol-sat-robustness-v1",
        "period": period,
        "entry_rule_frozen": entry_name,
        "volume_rule_frozen": "Volume[t] > mean(previous 10 same-TF bars), current bar excluded",
        "method": "Frozen entry; costs included; four chronological windows; 27-candidate geometry neighborhood then 9-candidate TP/max-hold neighborhood; plateau selection; baseline changed only for material robust improvement.",
        "signal_count_full_history": signal_count,
        "baseline": baseline,
        "stage_a_geometry": {
            "grid": gv,
            "chosen": stage_a["chosen"],
            "plateau_center": stage_a["plateau_center"],
            "top_plateau_rows": stage_a["top_plateau_rows"],
            "all_ranked": sorted_rows(stage_a_rows),
        },
        "stage_b_tp_hold": {
            "hold_values": holds,
            "tp_families": [{"name": n, "tp": list(v)} for n, v in tp_families()],
            "chosen": stage_b["chosen"],
            "plateau_center": stage_b["plateau_center"],
            "top_plateau_rows": stage_b["top_plateau_rows"],
            "all_ranked": sorted_rows(stage_b_rows),
        },
        "candidate_vs_baseline": delta,
        "decision": decision,
        "final_profile": final,
        "warning": "Historical robustness on observed history; fresh forward monitoring remains required.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    payload = analyze(args.db, args.period)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
