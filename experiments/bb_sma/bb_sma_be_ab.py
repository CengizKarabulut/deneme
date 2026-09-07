"""TP1 break-even A/B for frozen BB/SMA scan #3 profiles.

Compares:
- no_be: keep structural stop after TP1
- entry_be: from the next bar after TP1, stop >= entry
- cost_be: from the next bar after TP1, stop >= true round-trip cost break-even

All entry rules, exit-rule families and SAT parameters are frozen from the
previous robustness stages. This is the last risk-management check before lock.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from bb_sma_wf import (
    BOUNDARIES,
    COMMISSION_BPS,
    SLIPPAGE_BPS,
    WARMUP,
    MarketDataStore,
    entry_events,
    exit_variants,
    indicators,
    initial_stop,
    metrics,
)

PERIODS = ("2H", "4H", "1D", "1W", "1M")
ENTRY_BY_PERIOD = {
    "2H": "D_slope_volume",
    "4H": "C_volume",
    "1D": "D_slope_volume",
    "1W": "C_volume",
    "1M": "A_reclaim",
}
EXIT_BY_PERIOD = {
    "2H": "adaptive",
    "4H": "adaptive",
    "1D": "adaptive",
    "1W": "structural_control",
    "1M": "sma20_cross_below_sma50",
}


def final_profile(period: str) -> dict[str, Any]:
    target = EXIT_BY_PERIOD[period]
    rows = [x for x in exit_variants(period) if x["name"] == target]
    if not rows:
        raise RuntimeError(f"missing {period} {target}")
    p = dict(rows[0])
    # Narrow SAT robustness adopted a change only for 1W.
    if period == "1W":
        p.update({"swing": 11, "buffer": 0.15, "trail": 2.10, "max_hold": 60,
                  "tp1": 1.10, "tp2": 2.20, "tp3": 3.30})
    return p


def cost_break_even(entry: float) -> float:
    c = COMMISSION_BPS / 10000.0
    s = SLIPPAGE_BPS / 10000.0
    return entry * (1.0 + s) * (1.0 + c) / ((1.0 - s) * (1.0 - c))


def simulate_be(data: pd.DataFrame, signal_pos: int, p: dict[str, Any], be_mode: str) -> dict[str, Any] | None:
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
    remaining = 1.0
    cash = 0.0
    highest = entry
    min_low = entry
    max_high = entry
    tp1h = tp2h = tp3h = False
    trail_active = False
    tight = False
    be_from_pos: int | None = None
    exit_reason = "TIME"
    exit_pos = ep
    last = min(len(data) - 1, ep + int(p["max_hold"]) - 1)

    for pos in range(ep, last + 1):
        row = data.iloc[pos]
        high = float(row["high"]); low = float(row["low"]); close = float(row["close"])
        highest = max(highest, high); max_high = max(max_high, high); min_low = min(min_low, low)

        if be_mode != "no_be" and be_from_pos is not None and pos >= be_from_pos:
            be_price = entry if be_mode == "entry_be" else cost_break_even(entry)
            stop = max(stop, be_price)

        if low <= stop:
            cash += remaining * stop
            remaining = 0.0
            exit_reason = "TRAIL" if (trail_active or tight or be_from_pos is not None) else "STOP"
            exit_pos = pos
            break

        if not tp1h and high >= tp1:
            q = min(remaining, 0.30); cash += q * tp1; remaining -= q; tp1h = True
            if be_mode != "no_be":
                be_from_pos = pos + 1
        if remaining > 1e-12 and not tp2h and high >= tp2:
            q = min(remaining, 0.30); cash += q * tp2; remaining -= q; tp2h = True; trail_active = True
        if remaining > 1e-12 and not tp3h and high >= tp3:
            q = min(remaining, 0.20); cash += q * tp3; remaining -= q; tp3h = True

        rule = p["rule"]
        full_exit = False
        if rule == "below20":
            full_exit = bool(row["below20"])
        elif rule == "below20_2":
            full_exit = bool(row["below20_2"])
        elif rule == "below50":
            full_exit = bool(row["below50"])
        elif rule == "ma_cross":
            full_exit = bool(row["sma20_cross_down_50"])
        elif rule == "adaptive":
            if bool(row["below20"]):
                tight = True
            full_exit = bool(row["below50"])

        if full_exit and remaining > 1e-12:
            cash += remaining * close
            remaining = 0.0
            exit_reason = "TECH"
            exit_pos = pos
            break

        if remaining > 1e-12 and (trail_active or tight):
            a = float(row["atr14"])
            if np.isfinite(a) and a > 0:
                mult = float(p["tight"] if tight else p["trail"])
                stop = max(stop, highest - mult * a)

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
    times: list[pd.Timestamp] = []
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
                times.extend(pd.Timestamp(data.index[x]) for x in positions)
            if i % 100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)} loaded", flush=True)
    times.sort()
    return frames, times


def bounds_for(times: list[pd.Timestamp]) -> list[pd.Timestamp]:
    if len(times) < 80:
        return []
    b = [pd.Timestamp(times[min(len(times)-1, int(len(times)*q))]) for q in BOUNDARIES[:-1]]
    b.append(pd.Timestamp(times[-1]) + pd.Timedelta(days=3700))
    return b


def collect_mode(frames, p: dict[str, Any], mode: str, start, end):
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
            t = simulate_be(data, signal_pos, p, mode)
            if t is None:
                continue
            # Match bb_sma_wf.collect exactly: trades crossing the fold boundary
            # are excluded rather than attributed to either chronological window.
            if pd.Timestamp(t["exit_time"]) >= end:
                continue
            t["symbol"] = symbol
            trades.append(t)
            last_exit = int(t["exit_pos"])
    trades.sort(key=lambda x: x["entry_time"])
    return trades


def analyze(db: str, period: str) -> dict[str, Any]:
    entry_name = ENTRY_BY_PERIOD[period]
    p = final_profile(period)
    frames, times = load_frames(db, period, entry_name)
    bounds = bounds_for(times)
    if not bounds:
        return {"period": period, "classification": "INSUFFICIENT_SAMPLE"}

    rows = []
    for mode in ("no_be", "entry_be", "cost_be"):
        folds = []
        stitched = []
        for fi in range(4):
            tr = collect_mode(frames, p, mode, bounds[fi], bounds[fi+1])
            m = metrics(tr)
            stitched.extend(tr)
            folds.append({"fold": fi+1, "metrics": m})
        sm = metrics(stitched)
        exps = [float(f["metrics"].get("expectancy_r", 0.0)) for f in folds]
        rows.append({
            "mode": mode,
            "stitched": sm,
            "folds": folds,
            "positive_folds": sum(x > 0 for x in exps),
            "worst_fold_expectancy_r": float(min(exps)),
            "median_fold_expectancy_r": float(np.median(exps)),
        })

    rows.sort(key=lambda r: (
        r["positive_folds"], r["worst_fold_expectancy_r"], r["median_fold_expectancy_r"],
        float(r["stitched"].get("expectancy_r", 0.0)), float(r["stitched"].get("profit_factor") or 0.0)
    ), reverse=True)
    no_be = next(r for r in rows if r["mode"] == "no_be")
    best_be = max((r for r in rows if r["mode"] != "no_be"), key=lambda r: float(r["stitched"].get("expectancy_r", 0.0)))
    decision = "NO_BE" if float(no_be["stitched"].get("expectancy_r", 0.0)) >= float(best_be["stitched"].get("expectancy_r", 0.0)) else best_be["mode"].upper()

    return {
        "version": "bb-sma-be-ab-v2",
        "period": period,
        "entry_rule_frozen": entry_name,
        "exit_rule_frozen": EXIT_BY_PERIOD[period],
        "profile_frozen": {k: p[k] for k in ("swing","buffer","trail","tight","max_hold","tp1","tp2","tp3")},
        "cost_break_even_factor": cost_break_even(1.0),
        "rows": rows,
        "decision": decision,
        "warning": "Historical A/B on observed history; future data remains the true forward test.",
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
