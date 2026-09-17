from __future__ import annotations

import argparse
import bisect
import json
import math
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from exact_replay_common import (
    add_forward_metrics,
    adx_series,
    average_turnover,
    bb_rank_series,
    finalize_events,
    fresh_from_mask,
    load_symbol,
    load_symbols,
    previous_rvol,
    production_rsi,
    recursive_ema,
    wilder_atr,
)

TECHNICAL_SCANNERS = {
    "technical.failed_breakout",
    "technical.decision_zone",
    "technical.trend_continuation",
    "technical.exhaustion",
}
EMA_PERIODS = (5, 8, 10, 13, 20, 21, 34, 50, 55, 89, 100, 144, 200, 233)


def market_structure_series(df: pd.DataFrame, pivot: int = 5):
    n = len(df)
    highs = df.high.to_numpy(dtype=float)
    lows = df.low.to_numpy(dtype=float)
    high_flag = np.zeros(n, dtype=bool)
    low_flag = np.zeros(n, dtype=bool)
    for j in range(pivot, n - pivot):
        high_flag[j] = highs[j] == np.max(highs[j - pivot : j + pivot + 1])
        low_flag[j] = lows[j] == np.min(lows[j - pivot : j + pivot + 1])

    tone = np.full(n, "neutral", dtype=object)
    swing_high = np.full(n, np.nan)
    swing_low = np.full(n, np.nan)
    last_highs: list[float] = []
    last_lows: list[float] = []
    for i in range(n):
        center = i - pivot
        if center >= pivot:
            if high_flag[center]:
                last_highs.append(float(highs[center]))
                if len(last_highs) > 2:
                    last_highs.pop(0)
            if low_flag[center]:
                last_lows.append(float(lows[center]))
                if len(last_lows) > 2:
                    last_lows.pop(0)
        if last_highs:
            swing_high[i] = last_highs[-1]
        if last_lows:
            swing_low[i] = last_lows[-1]
        if len(last_highs) >= 2 and len(last_lows) >= 2:
            high_state = "HH" if last_highs[-1] > last_highs[-2] else "LH"
            low_state = "HL" if last_lows[-1] > last_lows[-2] else "LL"
            if (high_state, low_state) == ("HH", "HL"):
                tone[i] = "positive"
            elif (high_state, low_state) == ("LH", "LL"):
                tone[i] = "negative"
            else:
                tone[i] = "warning"
    return tone, swing_high, swing_low


def trend_tone_series(close: pd.Series):
    n = len(close)
    values = close.to_numpy(dtype=float)
    ema = {period: recursive_ema(values, period) for period in EMA_PERIODS}
    tone = np.full(n, "warning", dtype=object)
    for i in range(n):
        available = [period for period in EMA_PERIODS if period <= i + 1]
        if not available:
            continue
        current = [ema[p][i] for p in available]
        bullish = sum(left > right for left, right in zip(current, current[1:], strict=False))
        bearish = sum(left < right for left, right in zip(current, current[1:], strict=False))
        pairs = max(len(current) - 1, 1)
        if bullish / pairs >= 0.75:
            tone[i] = "positive"
        elif bearish / pairs >= 0.75:
            tone[i] = "negative"
        else:
            tone[i] = "warning"
    return tone, ema


def profile_at(df: pd.DataFrame, i: int, lookback: int = 100, bins: int = 48):
    start = max(0, i - lookback + 1)
    bars = df.iloc[start : i + 1]
    low = float(bars.low.min())
    high = float(bars.high.max())
    if high <= low:
        return None, None, None
    width = (high - low) / bins
    profile = np.zeros(bins, dtype=float)
    for row in bars.itertuples(index=False):
        first = max(min(int((float(row.low) - low) / width), bins - 1), 0)
        last = max(min(math.ceil((float(row.high) - low) / width) - 1, bins - 1), first)
        profile[first : last + 1] += float(row.volume) / (last - first + 1)
    total = float(profile.sum())
    if total <= 0:
        return None, None, None
    poc_index = int(np.argmax(profile))
    selected = {poc_index}
    cumulative = float(profile[poc_index])
    lower, upper = poc_index - 1, poc_index + 1
    while cumulative < total * 0.70 and (lower >= 0 or upper < bins):
        lower_volume = float(profile[lower]) if lower >= 0 else -1.0
        upper_volume = float(profile[upper]) if upper < bins else -1.0
        chosen = upper if upper_volume >= lower_volume else lower
        selected.add(chosen)
        cumulative += float(profile[chosen])
        if chosen == upper:
            upper += 1
        else:
            lower -= 1
    return (
        low + (poc_index + 0.5) * width,
        low + min(selected) * width,
        low + (max(selected) + 1) * width,
    )


def failed_break_at(df: pd.DataFrame, i: int, level: float | None, direction: str) -> bool:
    if level is None or not np.isfinite(level):
        return False
    recent = df.iloc[max(0, i - 4) : i + 1]
    close = float(df.close.iloc[i])
    if direction == "down":
        return bool((recent.low < level).any() and close > level)
    return bool((recent.high > level).any() and close < level)


