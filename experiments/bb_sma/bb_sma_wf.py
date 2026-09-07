"""Walk-forward research for BB Basis / SMA trend-continuation scan.

BB(20) Basis is treated as SMA20.

Entry families:
A_reclaim:
    Close crosses above SMA20 AND SMA20>SMA50>SMA200
B_slope:
    A + SMA20>SMA20[1]
C_volume:
    A + Volume[t] > mean(Volume[t-1]..Volume[t-10])
D_slope_volume:
    A + slope + volume

All signals use completed bars. Entry reference is t+1 open.
Four expanding walk-forward folds. Costs: 10 bps commission + 10 bps slippage per side.
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

_SHARED = Path(__file__).resolve().parents[1] / "stoch_rsi_momentum_volume"
sys.path.insert(0, str(_SHARED))
from market_data_store import MarketDataStore  # noqa: E402

PERIODS = ("15m","30m","45m","1H","2H","4H","1D","1W","1M")
BOUNDARIES = (0.45,0.60,0.75,0.90,1.00)
COMMISSION_BPS = 10.0
SLIPPAGE_BPS = 10.0
WARMUP = 240


def atr(frame: pd.DataFrame, length: int = 14) -> pd.Series:
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    prev = close.shift(1)
    tr = pd.concat([high-low, (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/length, adjust=False, min_periods=length).mean()


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    close = pd.to_numeric(out["close"], errors="coerce")
    volume = pd.to_numeric(out["volume"], errors="coerce")
    out["sma20"] = close.rolling(20, min_periods=20).mean()
    out["sma50"] = close.rolling(50, min_periods=50).mean()
    out["sma200"] = close.rolling(200, min_periods=200).mean()
    out["atr14"] = atr(out, 14)
    out["trend_ok"] = ((out["sma20"] > out["sma50"]) & (out["sma50"] > out["sma200"])).fillna(False)
    out["reclaim"] = ((close > out["sma20"]) & (close.shift(1) <= out["sma20"].shift(1))).fillna(False)
    out["slope20_up"] = (out["sma20"] > out["sma20"].shift(1)).fillna(False)
    prev10 = volume.shift(1).rolling(10, min_periods=10).mean()
    out["vol_prev10_avg"] = prev10
    out["volume_ok"] = (volume > prev10).fillna(False)
    out["below20"] = (close < out["sma20"]).fillna(False)
    out["below20_2"] = (out["below20"] & out["below20"].shift(1).fillna(False)).fillna(False)
    out["below50"] = (close < out["sma50"]).fillna(False)
    out["sma20_cross_down_50"] = (
        (out["sma20"] < out["sma50"]) & (out["sma20"].shift(1) >= out["sma50"].shift(1))
    ).fillna(False)
    return out


def entry_variants() -> list[dict[str,str]]:
    return [
        {"name":"A_reclaim","description":"Close crosses above SMA20; SMA20>SMA50>SMA200"},
        {"name":"B_slope","description":"A + SMA20 rising"},
        {"name":"C_volume","description":"A + current volume > previous 10 same-TF bar average"},
        {"name":"D_slope_volume","description":"A + rising SMA20 + 10-bar volume"},
    ]


def entry_events(data: pd.DataFrame, name: str) -> pd.Series:
    base = data["reclaim"] & data["trend_ok"]
    if name == "A_reclaim":
        cond = base
    elif name == "B_slope":
        cond = base & data["slope20_up"]
    elif name == "C_volume":
        cond = base & data["volume_ok"]
    elif name == "D_slope_volume":
        cond = base & data["slope20_up"] & data["volume_ok"]
    else:
        raise ValueError(name)
    return cond.fillna(False)


def structure(period: str) -> dict[str,Any]:
    table = {
        "15m": dict(stop_mode="hybrid", stop_atr=1.00, swing=5, buffer=0.10, trail=1.40, tight=1.00, max_hold=24),
        "30m": dict(stop_mode="hybrid", stop_atr=1.05, swing=5, buffer=0.12, trail=1.50, tight=1.05, max_hold=24),
        "45m": dict(stop_mode="hybrid", stop_atr=1.10, swing=5, buffer=0.15, trail=1.60, tight=1.15, max_hold=24),
        "1H": dict(stop_mode="swing", stop_atr=1.15, swing=7, buffer=0.15, trail=1.70, tight=1.25, max_hold=32),
        "2H": dict(stop_mode="swing", stop_atr=1.20, swing=7, buffer=0.18, trail=1.90, tight=1.40, max_hold=40),
        "4H": dict(stop_mode="swing", stop_atr=1.25, swing=7, buffer=0.20, trail=2.00, tight=1.50, max_hold=40),
        "1D": dict(stop_mode="swing", stop_atr=1.25, swing=7, buffer=0.20, trail=2.20, tight=1.65, max_hold=40),
        "1W": dict(stop_mode="swing", stop_atr=1.30, swing=9, buffer=0.15, trail=2.30, tight=1.75, max_hold=60),
        "1M": dict(stop_mode="swing", stop_atr=1.30, swing=9, buffer=0.15, trail=2.50, tight=1.90, max_hold=36),
    }
    return dict(table[period])


def exit_variants(period: str) -> list[dict[str,Any]]:
    s = structure(period)
    rows = []
    for name, rule in [
        ("structural_control","none"),
        ("close_below_sma20","below20"),
        ("two_closes_below_sma20","below20_2"),
        ("close_below_sma50","below50"),
        ("sma20_cross_below_sma50","ma_cross"),
        ("adaptive","adaptive"),
    ]:
        p = dict(s)
        p.update({
            "name": name, "rule": rule,
            "tp1":1.0, "tp2":2.0, "tp3":3.0,
            "alloc":(0.30,0.30,0.20), "runner":0.20,
        })
        rows.append(p)
    return rows


def initial_stop(data: pd.DataFrame, signal_pos: int, entry: float, p: dict[str,Any]) -> tuple[float,float]:
    a = float(data["atr14"].iloc[signal_pos])
    if not np.isfinite(a) or a <= 0:
        a = max(entry*0.02, 1e-6)
    start = max(0, signal_pos-int(p["swing"])+1)
    swing_low = float(pd.to_numeric(data["low"].iloc[start:signal_pos+1], errors="coerce").min())
    swing_stop = swing_low - float(p["buffer"])*a
    atr_stop = entry - float(p["stop_atr"])*a
    if p["stop_mode"] == "swing":
        raw = swing_stop if np.isfinite(swing_stop) and swing_stop < entry else atr_stop
    elif p["stop_mode"] == "hybrid":
        candidates = [x for x in (swing_stop, atr_stop) if np.isfinite(x) and x < entry]
        raw = max(candidates) if candidates else atr_stop
    else:
        raw = atr_stop
    risk = entry - raw
    risk = min(max(risk, 0.60*a), 2.60*a)
    return entry-risk, risk


def simulate(data: pd.DataFrame, signal_pos: int, p: dict[str,Any]) -> dict[str,Any] | None:
    ep = signal_pos + 1
    if ep >= len(data):
        return None
    entry = float(data["open"].iloc[ep])
    if not np.isfinite(entry) or entry <= 0:
        return None
    stop, risk = initial_stop(data, signal_pos, entry, p)
    if risk <= 0:
        return None
    tp1, tp2, tp3 = entry+risk*p["tp1"], entry+risk*p["tp2"], entry+risk*p["tp3"]
    remaining = 1.0
    cash = 0.0
    highest = entry
    min_low = entry
    max_high = entry
    tp1h = tp2h = tp3h = False
    trail_active = False
    tight = False
    exit_reason = "TIME"
    exit_pos = ep
    last = min(len(data)-1, ep+int(p["max_hold"])-1)

    for pos in range(ep, last+1):
        row = data.iloc[pos]
        high = float(row["high"]); low = float(row["low"]); close = float(row["close"])
        highest = max(highest, high); max_high = max(max_high, high); min_low = min(min_low, low)

        if low <= stop:
            cash += remaining*stop
            remaining = 0.0
            exit_reason = "TRAIL" if (trail_active or tight) else "STOP"
            exit_pos = pos
            break

        if not tp1h and high >= tp1:
            q = min(remaining, 0.30); cash += q*tp1; remaining -= q; tp1h = True
        if remaining > 1e-12 and not tp2h and high >= tp2:
            q = min(remaining, 0.30); cash += q*tp2; remaining -= q; tp2h = True; trail_active = True
        if remaining > 1e-12 and not tp3h and high >= tp3:
            q = min(remaining, 0.20); cash += q*tp3; remaining -= q; tp3h = True

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
            cash += remaining*close
            remaining = 0.0
            exit_reason = "TECH"
            exit_pos = pos
            break

        if remaining > 1e-12 and (trail_active or tight):
            a = float(row["atr14"])
            if np.isfinite(a) and a > 0:
                mult = float(p["tight"] if tight else p["trail"])
                stop = max(stop, highest-mult*a)

        if pos == last and remaining > 1e-12:
            cash += remaining*close
            remaining = 0.0
            exit_reason = "TIME"
            exit_pos = pos
            break

    pnl = cash-entry
    return {
        "signal_time":pd.Timestamp(data.index[signal_pos]),
        "entry_time":pd.Timestamp(data.index[ep]),
        "exit_time":pd.Timestamp(data.index[exit_pos]),
        "entry":entry, "risk":risk,
        "realized_r":pnl/risk,
        "return_pct":pnl/entry*100.0,
        "mfe_r":(max_high-entry)/risk,
        "mae_r":(min_low-entry)/risk,
        "tp1_hit":tp1h, "tp2_hit":tp2h, "tp3_hit":tp3h,
        "exit_reason":exit_reason, "exit_pos":exit_pos,
    }


def net_r(t: dict[str,Any], commission_bps: float=COMMISSION_BPS, slippage_bps: float=SLIPPAGE_BPS) -> float:
    entry = float(t["entry"]); risk = float(t["risk"]); gross_r = float(t["realized_r"])
    weighted_exit = entry + gross_r*risk
    c = commission_bps/10000.0; s = slippage_bps/10000.0
    buy = entry*(1+s); sell = weighted_exit*(1-s)
    return (sell*(1-c)-buy*(1+c))/risk


def metrics(trades: list[dict[str,Any]]) -> dict[str,Any]:
    if not trades:
        return {"trades":0,"profit_factor":None,"expectancy_r":0.0,"win_rate_pct":0.0}
    r = np.array([net_r(t) for t in trades], dtype=float)
    gp = float(r[r>0].sum()); gl = float(-r[r<0].sum())
    return {
        "trades":len(trades),
        "win_rate_pct":float((r>0).mean()*100.0),
        "expectancy_r":float(r.mean()),
        "median_r":float(np.median(r)),
        "profit_factor":gp/gl if gl>0 else None,
        "avg_mfe_r":float(np.mean([t["mfe_r"] for t in trades])),
        "avg_mae_r":float(np.mean([t["mae_r"] for t in trades])),
        "tp1_rate_pct":float(np.mean([t["tp1_hit"] for t in trades])*100.0),
        "tp2_rate_pct":float(np.mean([t["tp2_hit"] for t in trades])*100.0),
        "tp3_rate_pct":float(np.mean([t["tp3_hit"] for t in trades])*100.0),
    }


def score(m: dict[str,Any]) -> float:
    t = int(m.get("trades",0))
    if t < 30:
        return -1e9 + t
    pf = float(m.get("profit_factor") or 0.0)
    e = float(m.get("expectancy_r",0.0))
    return e*3.0 + min(pf,3.0)*0.18 + min(t,5000)/5000.0*0.05


def collect(frames, entry_name: str, p: dict[str,Any], start=None, end=None) -> list[dict[str,Any]]:
    trades = []
    for symbol, data, positions_by_entry in frames:
        last_exit = -1
        for signal_pos in positions_by_entry.get(entry_name, []):
            st = pd.Timestamp(data.index[signal_pos])
            if start is not None and st < start:
                continue
            if end is not None and st >= end:
                break
            if signal_pos <= last_exit:
                continue
            t = simulate(data, signal_pos, p)
            if t is None:
                continue
            if end is not None and pd.Timestamp(t["exit_time"]) >= end:
                continue
            t["symbol"] = symbol
            trades.append(t)
            last_exit = int(t["exit_pos"])
    trades.sort(key=lambda x: x["entry_time"])
    return trades


def raw_forward(data: pd.DataFrame, signal_pos: int) -> dict[str,float]:
    ep = signal_pos+1
    if ep >= len(data):
        return {}
    entry = float(data["open"].iloc[ep])
    if not np.isfinite(entry) or entry <= 0:
        return {}
    out = {}
    for h in (1,3,5,10,20):
        pos = ep+h-1
        if pos < len(data):
            out[str(h)] = (float(data["close"].iloc[pos])/entry-1.0)*100.0
    return out


def analyze(db: str, period: str) -> dict[str,Any]:
    entries = entry_variants()
    exits = exit_variants(period)
    combos = [(e,x) for e in entries for x in exits]
    frames = []
    all_times = []
    signal_counts = Counter()
    raw_by_entry = {e["name"]:[] for e in entries}

    with MarketDataStore(db, read_only=True) as store:
        symbols = store.list_symbols("BIST", period)
        for i, symbol in enumerate(symbols,1):
            frame = store.load_dataframe(symbol,"BIST",period,limit=0)
            if frame is None or len(frame) <= WARMUP+22:
                continue
            data = indicators(frame)
            pbe = {}
            for e in entries:
                ev = entry_events(data,e["name"])
                positions = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x>=WARMUP and x+1<len(data)]
                pbe[e["name"]] = positions
                signal_counts[e["name"]] += len(positions)
                all_times.extend(pd.Timestamp(data.index[x]) for x in positions)
                for x in positions:
                    rf = raw_forward(data,x)
                    if rf:
                        raw_by_entry[e["name"]].append(rf)
            if any(pbe.values()):
                frames.append((symbol,data,pbe))
            if i%100 == 0 or i == len(symbols):
                print(f"[{period}] {i}/{len(symbols)} loaded", flush=True)

    all_times.sort()
    if len(all_times) < 80:
        return {"version":"bb-sma-wf-v1","period":period,"classification":"INSUFFICIENT_SAMPLE","all_candidate_events":len(all_times)}

    bounds = [pd.Timestamp(all_times[min(len(all_times)-1,int(len(all_times)*q))]) for q in BOUNDARIES[:-1]]
    bounds.append(pd.Timestamp(all_times[-1]) + pd.Timedelta(days=3700))

    folds = []
    stitched = []
    selected_entries = []
    selected_exits = []
    for fi in range(4):
        ts, te = bounds[fi], bounds[fi+1]
        rows = []
        for e,x in combos:
            tr = collect(frames,e["name"],x,start=None,end=ts)
            m = metrics(tr)
            rows.append({"entry":e,"exit":x,"metrics":m,"score":score(m)})
        rows.sort(key=lambda r:r["score"], reverse=True)
        chosen = rows[0]
        test = collect(frames,chosen["entry"]["name"],chosen["exit"],start=ts,end=te)
        tm = metrics(test)
        stitched.extend(test)
        selected_entries.append(chosen["entry"]["name"])
        selected_exits.append(chosen["exit"]["name"])
        folds.append({
            "fold":fi+1,"test_start":ts.isoformat(),"test_end":te.isoformat(),
            "selected_entry":chosen["entry"],"selected_exit":chosen["exit"],
            "train_metrics":chosen["metrics"],"test_metrics":tm,"train_top5":rows[:5],
        })

    sm = metrics(stitched)
    exps = [float(f["test_metrics"].get("expectancy_r",0.0)) for f in folds]
    pfs = [float(f["test_metrics"].get("profit_factor") or 0.0) for f in folds]
    positive = sum(x>0 for x in exps)
    pf1 = sum(x>1 for x in pfs)
    cls = "REJECT"
    if sm["trades"] >= 80 and sm["expectancy_r"] > 0 and (sm["profit_factor"] or 0) > 1.10 and positive >= 3:
        cls = "PROMISING"
    if sm["trades"] >= 80 and sm["expectancy_r"] > 0.08 and (sm["profit_factor"] or 0) > 1.20 and positive == 4:
        cls = "STRONG_WALK_FORWARD"
    if sm["trades"] < 30:
        cls = "INSUFFICIENT_SAMPLE"

    raw_summary = {}
    for name, rows in raw_by_entry.items():
        raw_summary[name] = {}
        for h in ("1","3","5","10","20"):
            vals = np.array([r[h] for r in rows if h in r], dtype=float)
            raw_summary[name][h] = {
                "events":int(len(vals)),
                "avg_return_pct":float(vals.mean()) if len(vals) else None,
                "median_return_pct":float(np.median(vals)) if len(vals) else None,
                "positive_rate_pct":float((vals>0).mean()*100.0) if len(vals) else None,
            }

    return {
        "version":"bb-sma-wf-v1",
        "period":period,
        "method":"4 expanding walk-forward folds; completed-bar signal; t+1 open; 10bps commission + 10bps slippage per side",
        "definition":"BB(20) Basis == SMA20",
        "entry_signal_counts":dict(signal_counts),
        "raw_forward":raw_summary,
        "folds":folds,
        "stitched_walk_forward_oos":sm,
        "stability":{
            "positive_expectancy_folds":positive,
            "pf_above_1_folds":pf1,
            "median_fold_expectancy_r":float(np.median(exps)),
            "selected_entries":selected_entries,
            "selected_exits":selected_exits,
        },
        "classification":cls,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db",required=True)
    ap.add_argument("--period",choices=PERIODS,required=True)
    ap.add_argument("--output",required=True)
    args = ap.parse_args()
    payload = analyze(args.db,args.period)
    path = Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False,indent=2,default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
