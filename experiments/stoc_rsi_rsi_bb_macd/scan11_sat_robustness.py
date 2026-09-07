"""SAT robustness for frozen Scan 11 entry B.

Entry B is frozen:
RSI14>30 + Close fresh-crosses BB20 Basis + StochRSI K>D + MACD>Signal + RVOL20>1.5.

Exit families are compared first at baseline geometry, then a narrow structural
neighborhood is evaluated. No TP1 break-even is used in this stage.
"""
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
from scan11_entry_ab import indicators, entry_events  # noqa: E402

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

PERIODS = ("4H", "1D", "1W")
ENTRY = {"name": "B_bb_reclaim_with_momentum_confirm", "mode": "B"}

BASE_TIGHT = {"4H": 1.5, "1D": 1.6, "1W": 1.8}


def baseline_profile(period: str) -> dict[str, Any]:
    p = structure(period)
    p.update({"tp1": 1.0, "tp2": 2.0, "tp3": 3.0, "tight": BASE_TIGHT[period]})
    return p


def simulate(d: pd.DataFrame, sp: int, p: dict[str, Any], family: str, period: str) -> dict[str, Any] | None:
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
        hi = float(row["high"])
        lo = float(row["low"])
        cl = float(row["close"])
        highest = max(highest, hi)
        maxhigh = max(maxhigh, hi)
        minlow = min(minlow, lo)

        # Conservative same-bar ambiguity: stop first.
        if lo <= stop:
            cash += remaining * stop
            remaining = 0.0
            exit_pos = pos
            reason = "TRAIL" if (trail or tight) else "STOP"
            break

        if not h1 and hi >= tp1:
            q = min(remaining, .30)
            cash += q * tp1
            remaining -= q
            h1 = True
        if remaining > 1e-12 and not h2 and hi >= tp2:
            q = min(remaining, .30)
            cash += q * tp2
            remaining -= q
            h2 = True
            trail = True
        if remaining > 1e-12 and not h3 and hi >= tp3:
            q = min(remaining, .20)
            cash += q * tp3
            remaining -= q
            h3 = True

        basis = float(row["bb_basis"]) if pd.notna(row["bb_basis"]) else np.nan
        macd = float(row["macd"]) if pd.notna(row["macd"]) else np.nan
        sig = float(row["macd_signal"]) if pd.notna(row["macd_signal"]) else np.nan
        basis_loss = np.isfinite(basis) and cl < basis
        macd_weak = np.isfinite(macd) and np.isfinite(sig) and macd < sig

        if family in {"bb_tighten", "adaptive"} and basis_loss:
            tight = True

        hard = False
        if family == "bb_macd_hard":
            hard = basis_loss and macd_weak
        elif family == "adaptive":
            hard = basis_loss and macd_weak

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


def load_frames(db: str, period: str):
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
            ev = entry_events(d, ENTRY)
            ps = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x >= WARMUP and x+1 < len(d)]
            if ps:
                frames.append((sym, d, ps))
                times.extend(pd.Timestamp(d.index[x]) for x in ps)
                count += len(ps)
            if i % 100 == 0 or i == len(syms):
                print(f"[{period}] {i}/{len(syms)}", flush=True)
    times.sort()
    return frames, times, count


def collect(frames, p, family, period, start, end):
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
            t = simulate(d, sp, p, family, period)
            if t is None:
                continue
            if pd.Timestamp(t["exit_time"]) >= end:
                continue
            t["symbol"] = sym
            out.append(t)
            last_exit = int(t["exit_pos"])
    out.sort(key=lambda x: x["entry_time"])
    return out


def evaluate(frames, bounds, p, family, period):
    folds = []
    stitched = []
    for i in range(4):
        tr = collect(frames, p, family, period, bounds[i], bounds[i+1])
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


def profile_neighbors(period: str) -> list[dict[str, Any]]:
    base = baseline_profile(period)
    swings = [int(base["swing"]), int(base["swing"]) + 2]
    buffers = sorted(set([max(0.05, float(base["buffer"])-0.05), float(base["buffer"]), float(base["buffer"])+0.05]))
    trails = sorted(set([max(1.0, float(base["trail"])-0.2), float(base["trail"]), float(base["trail"])+0.2]))
    holds = [int(base["max_hold"]), int(base["max_hold"] + (20 if period != "1W" else 20))]
    targets = [(1.0,2.0,3.0), (1.1,2.2,3.3)]
    rows = []
    for sw in swings:
        for buf in buffers:
            for tr in trails:
                for hold in holds:
                    for t1,t2,t3 in targets:
                        p = dict(base)
                        p.update({"swing": sw, "buffer": round(buf,2), "trail": round(tr,2), "max_hold": hold, "tp1": t1, "tp2": t2, "tp3": t3})
                        rows.append(p)
    return rows


def score_key(row):
    s = row["stitched"]
    return (
        int(row["positive_folds"]),
        float(row["worst_fold_expectancy_r"]),
        float(row["median_fold_expectancy_r"]),
        float(s.get("expectancy_r", 0.0)),
        float(s.get("profit_factor") or 0.0),
    )


def analyze(db: str, period: str) -> dict[str, Any]:
    frames, times, signal_count = load_frames(db, period)
    bounds = bounds_for(times)
    if not bounds:
        return {"version":"scan11-sat-v1", "period":period, "signal_count":signal_count, "error":"insufficient bounds"}

    base = baseline_profile(period)
    families = ["structural", "bb_tighten", "bb_macd_hard", "adaptive"]
    family_rows = [evaluate(frames, bounds, dict(base), fam, period) for fam in families]
    family_rows.sort(key=score_key, reverse=True)
    family_winner = family_rows[0]["family"]

    # Narrow geometry around the winning family.
    narrow_rows = [evaluate(frames, bounds, p, family_winner, period) for p in profile_neighbors(period)]
    narrow_rows.sort(key=score_key, reverse=True)
    best_geometry = narrow_rows[0]

    # Tight-multiplier neighborhood only when the chosen family uses it.
    tight_rows = []
    if family_winner in {"bb_tighten", "adaptive"}:
        center = float(best_geometry["profile"]["tight"])
        for x in sorted(set([max(0.8, center-0.2), center, center+0.2])):
            p = dict(best_geometry["profile"])
            p["tight"] = round(x,2)
            tight_rows.append(evaluate(frames, bounds, p, family_winner, period))
        tight_rows.sort(key=score_key, reverse=True)

    return {
        "version": "scan11-sat-v1",
        "period": period,
        "entry_frozen": ENTRY["name"],
        "signal_count": signal_count,
        "family_baselines": family_rows,
        "family_winner": family_winner,
        "narrow_top10": narrow_rows[:10],
        "tight_rows": tight_rows,
        "note": "Candidate ranking is diagnostic. Final adoption uses a materiality/complexity gate, not lexicographic rank alone.",
        "warning": "Historical observed data; future unseen bars are true forward validation.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    result = analyze(a.db, a.period)
    p = Path(a.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
