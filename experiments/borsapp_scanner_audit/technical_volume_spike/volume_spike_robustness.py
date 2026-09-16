from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
THRESHOLDS = (1.5, 2.0, 2.5, 3.0, 4.0, 5.0)
INTRADAY = {"15m", "30m", "45m", "1H", "2H", "4H"}


def load_symbols(con: sqlite3.Connection, exchange: str, period: str) -> list[str]:
    rows = con.execute(
        "SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol",
        (exchange, period),
    ).fetchall()
    return [str(r[0]) for r in rows]


def load_frame(con: sqlite3.Connection, symbol: str, exchange: str, period: str) -> pd.DataFrame:
    df = pd.read_sql_query(
        """SELECT candle_time, open, high, low, close, volume
           FROM candles WHERE symbol=? AND exchange=? AND period=? ORDER BY candle_time""",
        con,
        params=(symbol, exchange, period),
    )
    if df.empty:
        return df
    df["candle_time"] = pd.to_datetime(df["candle_time"], errors="coerce")
    df = df.dropna(subset=["candle_time"]).set_index("candle_time")
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["open", "high", "low", "close", "volume"])


def atr14(df: pd.DataFrame) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([(df["high"]-df["low"]), (df["high"]-prev).abs(), (df["low"]-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()


def forward_max(s: pd.Series, h: int) -> pd.Series:
    return s.shift(-1).iloc[::-1].rolling(h, min_periods=h).max().iloc[::-1]


def forward_min(s: pd.Series, h: int) -> pd.Series:
    return s.shift(-1).iloc[::-1].rolling(h, min_periods=h).min().iloc[::-1]


def enrich(df: pd.DataFrame, period: str, window: int, min_history: int) -> pd.DataFrame:
    x = df.copy()
    vol = x["volume"].astype(float)
    turnover = x["close"].astype(float) * vol
    x["baseline_volume"] = vol.shift(1).rolling(window, min_periods=min_history).mean()
    x["rvol"] = vol / x["baseline_volume"].replace(0.0, np.nan)
    x["turnover_current_inclusive"] = turnover.rolling(window, min_periods=1).mean()
    x["turnover_previous_only"] = turnover.shift(1).rolling(window, min_periods=min_history).mean()
    x["atr14"] = atr14(x)
    x["quarter"] = x.index.to_period("Q").astype(str)
    if period in INTRADAY:
        x["slot"] = x.index.strftime("%H:%M")
        x["slot_baseline_volume"] = (
            x.groupby("slot", sort=False)["volume"]
             .transform(lambda s: s.shift(1).rolling(window, min_periods=min_history).mean())
        )
        x["slot_rvol"] = vol / x["slot_baseline_volume"].replace(0.0, np.nan)
    else:
        x["slot"] = "ALL"
        x["slot_rvol"] = x["rvol"]

    log_turn = np.log10(x["turnover_previous_only"].where(x["turnover_previous_only"] > 0))
    x["turnover_bucket"] = np.floor(log_turn * 4.0) / 4.0

    close = x["close"].astype(float)
    for h in HORIZONS:
        end_close = close.shift(-h)
        hi = forward_max(x["high"].astype(float), h)
        lo = forward_min(x["low"].astype(float), h)
        x[f"h{h}_return_pct"] = (end_close / close - 1.0) * 100.0
        x[f"h{h}_abs_return_pct"] = x[f"h{h}_return_pct"].abs()
        x[f"h{h}_mfe_pct"] = (hi / close - 1.0) * 100.0
        x[f"h{h}_mae_pct"] = (lo / close - 1.0) * 100.0
        x[f"h{h}_range_atr"] = (hi - lo) / x["atr14"].replace(0.0, np.nan)
    return x


def matched_edges(all_rows: pd.DataFrame, threshold: float, min_price: float, min_turnover: float) -> list[dict]:
    eligible = all_rows[(all_rows["close"] >= min_price) & (all_rows["turnover_previous_only"] >= min_turnover)].copy()
    events = eligible[eligible["rvol"] >= threshold].copy()
    controls = eligible[eligible["rvol"] < 1.5].copy()
    keys = ["symbol", "quarter", "slot", "turnover_bucket"]
    metrics = []
    for h in HORIZONS:
        metrics += [f"h{h}_abs_return_pct", f"h{h}_range_atr", f"h{h}_mfe_pct", f"h{h}_mae_pct"]
    control_med = controls.groupby(keys, dropna=False)[metrics].median().reset_index()
    matched = events.merge(control_med, on=keys, how="inner", suffixes=("_event", "_control"))
    out = []
    for h in HORIZONS:
        row = {"threshold": threshold, "horizon": h, "events": int(len(events)), "matched_events": int(len(matched)),
               "match_rate_pct": float(len(matched) / len(events) * 100.0) if len(events) else np.nan}
        for metric in ("abs_return_pct", "range_atr", "mfe_pct", "mae_pct"):
            e = matched[f"h{h}_{metric}_event"]
            c = matched[f"h{h}_{metric}_control"]
            valid = e.notna() & c.notna()
            row[f"event_median_{metric}"] = float(e[valid].median()) if valid.any() else np.nan
            row[f"control_median_{metric}"] = float(c[valid].median()) if valid.any() else np.nan
            row[f"median_edge_{metric}"] = float((e[valid] - c[valid]).median()) if valid.any() else np.nan
        out.append(row)
    return out


def turnover_impact(all_rows: pd.DataFrame, threshold: float, min_price: float, min_turnover: float) -> dict:
    base = (all_rows["close"] >= min_price) & (all_rows["rvol"] >= threshold)
    current = base & (all_rows["turnover_current_inclusive"] >= min_turnover)
    previous = base & (all_rows["turnover_previous_only"] >= min_turnover)
    rescued = current & ~previous
    lost = previous & ~current
    return {
        "threshold": threshold,
        "current_inclusive_events": int(current.sum()),
        "previous_only_events": int(previous.sum()),
        "rescued_by_current_bar": int(rescued.sum()),
        "rescued_share_of_production_pct": float(rescued.sum()/current.sum()*100.0) if current.sum() else np.nan,
        "previous_only_not_current": int(lost.sum()),
    }


def slot_impact(all_rows: pd.DataFrame, period: str, threshold: float, min_price: float, min_turnover: float) -> dict:
    eligible = (all_rows["close"] >= min_price) & (all_rows["turnover_previous_only"] >= min_turnover)
    standard = eligible & (all_rows["rvol"] >= threshold)
    slot = eligible & (all_rows["slot_rvol"] >= threshold)
    overlap = standard & slot
    union = standard | slot
    row = {
        "period": period,
        "threshold": threshold,
        "standard_events": int(standard.sum()),
        "slot_normalized_events": int(slot.sum()),
        "overlap_events": int(overlap.sum()),
        "jaccard_pct": float(overlap.sum()/union.sum()*100.0) if union.sum() else np.nan,
    }
    for h in (1, 5, 20):
        for label, mask in (("standard", standard), ("slot", slot)):
            row[f"h{h}_{label}_median_abs_return_pct"] = float(all_rows.loc[mask, f"h{h}_abs_return_pct"].median())
            row[f"h{h}_{label}_median_range_atr"] = float(all_rows.loc[mask, f"h{h}_range_atr"].median())
    return row


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f"file:{Path(args.db).resolve().as_posix()}?mode=ro", uri=True)
    try:
        frames = []
        symbols = load_symbols(con, args.exchange, args.period)
        for symbol in symbols:
            raw = load_frame(con, symbol, args.exchange, args.period)
            if len(raw) < args.min_history + max(HORIZONS) + 2:
                continue
            x = enrich(raw, args.period, args.window, args.min_history)
            x["symbol"] = symbol
            frames.append(x.reset_index(names="candle_time"))
        if not frames:
            raise RuntimeError("No usable data")
        all_rows = pd.concat(frames, ignore_index=True)

        matched = []
        for t in THRESHOLDS:
            matched.extend(matched_edges(all_rows, t, args.min_price, args.min_turnover))
        pd.DataFrame(matched).to_csv(out / f"matched_control_{args.period}.csv", index=False)

        turnover = [turnover_impact(all_rows, t, args.min_price, args.min_turnover) for t in THRESHOLDS]
        pd.DataFrame(turnover).to_csv(out / f"turnover_impact_{args.period}.csv", index=False)

        slot_rows = [slot_impact(all_rows, args.period, t, args.min_price, args.min_turnover) for t in THRESHOLDS]
        pd.DataFrame(slot_rows).to_csv(out / f"slot_normalization_{args.period}.csv", index=False)

        manifest = {
            "scanner": "technical.volume_spike",
            "stage": "robustness_2",
            "period": args.period,
            "symbols_in_db": len(symbols),
            "symbols_usable": int(all_rows["symbol"].nunique()),
            "rows": int(len(all_rows)),
            "thresholds": list(THRESHOLDS),
            "control_definition": "same symbol + quarter + intraday slot + 0.25 log10 previous-turnover bucket; controls have RVOL < 1.5",
            "turnover_variant": "production current-inclusive vs previous-only 20-bar average",
            "slot_variant": "same clock-slot previous 20 observations; daily/weekly equals standard RVOL",
        }
        (out / f"robustness_manifest_{args.period}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    finally:
        con.close()


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--period", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--exchange", default="BIST")
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--min-history", type=int, default=5)
    p.add_argument("--min-price", type=float, default=1.0)
    p.add_argument("--min-turnover", type=float, default=20_000_000.0)
    return p

if __name__ == "__main__":
    run(parser().parse_args())
