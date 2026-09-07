"""Final TP1 break-even A/B for scan #2.

Frozen final entry and structural profiles are tested with three stop-management
variants after TP1:
- no_be: keep the original structural stop until TP2 activates trailing
- entry_be: from the next bar after TP1, stop cannot be below entry
- cost_be: from the next bar after TP1, stop cannot be below true round-trip
  break-even after the modeled commission and slippage

The same four chronological windows and trading costs are used. Stop is checked
before targets on each OHLC bar; a TP1 hit can only tighten the stop for the
following bar, avoiding optimistic same-bar path assumptions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_data_store import MarketDataStore
from stoch_momentum_volume_wf import (
    WARMUP,
    BOUNDARIES,
    COMMISSION_BPS,
    SLIPPAGE_BPS,
    indicators,
    entry_events,
    exit_variants,
    initial_stop,
    metrics,
)

PERIODS = ("1D", "1W", "1M")
ENTRY_BY_PERIOD = {
    "1D": "B_stoch_trigger",
    "1W": "C_momentum_trigger",
    "1M": "C_momentum_trigger",
}
BE_MODES = ("no_be", "entry_be", "cost_be")


def final_profile(period: str) -> dict[str, Any]:
    rows = [x for x in exit_variants(period) if x["name"] == "structural_control"]
    if not rows:
        raise RuntimeError("structural_control missing")
    p = dict(rows[0])
    if period == "1M":
        # Adopted by the pre-declared narrow SAT robustness threshold.
        p.update({"swing": 7, "buffer": 0.15, "trail": 2.70, "max_hold": 36,
                  "tp1": 1.10, "tp2": 2.20, "tp3": 3.30})
    return p


def true_cost_break_even(entry: float) -> float:
    c = COMMISSION_BPS / 10000.0
    s = SLIPPAGE_BPS / 10000.0
    return entry * ((1.0 + s) * (1.0 + c)) / ((1.0 - s) * (1.0 - c))


def simulate(data: pd.DataFrame, signal_pos: int, p: dict[str, Any], be_mode: str):
    ep = signal_pos + 1
    if ep >= len(data):
        return None
    entry = float(data["open"].iloc[ep])
    if not np.isfinite(entry) or entry <= 0:
        return None
    stop, risk = initial_stop(data, signal_pos, entry, p)
    if risk <= 0:
        return None

    tp1 = entry + risk * float(p["tp1"])
    tp2 = entry + risk * float(p["tp2"])
    tp3 = entry + risk * float(p["tp3"])
    alloc = p["alloc"]
    remaining = 1.0
    cash = 0.0
    highest = entry
    min_low = entry
    max_high = entry
    tp1h = tp2h = tp3h = False
    trail_active = False
    exit_reason = "TIME"
    exit_pos = ep
    last = min(len(data) - 1, ep + int(p["max_hold"]) - 1)

    for pos in range(ep, last + 1):
        row = data.iloc[pos]
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        highest = max(highest, high)
        max_high = max(max_high, high)
        min_low = min(min_low, low)

        # Conservative same-bar rule: stop is evaluated before any target.
        if low <= stop:
            cash += remaining * stop
            remaining = 0.0
            exit_reason = "TRAIL" if trail_active or tp1h and be_mode != "no_be" else "STOP"
            exit_pos = pos
            break

        just_hit_tp1 = False
        if not tp1h and high >= tp1:
            q = min(remaining, alloc[0])
            cash += q * tp1
            remaining -= q
            tp1h = True
            just_hit_tp1 = True
        if remaining > 1e-12 and not tp2h and high >= tp2:
            q = min(remaining, alloc[1])
            cash += q * tp2
            remaining -= q
            tp2h = True
            trail_active = True
        if remaining > 1e-12 and not tp3h and high >= tp3:
            q = min(remaining, alloc[2])
            cash += q * tp3
            remaining -= q
            tp3h = True

        # No hard technical exit in the final structural_control profile.
        if remaining > 1e-12 and trail_active:
            a = float(row["atr14"])
            if np.isfinite(a) and a > 0:
                stop = max(stop, highest - float(p["trail"]) * a)

        # TP1 tightens stop only after this bar has fully resolved.
        if remaining > 1e-12 and tp1h and be_mode != "no_be":
            be = entry if be_mode == "entry_be" else true_cost_break_even(entry)
            stop = max(stop, be)

        if pos == last and remaining > 1e-12:
            cash += remaining * close
            remaining = 0.0
            exit_reason = "TIME"
            exit_pos = pos
            break

    pnl = cash - entry
    return {
        "signal_time": pd.Timestamp(data.index[signal_pos]),
        "entry_time": pd.Timestamp(data.index[ep]),
        "exit_time": pd.Timestamp(data.index[exit_pos]),
        "entry": entry,
        "risk": risk,
        "realized_r": pnl / risk,
        "return_pct": pnl / entry * 100.0,
        "mfe_r": (max_high - entry) / risk,
        "mae_r": (min_low - entry) / risk,
        "tp1_hit": tp1h,
        "tp2_hit": tp2h,
        "tp3_hit": tp3h,
        "exit_reason": exit_reason,
        "exit_pos": exit_pos,
    }


def load_frames(db: str, period: str, entry_name: str):
    frames = []
    all_times = []
    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", period)
        for i, symbol in enumerate(symbols, 1):
            frame = store.load_dataframe(symbol, "BIST", period, limit=0)
            if frame is None or len(frame) <= WARMUP + 22:
                continue
            data = indicators(frame)
            ev = entry_events(data, entry_name)
            positions = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x >= WARMUP and x + 1 < len(data)]
            if positions:
                frames.append((symbol, data, positions))
                all_times.extend(pd.Timestamp(data.index[x]) for x in positions)
            if i % 100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)} loaded", flush=True)
    all_times.sort()
    return frames, all_times


def bounds_from_times(all_times):
    if len(all_times) < 80:
        return []
    b = [pd.Timestamp(all_times[min(len(all_times)-1, int(len(all_times)*q))]) for q in BOUNDARIES[:-1]]
    b.append(pd.Timestamp(all_times[-1]) + pd.Timedelta(days=3700))
    return b


def collect(frames, p, be_mode, start, end):
    trades = []
    for symbol, data, positions in frames:
        last_exit = -1
        for signal_pos in positions:
            st = pd.Timestamp(data.index[signal_pos])
            if st < start:
                continue
            if st >= end:
                break
            if signal_pos <= last_exit:
                continue
            t = simulate(data, signal_pos, p, be_mode)
            if t is None:
                continue
            if pd.Timestamp(t["exit_time"]) >= end:
                continue
            t["symbol"] = symbol
            trades.append(t)
            last_exit = int(t["exit_pos"])
    trades.sort(key=lambda x: x["entry_time"])
    return trades


def evaluate(frames, p, be_mode, bounds):
    folds = []
    stitched = []
    for fi in range(4):
        tr = collect(frames, p, be_mode, bounds[fi], bounds[fi+1])
        m = metrics(tr)
        stitched.extend(tr)
        folds.append({"fold": fi+1, "metrics": m})
    sm = metrics(stitched)
    exps = [float(f["metrics"].get("expectancy_r", 0.0)) for f in folds]
    pfs = [float(f["metrics"].get("profit_factor") or 0.0) for f in folds]
    return {
        "be_mode": be_mode,
        "folds": folds,
        "stitched": sm,
        "positive_folds": sum(x > 0 for x in exps),
        "pf_above_1_folds": sum(x > 1 for x in pfs),
        "worst_fold_expectancy_r": float(min(exps)),
        "median_fold_expectancy_r": float(np.median(exps)),
    }


def decide(rows):
    base = next(r for r in rows if r["be_mode"] == "no_be")
    candidates = [r for r in rows if r["be_mode"] != "no_be"]
    candidates.sort(key=lambda r: (
        r["positive_folds"], r["worst_fold_expectancy_r"], r["median_fold_expectancy_r"],
        float(r["stitched"].get("expectancy_r",0)), float(r["stitched"].get("profit_factor") or 0)
    ), reverse=True)
    best = candidates[0]
    de = float(best["stitched"].get("expectancy_r",0)) - float(base["stitched"].get("expectancy_r",0))
    dpf = float(best["stitched"].get("profit_factor") or 0) - float(base["stitched"].get("profit_factor") or 0)
    dw = float(best["worst_fold_expectancy_r"]) - float(base["worst_fold_expectancy_r"])
    adopt = (
        best["positive_folds"] == 4
        and best["worst_fold_expectancy_r"] > 0
        and dw >= -0.02
        and (de >= 0.03 or dpf >= 0.10)
    )
    return {
        "decision": "ADOPT_" + best["be_mode"].upper() if adopt else "KEEP_NO_BE",
        "selected": best if adopt else base,
        "best_be_candidate": best,
        "delta_best_be_vs_no_be": {
            "expectancy_r": de,
            "profit_factor": dpf,
            "worst_fold_expectancy_r": dw,
        },
        "materiality_rule": "Adopt only if 4/4 positive, worst fold >0, worst-fold delta >= -0.02R, and expectancy +0.03R OR PF +0.10 vs no_be.",
    }


def analyze(db: str, period: str):
    entry = ENTRY_BY_PERIOD[period]
    p = final_profile(period)
    frames, times = load_frames(db, period, entry)
    bounds = bounds_from_times(times)
    if not bounds:
        return {"period": period, "classification": "INSUFFICIENT_SAMPLE"}
    rows = [evaluate(frames, p, mode, bounds) for mode in BE_MODES]
    decision = decide(rows)
    return {
        "version": "stoch-mom-vol-be-ab-v1",
        "period": period,
        "entry_rule_frozen": entry,
        "profile_frozen": {k:p[k] for k in ("swing","buffer","trail","max_hold","tp1","tp2","tp3")},
        "cost_break_even_factor": true_cost_break_even(1.0),
        "same_bar_policy": "STOP before TP; TP1 BE applies only after target bar resolves",
        "rows": rows,
        **decision,
        "warning": "Historical A/B on observed data; forward monitoring remains required.",
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()
    d = analyze(a.db, a.period)
    p = Path(a.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
