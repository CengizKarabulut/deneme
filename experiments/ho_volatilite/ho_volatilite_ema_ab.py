"""HO/Volatilite — isolated EMA A/B entry-quality experiment.

Only the EMA interpretation changes:
A aligned: Close > EMA21 > EMA55
B fresh cross: Close > EMA21 and EMA21 fresh-crosses EMA55

Everything else is held fixed, including the original cross-timeframe 1H
volume-change and volatility comparisons.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_BB = Path(__file__).resolve().parents[1] / "bb_squeeze"
sys.path.insert(0, str(_BB))
from bb_squeeze_entry_stage import (  # noqa: E402
    MarketDataStore,
    PERIODS,
    WARMUP,
    structure,
    metrics,
    bounds_for,
    collect,
    atr,
)

_TAVAN = Path(__file__).resolve().parents[1] / "tavan_tarama"
sys.path.insert(0, str(_TAVAN))
from tavan_entry_stage import rsi  # noqa: E402


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=span).mean()


def true_range_pct(frame: pd.DataFrame) -> pd.Series:
    h = pd.to_numeric(frame["high"], errors="coerce")
    l = pd.to_numeric(frame["low"], errors="coerce")
    c = pd.to_numeric(frame["close"], errors="coerce")
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr * 100.0 / l.abs().replace(0.0, np.nan)


def base_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    c = pd.to_numeric(out["close"], errors="coerce")
    v = pd.to_numeric(out["volume"], errors="coerce")

    out["ema21"] = ema(c, 21)
    out["ema55"] = ema(c, 55)
    out["ema21_cross_55_up"] = (
        (out["ema21"] > out["ema55"])
        & (out["ema21"].shift(1) <= out["ema55"].shift(1))
    ).fillna(False)

    out["volume_change"] = v - v.shift(1)
    out["volatility_pct"] = true_range_pct(out)

    out["momentum14"] = c - c.shift(14)

    r = rsi(c, 14)
    lo = r.rolling(14, min_periods=14).min()
    hi = r.rolling(14, min_periods=14).max()
    raw = 100.0 * (r-lo) / (hi-lo).replace(0.0, np.nan)
    k = raw.rolling(3, min_periods=3).mean()
    d = k.rolling(3, min_periods=3).mean()
    out["stoch_k"] = k
    out["stoch_d"] = d
    out["stoch_cross_up"] = ((k > d) & (k.shift(1) <= d.shift(1))).fillna(False)

    e12 = ema(c, 12)
    e26 = ema(c, 26)
    out["macd_level"] = e12 - e26
    out["atr14"] = atr(out, 14)
    return out


def ref_1h_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    v = pd.to_numeric(out["volume"], errors="coerce")
    out["volume_change_1h"] = v - v.shift(1)
    out["volatility_1h"] = true_range_pct(out)
    return out


def daily_volume_regime(frame: pd.DataFrame) -> pd.DataFrame:
    """Look-ahead-free daily AvgVol10/30 using only prior completed daily bars."""
    out = frame.copy()
    v = pd.to_numeric(out["volume"], errors="coerce")
    prior = v.shift(1)
    out["avgvol10d_prev"] = prior.rolling(10, min_periods=10).mean()
    out["avgvol30d_prev"] = prior.rolling(30, min_periods=30).mean()
    return out


def _ns(index: pd.Index) -> np.ndarray:
    idx = pd.DatetimeIndex(pd.to_datetime(index))
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return idx.asi8


def align_last_ref_before_next_target(
    target_index: pd.Index,
    ref_index: pd.Index,
    ref_values: pd.Series,
) -> pd.Series:
    """Value of last ref bar available by the completion of each target bar.

    Target bars are labelled at their start.  The next target label is used as
    a strict upper bound.  Thus a target row can only see ref rows whose label
    is strictly earlier than the next target bar.
    """
    ti = _ns(target_index)
    ri = _ns(ref_index)
    vals = pd.to_numeric(ref_values, errors="coerce").to_numpy(dtype=float)
    out = np.full(len(ti), np.nan, dtype=float)
    if len(ti) < 2 or len(ri) == 0:
        return pd.Series(out, index=target_index)
    cutoffs = ti[1:]
    pos = np.searchsorted(ri, cutoffs, side="left") - 1
    ok = (pos >= 0) & (pos < len(vals))
    tmp = np.full(len(cutoffs), np.nan, dtype=float)
    tmp[ok] = vals[pos[ok]]
    out[:-1] = tmp
    return pd.Series(out, index=target_index)


def enrich_cross_timeframe(
    target: pd.DataFrame,
    ref1h: pd.DataFrame,
    daily: pd.DataFrame,
    period: str,
) -> pd.DataFrame:
    d = base_indicators(target)

    if period == "1H":
        # Preserve exact original semantics: target 1H compared with itself.
        d["ref1h_volume_change"] = d["volume_change"]
        d["ref1h_volatility"] = d["volatility_pct"]
    else:
        h = ref_1h_indicators(ref1h)
        d["ref1h_volume_change"] = align_last_ref_before_next_target(
            d.index, h.index, h["volume_change_1h"]
        )
        d["ref1h_volatility"] = align_last_ref_before_next_target(
            d.index, h.index, h["volatility_1h"]
        )

    dv = daily_volume_regime(daily)
    d["avgvol10d_prev"] = align_last_ref_before_next_target(
        d.index, dv.index, dv["avgvol10d_prev"]
    )
    d["avgvol30d_prev"] = align_last_ref_before_next_target(
        d.index, dv.index, dv["avgvol30d_prev"]
    )
    return d


def entry_variants() -> list[dict[str, Any]]:
    return [
        {"name": "A_aligned", "ema_mode": "aligned"},
        {"name": "B_fresh_cross", "ema_mode": "fresh_cross"},
    ]


def common_condition(d: pd.DataFrame) -> pd.Series:
    vc = pd.to_numeric(d["volume_change"], errors="coerce")
    vc1 = pd.to_numeric(d["ref1h_volume_change"], errors="coerce")
    vol = pd.to_numeric(d["volatility_pct"], errors="coerce")
    vol1 = pd.to_numeric(d["ref1h_volatility"], errors="coerce")
    av10 = pd.to_numeric(d["avgvol10d_prev"], errors="coerce")
    av30 = pd.to_numeric(d["avgvol30d_prev"], errors="coerce")
    mom = pd.to_numeric(d["momentum14"], errors="coerce")
    macd = pd.to_numeric(d["macd_level"], errors="coerce")
    return (
        (vc > vc1)
        & (av10 > av30)
        & (vol > vol1)
        & (mom > 0.0)
        & d["stoch_cross_up"]
        & (macd > 0.0)
    ).fillna(False)


def entry_events(d: pd.DataFrame, variant: dict[str, Any]) -> pd.Series:
    c = pd.to_numeric(d["close"], errors="coerce")
    e21 = pd.to_numeric(d["ema21"], errors="coerce")
    e55 = pd.to_numeric(d["ema55"], errors="coerce")
    common = common_condition(d)
    if variant["ema_mode"] == "aligned":
        ema_ok = (c > e21) & (e21 > e55)
    elif variant["ema_mode"] == "fresh_cross":
        ema_ok = (c > e21) & d["ema21_cross_55_up"]
    else:
        raise ValueError(variant["ema_mode"])
    return (common & ema_ok).fillna(False)


def classify(row: dict[str, Any]) -> str:
    m = row["stitched"]
    n = int(m.get("trades", 0))
    pf = float(m.get("profit_factor") or 0)
    ex = float(m.get("expectancy_r", 0))
    pos = row.get("positive_folds")
    worst = row.get("worst_fold_expectancy_r")
    if n < 30 or pos is None or worst is None:
        return "INSUFFICIENT_SAMPLE"
    if pos == 4 and pf > 1.20 and ex > 0.08 and worst > 0:
        return "ROBUST_STRONG"
    if pos >= 3 and pf > 1.10 and ex > 0:
        return "ROBUST_PROMISING"
    if pf > 1 and ex > 0:
        return "POSITIVE_UNSTABLE"
    return "REJECT"


def _full_metrics(frames, entry_name: str, p: dict[str, Any], times: list[pd.Timestamp]) -> dict[str, Any]:
    if not times:
        return metrics([])
    start = pd.Timestamp(times[0]) - pd.Timedelta(days=3700)
    end = pd.Timestamp(times[-1]) + pd.Timedelta(days=3700)
    return metrics(collect(frames, entry_name, p, start, end))


def analyze(db: str, ref1h_db: str, daily_db: str, period: str) -> dict[str, Any]:
    variants = entry_variants()
    p = structure(period)
    frames = []
    times = {v["name"]: [] for v in variants}
    counts = Counter()

    with (
        MarketDataStore(db, read_only=True) as store,
        MarketDataStore(ref1h_db, read_only=True) as hstore,
        MarketDataStore(daily_db, read_only=True) as dstore,
    ):
        syms = store.list_symbols("BIST", period)
        for i, sym in enumerate(syms, 1):
            fr = store.load_dataframe(sym, "BIST", period, limit=0)
            if fr is None or len(fr) <= WARMUP + 22:
                continue

            if period == "1H":
                hfr = fr
            else:
                hfr = hstore.load_dataframe(sym, "BIST", "1H", limit=0)
            dfr = dstore.load_dataframe(sym, "BIST", "1D", limit=0)
            if hfr is None or hfr.empty or dfr is None or dfr.empty:
                continue

            d = enrich_cross_timeframe(fr, hfr, dfr, period)
            pbe = {}
            for v in variants:
                ev = entry_events(d, v)
                ps = [
                    int(x) for x in np.flatnonzero(ev.to_numpy(bool))
                    if x >= WARMUP and x + 1 < len(d)
                ]
                pbe[v["name"]] = ps
                counts[v["name"]] += len(ps)
                times[v["name"]].extend(pd.Timestamp(d.index[x]) for x in ps)
            if any(pbe.values()):
                frames.append((sym, d, pbe))
            if i % 100 == 0 or i == len(syms):
                print(f"[{period}] {i}/{len(syms)}", flush=True)

    for key in times:
        times[key].sort()

    rows = []
    for v in variants:
        name = v["name"]
        full = _full_metrics(frames, name, p, times[name])
        b = bounds_for(times[name])
        if not b:
            row = {
                "entry": v,
                "signal_count": counts[name],
                "folds": [],
                "stitched": full,
                "positive_folds": None,
                "worst_fold_expectancy_r": None,
                "median_fold_expectancy_r": None,
            }
            row["classification"] = "INSUFFICIENT_SAMPLE"
            rows.append(row)
            continue

        folds = []
        stitched = []
        for fi in range(4):
            tr = collect(frames, name, p, b[fi], b[fi+1])
            stitched.extend(tr)
            folds.append({"fold": fi+1, "metrics": metrics(tr)})
        sm = metrics(stitched)
        fold_ex = [float(f["metrics"].get("expectancy_r", 0)) for f in folds]
        row = {
            "entry": v,
            "signal_count": counts[name],
            "folds": folds,
            "stitched": sm,
            "full_sample": full,
            "positive_folds": sum(x > 0 for x in fold_ex),
            "worst_fold_expectancy_r": float(min(fold_ex)),
            "median_fold_expectancy_r": float(np.median(fold_ex)),
        }
        row["classification"] = classify(row)
        rows.append(row)

    rank = {
        "ROBUST_STRONG": 4,
        "ROBUST_PROMISING": 3,
        "POSITIVE_UNSTABLE": 2,
        "REJECT": 1,
        "INSUFFICIENT_SAMPLE": 0,
    }
    rows.sort(
        key=lambda r: (
            rank[r["classification"]],
            -999 if r["positive_folds"] is None else r["positive_folds"],
            -999.0 if r["worst_fold_expectancy_r"] is None else r["worst_fold_expectancy_r"],
            float(r["stitched"].get("expectancy_r", 0)),
            float(r["stitched"].get("profit_factor") or 0),
        ),
        reverse=True,
    )
    by_name = {r["entry"]["name"]: r for r in rows}
    return {
        "version": "ho-volatilite-ema-ab-v1",
        "period": period,
        "method": "Only EMA A/B changes; all other original conditions fixed; same structural exit; costs included; entry-specific chronological folds when sample permits",
        "fixed_conditions": {
            "volume_change": "TF Volume[t]-Volume[t-1] > last completed 1H Volume[t]-Volume[t-1] available at TF bar completion",
            "avg_volume": "prior completed daily SMA10 > prior completed daily SMA30",
            "volatility": "TF TrueRange% > last completed 1H TrueRange% available at TF bar completion",
            "momentum14": ">0",
            "stoch_rsi": "fresh K cross above D, 3,3,14,14",
            "macd_level": ">0",
        },
        "rows": rows,
        "by_name": by_name,
        "best": rows[0] if rows else None,
        "warning": "Observed historical data; future unseen bars are true forward validation. Cross-timeframe fields are intentionally held fixed in this isolation stage.",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--ref1h-db", required=True)
    ap.add_argument("--daily-db", required=True)
    ap.add_argument("--period", choices=PERIODS, required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    result = analyze(args.db, args.ref1h_db, args.daily_db, args.period)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
