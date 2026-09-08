"""SAT robustness for Scan 14 MACD DipDonusu."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
from scan14_entry_abc import indicators, entry_events  # noqa: E402

_BB = Path(__file__).resolve().parents[1] / "bb_squeeze"
sys.path.insert(0, str(_BB))
from bb_squeeze_entry_stage import (  # noqa: E402
    MarketDataStore,
    WARMUP,
    structure,
    initial_stop,
    metrics,
    bounds_for,
)

PERIODS = ("4H", "1D", "1W", "1M")
ENTRY_BY_PERIOD = {
    "4H": [
        {"name": "C_strong_rvol_1_50", "mode": "C", "rvol_min": 1.50},
    ],
    "1D": [
        {"name": "A_no_rvol", "mode": "A", "rvol_min": None},
        {"name": "C_strong_rvol_1_50", "mode": "C", "rvol_min": 1.50},
    ],
    "1W": [
        {"name": "A_no_rvol", "mode": "A", "rvol_min": None},
        {"name": "C_strong_rvol_1_50", "mode": "C", "rvol_min": 1.50},
    ],
    "1M": [
        {"name": "A_no_rvol", "mode": "A", "rvol_min": None},
    ],
}
BASE_TIGHT = {"4H": 1.5, "1D": 1.6, "1W": 1.8, "1M": 2.0}


def baseline_profile(period: str) -> dict[str, Any]:
    p = structure(period)
    p.update({"tp1": 1.0, "tp2": 2.0, "tp3": 3.0, "tight": BASE_TIGHT[period]})
    return p


def simulate(d: pd.DataFrame, sp: int, p: dict[str, Any], family: str) -> dict[str, Any] | None:
    ep = sp + 1
    if ep >= len(d):
        return None
    entry = float(d["open"].iloc[ep])
    if not np.isfinite(entry) or entry <= 0:
        return None

    stop, risk = initial_stop(d, sp, entry, p)
    tp1 = entry + risk * float(p["tp1"])
    tp2 = entry + risk * float(p["tp2"])
    tp3 = entry + risk * float(p["tp3"])

    remaining = 1.0
    cash = 0.0
    h1 = h2 = h3 = False
    trail = False
    tight = False
    highest = entry
    minlow = entry
    maxhigh = entry
    last = min(len(d)-1, ep + int(p["max_hold"]) - 1)
    exit_pos = ep
    reason = "TIME"

    for pos in range(ep, last+1):
        row = d.iloc[pos]
        hi = float(row["high"]); lo = float(row["low"]); cl = float(row["close"])
        highest = max(highest, hi); maxhigh = max(maxhigh, hi); minlow = min(minlow, lo)

        if lo <= stop:
            cash += remaining * stop
            remaining = 0.0
            exit_pos = pos
            reason = "TRAIL" if (trail or tight) else "STOP"
            break

        if not h1 and hi >= tp1:
            q = min(remaining, .30); cash += q * tp1; remaining -= q; h1 = True
        if remaining > 1e-12 and not h2 and hi >= tp2:
            q = min(remaining, .30); cash += q * tp2; remaining -= q; h2 = True; trail = True
        if remaining > 1e-12 and not h3 and hi >= tp3:
            q = min(remaining, .20); cash += q * tp3; remaining -= q; h3 = True

        m = float(row["macd"]) if pd.notna(row["macd"]) else np.nan
        s = float(row["macd_signal"]) if pd.notna(row["macd_signal"]) else np.nan
        weak = np.isfinite(m) and np.isfinite(s) and m < s
        failed_below_zero = weak and np.isfinite(m) and m < 0.0

        if family == "macd_tighten" and weak:
            tight = True
        elif family == "fail_tighten" and failed_below_zero:
            tight = True

        hard = False
        if family == "macd_hard":
            hard = weak
        elif family == "fail_hard":
            hard = failed_below_zero

        if remaining > 1e-12 and hard:
            cash += remaining * cl
            remaining = 0.0
            exit_pos = pos
            reason = "TECH"
            break

        if remaining > 1e-12 and (trail or tight):
            a = float(row["atr14"])
            if np.isfinite(a) and a > 0:
                mult = float(p["tight"] if tight else p["trail"])
                stop = max(stop, highest - mult * a)

        if pos == last and remaining > 1e-12:
            cash += remaining * cl
            remaining = 0.0
            exit_pos = pos
            reason = "TIME"
            break

    pnl = cash - entry
    return {
        "signal_time": pd.Timestamp(d.index[sp]),
        "entry_time": pd.Timestamp(d.index[ep]),
        "exit_time": pd.Timestamp(d.index[exit_pos]),
        "entry": entry,
        "risk": risk,
        "realized_r": pnl / risk,
        "mfe_r": (maxhigh-entry) / risk,
        "mae_r": (minlow-entry) / risk,
        "tp1_hit": h1,
        "tp2_hit": h2,
        "tp3_hit": h3,
        "exit_reason": reason,
        "exit_pos": exit_pos,
    }


def load_frames(db: str, period: str, entry: dict[str, Any]):
    frames = []
    times: list[pd.Timestamp] = []
    count = 0
    with MarketDataStore(db, read_only=True) as store:
        syms = store.list_symbols("BIST", period)
        for i, sym in enumerate(syms, 1):
            fr = store.load_dataframe(sym, "BIST", period, limit=0)
            if fr is None or len(fr) <= WARMUP + 22:
                continue
            d = indicators(fr)
            ev = entry_events(d, entry)
            ps = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x >= WARMUP and x+1 < len(d)]
            if ps:
                frames.append((sym, d, ps))
                times.extend(pd.Timestamp(d.index[x]) for x in ps)
                count += len(ps)
            if i % 100 == 0 or i == len(syms):
                print(f"[{period}/{entry['mode']}] {i}/{len(syms)}", flush=True)
    times.sort()
    return frames, times, count


def collect(frames, p, family, start, end):
    out = []
    for sym, d, ps in frames:
        last_exit = -1
        for sp in ps:
            st = pd.Timestamp(d.index[sp])
            if st < start:
                continue
            if st >= end:
                break
            if sp <= last_exit:
                continue
            t = simulate(d, sp, p, family)
            if t is None:
                continue
            if pd.Timestamp(t["exit_time"]) >= end:
                continue
            t["symbol"] = sym
            out.append(t)
            last_exit = int(t["exit_pos"])
    out.sort(key=lambda x: x["entry_time"])
    return out


def evaluate(frames, bounds, p, family):
    folds = []; stitched = []
    for i in range(4):
        tr = collect(frames, p, family, bounds[i], bounds[i+1])
        stitched.extend(tr)
        folds.append({"fold": i+1, "metrics": metrics(tr)})
    sm = metrics(stitched)
    ex = [float(x["metrics"].get("expectancy_r", 0.0)) for x in folds]
    return {
        "family": family,
        "profile": p,
        "folds": folds,
        "stitched": sm,
        "positive_folds": sum(x > 0 for x in ex),
        "worst_fold_expectancy_r": float(min(ex)),
        "median_fold_expectancy_r": float(np.median(ex)),
    }


def score_key(row):
    s = row["stitched"]
    return (
        int(row["positive_folds"]),
        float(row["worst_fold_expectancy_r"]),
        float(row["median_fold_expectancy_r"]),
        float(s.get("expectancy_r", 0.0)),
        float(s.get("profit_factor") or 0.0),
    )


def compact_neighbors(period: str, base: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []; seen = set()
    def add(**kw):
        p = dict(base); p.update(kw)
        key = tuple(sorted(p.items()))
        if key not in seen:
            seen.add(key); rows.append(p)
    add()
    add(swing=int(base["swing"])+2)
    add(buffer=round(max(.05, float(base["buffer"])-.05), 2))
    add(buffer=round(float(base["buffer"])+.05, 2))
    add(trail=round(max(1.0, float(base["trail"])-.2), 2))
    add(trail=round(float(base["trail"])+.2, 2))
    add(tp1=1.1, tp2=2.2, tp3=3.3)
    add(max_hold=int(base["max_hold"])+(12 if period=="1M" else 20))
    add(swing=int(base["swing"])+2, tp1=1.1, tp2=2.2, tp3=3.3)
    add(swing=int(base["swing"])+2, buffer=round(float(base["buffer"])+.05,2), trail=round(max(1.0,float(base["trail"])-.2),2), tp1=1.1,tp2=2.2,tp3=3.3)
    return rows


def analyze_entry(db: str, period: str, entry: dict[str, Any]):
    frames, times, signal_count = load_frames(db, period, entry)
    b = bounds_for(times)
    if not b:
        return {"entry": entry, "signal_count": signal_count, "error": "insufficient bounds"}
    base = baseline_profile(period)
    families = ["structural", "macd_tighten", "fail_tighten", "macd_hard", "fail_hard"]
    fam = [evaluate(frames, b, dict(base), f) for f in families]
    fam.sort(key=score_key, reverse=True)
    winner = fam[0]["family"]

    candidates = []
    if period != "1M":
        candidates = [evaluate(frames, b, p, winner) for p in compact_neighbors(period, base)]
        if winner in {"macd_tighten", "fail_tighten"}:
            for x in sorted(set([max(.8, BASE_TIGHT[period]-.4), max(.8, BASE_TIGHT[period]-.2), BASE_TIGHT[period], BASE_TIGHT[period]+.2])):
                p = dict(base); p["tight"] = round(x,2)
                candidates.append(evaluate(frames, b, p, winner))
        candidates.sort(key=score_key, reverse=True)

    return {
        "entry": entry,
        "signal_count": signal_count,
        "family_baselines": fam,
        "family_winner": winner,
        "compact_candidates": candidates[:20],
    }


def analyze(db: str, period: str) -> dict[str, Any]:
    rows = [analyze_entry(db, period, e) for e in ENTRY_BY_PERIOD[period]]
    return {
        "version": "scan14-sat-v1",
        "period": period,
        "entries": rows,
        "note": "Final adoption uses materiality/complexity gate; diagnostic rank alone is not final. 1M remains research-only.",
        "warning": "Historical observed data; future unseen bars are true forward validation.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    d = analyze(a.db, a.period)
    p = Path(a.output); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2, default=str)+"\n", encoding="utf-8")
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
