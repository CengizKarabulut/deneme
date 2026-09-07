"""Final fixed-rule 4H comparison for NE ARARSAN VAR.

Compares the simplified production skeleton with four MACD trigger families:
1) bullish MACD crossover
2) histogram rising two steps, sign unrestricted
3) histogram rising two steps while negative
4) histogram rising two steps while positive

CCI and StochRSI are intentionally absent. Every rule is held fixed across four
chronological evaluation windows. The exit is fixed to the previously strongest
4H structural control_123 profile. This is historical robustness research, not
a fresh untouched holdout.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from market_data_store import MarketDataStore
from ne_ararsan_var_research import WARMUP, build_indicator_frame
from ne_ararsan_var_histogram_wf import add_histogram, collect, exit_variants, metrics

PERIOD = "4H"
BOUNDARIES = (0.45, 0.60, 0.75, 0.90, 1.00)

ENTRY_VARIANTS = (
    {"name": "macd_bull_cross", "type": "cross"},
    {"name": "hist_rise_any", "type": "hist", "sign": "any"},
    {"name": "hist_rise_neg", "type": "hist", "sign": "neg"},
    {"name": "hist_rise_pos", "type": "hist", "sign": "pos"},
)


def fixed_exit() -> dict[str, Any]:
    rows = [x for x in exit_variants(PERIOD) if x["name"] == "control_123"]
    if not rows:
        raise RuntimeError("4H control_123 exit profile bulunamadı")
    return dict(rows[0])


def build_events(data: pd.DataFrame, variant: dict[str, Any]) -> pd.Series:
    close = pd.to_numeric(data["close"], errors="coerce")
    hist = pd.to_numeric(data["hist"], errors="coerce")
    common = (
        (close > data["ema5"])
        & (data["ema5"] > data["ema8"])
        & (data["ema8"] > data["ema13"])
        & (data["rsi14"] > 30.0)
        & (data["rsi14"] < 60.0)
        & (data["rvol20"] > 1.50)
    ).fillna(False)

    if variant["type"] == "cross":
        trigger = (
            (data["macd"] > data["macd_signal"])
            & (data["macd"].shift(1) <= data["macd_signal"].shift(1))
        ).fillna(False)
        return (common & trigger).fillna(False)

    rising2 = (hist > hist.shift(1)) & (hist.shift(1) > hist.shift(2))
    condition = common & rising2
    sign = variant.get("sign")
    if sign == "neg":
        condition &= hist < 0.0
    elif sign == "pos":
        condition &= hist > 0.0
    condition = condition.fillna(False)
    return (condition & ~condition.shift(1).fillna(False)).fillna(False)


def rank_key(result: dict[str, Any]) -> tuple:
    m = result["stitched"]
    return (
        int(result["positive_expectancy_folds"]),
        int(result["pf_above_1_folds"]),
        float(result["worst_fold_expectancy_r"]),
        float(result["median_fold_expectancy_r"]),
        float(m.get("expectancy_r", -99.0)),
        float(m.get("profit_factor") or 0.0),
        int(m.get("trades", 0)),
    )


def classification(result: dict[str, Any]) -> str:
    m = result["stitched"]
    trades = int(m.get("trades", 0))
    pf = float(m.get("profit_factor") or 0.0)
    exp = float(m.get("expectancy_r", 0.0))
    pos = int(result["positive_expectancy_folds"])
    worst = float(result["worst_fold_expectancy_r"])
    if trades < 80:
        return "INSUFFICIENT_SAMPLE"
    if pos == 4 and pf > 1.20 and exp > 0.08 and worst > 0:
        return "ROBUST_STRONG"
    if pos >= 3 and pf > 1.10 and exp > 0:
        return "ROBUST_PROMISING"
    if pf > 1.0 and exp > 0:
        return "POSITIVE_BUT_UNSTABLE"
    return "REJECT"


def analyze(db: str) -> dict[str, Any]:
    frames = []
    all_times: list[pd.Timestamp] = []
    signal_counts = {v["name"]: 0 for v in ENTRY_VARIANTS}

    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", PERIOD)
        for i, symbol in enumerate(symbols, 1):
            frame = store.load_dataframe(symbol, "BIST", PERIOD, limit=0)
            if frame is None or len(frame) <= WARMUP + 5:
                continue
            data = add_histogram(build_indicator_frame(frame))
            positions_by_entry = {}
            for variant in ENTRY_VARIANTS:
                events = build_events(data, variant)
                positions = [
                    int(x)
                    for x in np.flatnonzero(events.to_numpy(dtype=bool))
                    if x >= WARMUP and x + 1 < len(data)
                ]
                positions_by_entry[variant["name"]] = positions
                signal_counts[variant["name"]] += len(positions)
                all_times.extend(pd.Timestamp(data.index[x]) for x in positions)
            if any(positions_by_entry.values()):
                frames.append((symbol, data, positions_by_entry))
            if i % 100 == 0 or i == len(symbols):
                print(f"[4H] {i}/{len(symbols)} loaded", flush=True)

    all_times.sort()
    if len(all_times) < 100:
        raise RuntimeError(f"4H: yetersiz aday olay ({len(all_times)})")

    bounds = [
        pd.Timestamp(all_times[min(len(all_times) - 1, int(len(all_times) * q))])
        for q in BOUNDARIES[:-1]
    ]
    bounds.append(pd.Timestamp(all_times[-1]) + pd.Timedelta(days=3700))

    exit_profile = fixed_exit()
    results = []
    for variant in ENTRY_VARIANTS:
        folds = []
        stitched = []
        for idx in range(4):
            start = bounds[idx]
            end = bounds[idx + 1]
            trades = collect(frames, variant["name"], exit_profile, start=start, end=end)
            m = metrics(trades)
            stitched.extend(trades)
            folds.append({
                "fold": idx + 1,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "metrics": m,
            })
        stitched_m = metrics(stitched)
        exps = [float(f["metrics"].get("expectancy_r", 0.0)) for f in folds]
        pfs = [float(f["metrics"].get("profit_factor") or 0.0) for f in folds]
        result = {
            "entry": variant,
            "signal_count_full_history": signal_counts[variant["name"]],
            "folds": folds,
            "stitched": stitched_m,
            "positive_expectancy_folds": sum(x > 0 for x in exps),
            "pf_above_1_folds": sum(x > 1 for x in pfs),
            "median_fold_expectancy_r": float(np.median(exps)),
            "worst_fold_expectancy_r": float(min(exps)),
            "best_fold_expectancy_r": float(max(exps)),
        }
        result["classification"] = classification(result)
        results.append(result)

    results.sort(key=rank_key, reverse=True)
    return {
        "version": "ne-ararsan-var-4h-final-fixed-compare-v1",
        "period": PERIOD,
        "method": "four fixed entry rules across four chronological windows; fixed 4H control_123 exit; next-bar open; 10bps commission + 10bps slippage per side",
        "common_entry": "Close > EMA5 > EMA8 > EMA13; 30<RSI14<60; RVOL20>1.50; no CCI; no StochRSI",
        "fixed_exit": exit_profile,
        "ranked_variants": results,
        "best_variant": results[0],
        "warning": "Historical robustness only; future new data remains the true forward validation.",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    payload = analyze(args.db)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