def oscillator_pivots(values: np.ndarray, low: bool, width: int = 5) -> list[int]:
    positions: list[int] = []
    for i in range(width, len(values) - width):
        window = values[i - width : i + width + 1]
        if not np.all(np.isfinite(window)):
            continue
        center = float(values[i])
        neighbours = np.concatenate((window[:width], window[width + 1 :]))
        if (center < float(np.min(neighbours))) if low else (center > float(np.max(neighbours))):
            positions.append(i)
    return positions


def strong_divergences_at(
    df: pd.DataFrame,
    i: int,
    oscillator: np.ndarray,
    atr: float,
    low_pivots: list[int],
    high_pivots: list[int],
) -> int:
    count = 0
    max_center = i - 5
    if max_center < 0:
        return 0
    for pivots, bullish in ((low_pivots, True), (high_pivots, False)):
        stop = bisect.bisect_right(pivots, max_center)
        eligible = pivots[:stop]
        if len(eligible) < 2:
            continue
        # Only second pivots confirmed in the last five bars can contribute.
        for first, second in zip(eligible, eligible[1:], strict=False):
            if not 5 <= second - first <= 60:
                continue
            age = i - (second + 5)
            if not 0 <= age <= 5:
                continue
            first_osc = float(oscillator[first])
            second_osc = float(oscillator[second])
            first_price = float(df.low.iloc[first] if bullish else df.high.iloc[first])
            second_price = float(df.low.iloc[second] if bullish else df.high.iloc[second])
            regular = (
                (bullish and second_osc > first_osc and second_price < first_price)
                or ((not bullish) and second_osc < first_osc and second_price > first_price)
            )
            hidden = (
                (bullish and second_osc < first_osc and second_price > first_price)
                or ((not bullish) and second_osc > first_osc and second_price < first_price)
            )
            if not (regular or hidden):
                continue
            points = 1 + int(age <= 2)
            points += int(atr > 0 and abs(second_price - first_price) / atr >= 0.75)
            points += int(abs(second_osc - first_osc) >= 5)
            count += int(points >= 3)
    return count


def near_confluence_at(
    current_close: float,
    atr: float,
    ema_values: list[float],
    profile: tuple[float | None, float | None, float | None],
    swing_high: float,
    swing_low: float,
    bb_lower: float,
    bb_middle: float,
    bb_upper: float,
) -> bool:
    if not np.isfinite(atr) or atr <= 0:
        return False
    levels: list[tuple[float, str]] = []
    levels.extend((float(value), "EMA") for value in ema_values if np.isfinite(value))
    levels.extend((float(value), "Profil") for value in profile if value is not None and np.isfinite(value))
    levels.extend((float(value), "Yapı") for value in (swing_high, swing_low) if np.isfinite(value))
    levels.extend((float(value), "Volatilite") for value in (bb_lower, bb_middle, bb_upper) if np.isfinite(value))
    levels.sort()
    clusters: list[list[tuple[float, str]]] = []
    for level in levels:
        if not clusters or level[0] - clusters[-1][0][0] > atr * 0.25:
            clusters.append([level])
        else:
            clusters[-1].append(level)
    return any(
        len({family for _, family in cluster}) >= 2
        and abs(sum(value for value, _ in cluster) / len(cluster) - current_close) / atr <= 0.75
        for cluster in clusters
    )


