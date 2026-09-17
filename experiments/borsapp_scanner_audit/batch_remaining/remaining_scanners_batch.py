from __future__ import annotations

import argparse
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
EMA_PERIODS = (5, 8, 13, 21, 55, 200)


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0)
    dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = dn.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = au / ad.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(s: pd.Series):
    m = ema(s, 12) - ema(s, 26)
    sig = ema(m, 9)
    return m, sig, m - sig


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df.close.shift(1)
    tr = pd.concat([(df.high - df.low), (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def adx(df: pd.DataFrame, n: int = 14):
    up = df.high.diff()
    down = -df.low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    pc = df.close.shift(1)
    tr = pd.concat([(df.high - df.low), (df.high - pc).abs(), (df.low - pc).abs()], axis=1).max(axis=1)
    atrn = tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    plus = 100 * plus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atrn
    minus = 100 * minus_dm.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / atrn
    dx = 100 * (plus - minus).abs() / (plus + minus).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False, min_periods=n).mean(), plus, minus


def stochastic(s: pd.Series, n: int = 10, smooth: int = 3, signal: int = 3):
    ll = s.rolling(n, min_periods=n).min()
    hh = s.rolling(n, min_periods=n).max()
    raw = 100 * (s - ll) / (hh - ll).replace(0, np.nan)
    k = raw.rolling(smooth, min_periods=smooth).mean()
    d = k.rolling(signal, min_periods=signal).mean()
    return k, d


def bb_rank(close: pd.Series, bb_n: int = 20, rank_n: int = 100) -> pd.Series:
    mid = sma(close, bb_n)
    sd = close.rolling(bb_n, min_periods=bb_n).std(ddof=0)
    width = (4 * sd) / mid.replace(0, np.nan)
    return width.rolling(rank_n, min_periods=rank_n).apply(lambda x: 100.0 * (np.sum(x <= x[-1]) / len(x)), raw=True)


def prior_rvol(volume: pd.Series, n: int = 20) -> pd.Series:
    return volume / volume.shift(1).rolling(n, min_periods=5).mean()


def inclusive_rvol(volume: pd.Series, n: int = 20) -> pd.Series:
    return volume / volume.rolling(n, min_periods=n).mean()


def average_turnover(df: pd.DataFrame, n: int = 20) -> pd.Series:
    return (df.close * df.volume).rolling(n, min_periods=5).mean()


def rising_or_cross(a: pd.Series, b: pd.Series) -> pd.Series:
    cross = (a > b) & (a.shift(1) <= b.shift(1))
    rising = (a > b) & (a > a.shift(1))
    return cross | rising


def load_symbol(conn: sqlite3.Connection, symbol: str, exchange: str, period: str) -> pd.DataFrame:
    q = """
    SELECT candle_time, open, high, low, close, volume
    FROM candles WHERE symbol=? AND exchange=? AND period=? ORDER BY candle_time
    """
    df = pd.read_sql_query(q, conn, params=(symbol, exchange, period))
    if df.empty:
        return df
    df['candle_time'] = pd.to_datetime(df.candle_time, errors='coerce')
    for c in ['open','high','low','close','volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df.dropna().reset_index(drop=True)


def signal_mask(df: pd.DataFrame, scanner: str):
    c, v = df.close, df.volume
    rv_prior = prior_rvol(v)
    rv20 = inclusive_rvol(v)
    turn = average_turnover(df)
    liquid = (c >= 1.0) & (turn >= 20_000_000)
    r14 = rsi(c, 14)
    r7 = rsi(c, 7)
    m, ms, mh = macd(c)
    e = {n: ema(c, n) for n in EMA_PERIODS}
    s = {n: sma(c, n) for n in (5,8,21,50,55,200)}
    a = atr(df)
    ax, pdi, mdi = adx(df)
    bbr = bb_rank(c)

    if scanner == 'technical.failed_breakout':
        lo20 = df.low.shift(1).rolling(20, min_periods=20).min()
        hi20 = df.high.shift(1).rolling(20, min_periods=20).max()
        bull = liquid & (df.low < lo20) & (c >= lo20)
        bear = liquid & (df.high > hi20) & (c <= hi20)
        return bull | bear, np.where(bull, 1, np.where(bear, -1, 0))

    if scanner == 'technical.decision_zone':
        mask = liquid & (bbr <= 20) & (ax < 20)
        return mask, np.zeros(len(df), dtype=int)

    if scanner == 'technical.trend_continuation':
        bull = liquid & (ax >= 25) & (c > e[21]) & (c > e[55]) & (rv_prior >= 1.0)
        bear = liquid & (ax >= 25) & (c < e[21]) & (c < e[55]) & (rv_prior >= 1.0)
        return bull | bear, np.where(bull, 1, np.where(bear, -1, 0))

    if scanner == 'technical.exhaustion':
        lo20 = df.low.shift(1).rolling(20, min_periods=20).min()
        hi20 = df.high.shift(1).rolling(20, min_periods=20).max()
        bull = liquid & (r14 <= 30) & (df.low < lo20) & (c >= lo20)
        bear = liquid & (r14 >= 70) & (df.high > hi20) & (c <= hi20)
        return bull | bear, np.where(bull, 1, np.where(bear, -1, 0))

    if scanner == 'signal.macd_positive_cross':
        cond = (r14 > 30) & (m > 0) & rising_or_cross(m, ms)
        return cond, np.ones(len(df), dtype=int)

    if scanner == 'signal.rsi_momentum_volume':
        cond = (r7 > 60) & (((r7 > 50) & (r7.shift(1) <= 50)) | ((r7 > 50) & (r7 > r7.shift(1)))) & (v > v.rolling(10, min_periods=10).mean() * 1.5)
        return cond, np.ones(len(df), dtype=int)

    if scanner == 'signal.rsi_macd_volume':
        rsi_leg = (r14 < 70) & (((r14 > 50) & (r14.shift(1) <= 50)) | ((r14 > 50) & (r14 > r14.shift(1))))
        macd_leg = rising_or_cross(m, ms)
        cond = rsi_leg & macd_leg & (v > v.rolling(20, min_periods=20).mean() * 1.5)
        return cond, np.ones(len(df), dtype=int)

    if scanner.startswith('signal.smi_macd_'):
        k, d = stochastic(c, 10, 3, 3)
        smi_up = rising_or_cross(k, d)
        hist_rising = mh > mh.shift(1)
        vol_ok = v > v.rolling(20, min_periods=20).mean() * 1.5
        full = (c > s[200]) & vol_ok
        if scanner == 'signal.smi_macd_positive':
            cond = smi_up & (k > 0) & (mh > 0) & hist_rising
        elif scanner == 'signal.smi_macd_positive_volume_confirmed':
            cond = smi_up & (k > 0) & (mh > 0) & hist_rising & full
        elif scanner == 'signal.smi_macd_early':
            cond = smi_up & (k < 0) & (mh < 0) & hist_rising & (~full)
        else:
            cond = smi_up & (k < 0) & (mh < 0) & hist_rising & full
        return cond, np.ones(len(df), dtype=int)

    if scanner == 'signal.sma_macd_volume':
        ma_ok = (c > s[5]) & (c > s[8]) & (c > s[21]) & (c > s[50]) & (c > s[55]) & (c > s[200])
        cond = ma_ok & (m > 0) & rising_or_cross(m, ms) & (v > v.rolling(20, min_periods=20).mean() * 1.5)
        return cond, np.ones(len(df), dtype=int)

    if scanner == 'signal.ema_trend_volume':
        long_ok = (c > e[21]) & (c > e[55]) & (c > e[200])
        short_ok = rising_or_cross(e[8], e[13]) & rising_or_cross(e[5], e[8]) & rising_or_cross(e[5], e[13])
        cond = long_ok & short_ok & (v > v.rolling(20, min_periods=20).mean() * 1.5)
        return cond, np.ones(len(df), dtype=int)

    if scanner == 'ma.near_zone':
        # Research proxy for qualified MA proximity: closest of EMA21/55/200 within 1 ATR.
        dist = pd.concat([(c - e[21]).abs(), (c - e[55]).abs(), (c - e[200]).abs()], axis=1).min(axis=1)
        nearest = pd.concat([e[21], e[55], e[200]], axis=1).mean(axis=1)
        mask = dist <= a
        direction = np.where(c >= nearest, 1, -1)
        return mask, direction

    if scanner == 'decision.panel_v645':
        # Approximate parity of the documented v6.4.5 score engine. This is marked proxy in the output.
        score = pd.Series(0.0, index=df.index)
        score += (c > s[21]).astype(int) * 4
        score += (s[21] > s[50]).astype(int) * 4
        score += (s[50] > s[200]).astype(int) * 4
        score += (s[21] > s[21].shift(5)).astype(int) * 3
        score += (s[50] > s[50].shift(10)).astype(int) * 3
        score += (s[200] > s[200].shift(20)).astype(int) * 2
        score += ((e[5] > e[8]) & (e[8] > e[13])).astype(int) * 3
        score += ((e[5] > e[5].shift(1)) & (e[8] > e[8].shift(1)) & (e[13] > e[13].shift(1))).astype(int) * 2
        score += (m > 0).astype(int) * 4
        score += (m > ms).astype(int) * 5
        score += (mh > 0).astype(int) * 6
        score += ((r14 >= 50) & (r14 <= 70)).astype(int) * 5
        score += np.select([rv_prior >= 3, rv_prior >= 2, rv_prior >= 1.5, rv_prior >= 1.2, rv_prior >= 1], [18,16,12,7,3], default=0)
        score += (ax >= 25).astype(int) * 5
        score += (pdi > mdi).astype(int) * 3
        prev20 = df.high.shift(1).rolling(20, min_periods=20).max()
        breakout = c > prev20
        mask = (score >= 75) & breakout
        return mask, np.ones(len(df), dtype=int)

    raise ValueError(scanner)


def summarize(events: pd.DataFrame, split: str) -> dict:
    x = events if split == 'all' else events[events['split'] == split]
    out = {'split': split, 'events': int(len(x)), 'symbols': int(x.symbol.nunique()) if len(x) else 0}
    if x.empty:
        return out
    out['fresh_rate'] = float(x.fresh.mean())
    for h in HORIZONS:
        sr = x[f'ret_{h}'] * x.direction.replace(0, 1)
        out[f'hit_{h}'] = float((sr > 0).mean())
        out[f'median_signed_{h}'] = float(sr.median())
        out[f'median_abs_{h}'] = float(x[f'ret_{h}'].abs().median())
        out[f'median_mfe_{h}'] = float(x[f'mfe_{h}'].median())
        out[f'median_mae_{h}'] = float(x[f'mae_{h}'].median())
        out[f'median_range_atr_{h}'] = float(x[f'range_atr_{h}'].median())
    return out


def audit(db: Path, scanner: str, period: str, exchange: str, out_dir: Path, holdout: float):
    uri = f'file:{db.as_posix()}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    syms = [r[0] for r in conn.execute('SELECT DISTINCT symbol FROM candles WHERE exchange=? AND period=? ORDER BY symbol', (exchange, period)).fetchall()]
    rows = []
    eligible = 0
    for sym in syms:
        df = load_symbol(conn, sym, exchange, period)
        if len(df) < 80:
            continue
        eligible += 1
        mask, direction = signal_mask(df, scanner)
        a = atr(df)
        idxs = np.flatnonzero(np.asarray(mask.fillna(False) if hasattr(mask, 'fillna') else mask, dtype=bool))
        for i in idxs:
            if i + max(HORIZONS) >= len(df) or not np.isfinite(a.iloc[i]) or a.iloc[i] <= 0:
                continue
            prev = bool(mask.iloc[i-1]) if i > 0 and hasattr(mask, 'iloc') else False
            row = {'symbol': sym, 'time': df.candle_time.iloc[i], 'direction': int(direction[i]), 'fresh': not prev}
            entry = float(df.close.iloc[i])
            for h in HORIZONS:
                fut = df.iloc[i+1:i+h+1]
                ret = float(df.close.iloc[i+h] / entry - 1)
                row[f'ret_{h}'] = ret
                if row['direction'] >= 0:
                    row[f'mfe_{h}'] = float(fut.high.max() / entry - 1)
                    row[f'mae_{h}'] = float(fut.low.min() / entry - 1)
                else:
                    row[f'mfe_{h}'] = float(entry / fut.low.min() - 1)
                    row[f'mae_{h}'] = float(entry / fut.high.max() - 1)
                row[f'range_atr_{h}'] = float((fut.high.max() - fut.low.min()) / a.iloc[i])
            rows.append(row)
    conn.close()
    ev = pd.DataFrame(rows)
    if not ev.empty:
        ev = ev.sort_values('time').reset_index(drop=True)
        cut = int(math.floor(len(ev) * (1 - holdout)))
        ev['split'] = np.where(np.arange(len(ev)) < cut, 'research', 'holdout')
    else:
        ev['split'] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    ev.to_csv(out_dir / 'events.csv', index=False)
    summary = [summarize(ev, s) for s in ('all','research','holdout')]
    pd.DataFrame(summary).to_csv(out_dir / 'summary.csv', index=False)
    proxy = scanner in {'ma.near_zone','decision.panel_v645'}
    manifest = {
        'scanner': scanner, 'period': period, 'exchange': exchange,
        'symbols_in_db': len(syms), 'symbols_with_min_history': eligible,
        'events': int(len(ev)), 'holdout_fraction': holdout,
        'parity_note': 'research_proxy_requires_production-engine_validation' if proxy else 'production_rule_reconstructed_from_audit_spec',
        'horizons': HORIZONS,
    }
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--db', required=True)
    p.add_argument('--scanner', required=True)
    p.add_argument('--period', required=True)
    p.add_argument('--exchange', default='BIST')
    p.add_argument('--out-dir', required=True)
    p.add_argument('--holdout', type=float, default=0.20)
    a = p.parse_args()
    audit(Path(a.db), a.scanner, a.period, a.exchange, Path(a.out_dir), a.holdout)


if __name__ == '__main__':
    main()