def exact_mask(df: pd.DataFrame, scanner: str):
    n = len(df)
    index = np.arange(n)
    close = df.close.to_numpy(dtype=float)
    low = df.low.to_numpy(dtype=float)
    high = df.high.to_numpy(dtype=float)
    atr = wilder_atr(df, 14)
    adx, _plus_di, _minus_di = adx_series(df, 14)
    rsi = production_rsi(df.close, 14)
    bbr, squeeze, bb_lower, bb_middle, bb_upper = bb_rank_series(df.close, 20, 100)
    rvol = previous_rvol(df.volume, 20, 5)
    turnover = average_turnover(df, 20)
    structure_tone, swing_high, swing_low = market_structure_series(df, 5)
    trend_tone, ema = trend_tone_series(df.close)

    prior_low = df.low.shift(1).rolling(20, min_periods=20).min().to_numpy(dtype=float)
    prior_high = df.high.shift(1).rolling(20, min_periods=20).max().to_numpy(dtype=float)
    pierced_down = (low < prior_low) & (prior_low <= close)
    pierced_up = (high > prior_high) & (prior_high >= close)
    stacked_bull = (close > ema[21]) & (close > ema[55])
    stacked_bear = (close < ema[21]) & (close < ema[55])
    stacked = stacked_bull | stacked_bear
    liquid = (index >= 59) & (close >= 1.0) & np.isfinite(turnover) & (turnover >= 20_000_000.0)

    if scanner == "technical.failed_breakout":
        pre = liquid & (pierced_down | pierced_up) & (squeeze < 8)
    elif scanner == "technical.decision_zone":
        pre = liquid & np.isfinite(bbr) & (bbr <= 20.0) & np.isfinite(adx) & (adx < 20.0)
        pre &= (squeeze >= 3) | (adx < 18.0)
    elif scanner == "technical.trend_continuation":
        pre = liquid & np.isfinite(adx) & (adx >= 25.0) & stacked & np.isfinite(rvol) & (rvol >= 1.0)
        # With ADX>=25, setup priority allows Trend continuation only when squeeze decision is inactive.
        pre &= squeeze < 3
        pre &= (structure_tone == trend_tone) & np.isin(structure_tone, ["positive", "negative"])
    elif scanner == "technical.exhaustion":
        pre = liquid & ((rsi <= 30.0) | (rsi >= 70.0)) & (pierced_down | pierced_up)
    else:
        raise ValueError(scanner)

    mask = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    low_pivots = oscillator_pivots(rsi, low=True, width=5) if scanner == "technical.exhaustion" else []
    high_pivots = oscillator_pivots(rsi, low=False, width=5) if scanner == "technical.exhaustion" else []

    for i in np.flatnonzero(pre):
        i = int(i)
        profile = profile_at(df, i, 100, 48)
        failed_down = failed_break_at(df, i, profile[1], "down") or failed_break_at(df, i, swing_low[i], "down")
        failed_up = failed_break_at(df, i, profile[2], "up") or failed_break_at(df, i, swing_high[i], "up")

        setup = "Yön arayışı / geçiş"
        setup_direction = 0
        if failed_down and squeeze[i] < 8:
            setup = "Destekte reddedilme / başarısız aşağı kırılım"
            setup_direction = 1
        elif failed_up and squeeze[i] < 8:
            setup = "Dirençte reddedilme / başarısız yukarı kırılım"
            setup_direction = -1
        elif squeeze[i] >= 3 or adx[i] < 18:
            setup = "Sıkışma / karar bölgesi"
            setup_direction = 0
        elif structure_tone[i] == trend_tone[i] and structure_tone[i] in {"positive", "negative"} and adx[i] >= 20:
            setup = "Trend devamı"
            setup_direction = 1 if structure_tone[i] == "positive" else -1
        elif scanner == "technical.exhaustion":
            available_ema = [ema[p][i] for p in EMA_PERIODS if p <= i + 1]
            confluence = near_confluence_at(
                close[i], atr[i], available_ema, profile, swing_high[i], swing_low[i], bb_lower[i], bb_middle[i], bb_upper[i]
            )
            divergences = strong_divergences_at(df, i, rsi, float(atr[i]), low_pivots, high_pivots)
            if divergences and confluence and (rsi[i] <= 35.0 or rsi[i] >= 65.0):
                setup = "Tükenme denemesi"
                setup_direction = 1 if rsi[i] <= 35.0 else -1

        if scanner == "technical.failed_breakout" and "reddedilme" in setup.casefold():
            mask[i] = True
            direction[i] = setup_direction
        elif scanner == "technical.decision_zone" and setup == "Sıkışma / karar bölgesi":
            mask[i] = True
            direction[i] = 0
        elif scanner == "technical.trend_continuation" and setup == "Trend devamı":
            mask[i] = True
            direction[i] = setup_direction
        elif scanner == "technical.exhaustion" and setup == "Tükenme denemesi":
            mask[i] = True
            direction[i] = setup_direction

    return mask, direction, atr, int(pre.sum())


def audit(db: Path, scanner: str, period: str, exchange: str, out_dir: Path, holdout: float) -> None:
    uri = f"file:{db.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    symbols = load_symbols(conn, exchange, period)
    rows: list[dict] = []
    eligible = 0
    prefilter_candidates = 0
    raw_events = 0
    for symbol in symbols:
        df = load_symbol(conn, symbol, exchange, period)
        if len(df) < 80:
            continue
        eligible += 1
        mask, direction, atr, candidates = exact_mask(df, scanner)
        prefilter_candidates += candidates
        raw_events += int(mask.sum())
        add_forward_metrics(
            rows,
            df,
            np.flatnonzero(mask),
            direction,
            atr,
            fresh_from_mask(mask),
            symbol,
        )
    conn.close()
    manifest = {
        "scanner": scanner,
        "period": period,
        "exchange": exchange,
        "symbols_in_db": len(symbols),
        "symbols_with_min_history": eligible,
        "exact_prefilter_candidates": prefilter_candidates,
        "raw_matches_before_forward_horizon": raw_events,
        "parity_note": "exact_production_technical_context_replay_v1",
        "production_source": "borsapp/main TechnicalMarketContextProvider + technical.market_screens",
    }
    events, summaries = finalize_events(rows, out_dir, manifest, holdout)
    print(json.dumps({**manifest, "events": len(events), "summary": summaries}, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--scanner", required=True, choices=sorted(TECHNICAL_SCANNERS))
    parser.add_argument("--period", required=True)
    parser.add_argument("--exchange", default="BIST")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--holdout", type=float, default=0.20)
    args = parser.parse_args()
    audit(Path(args.db), args.scanner, args.period, args.exchange, Path(args.out_dir), args.holdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
