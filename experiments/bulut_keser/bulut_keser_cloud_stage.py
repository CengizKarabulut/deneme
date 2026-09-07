"""BulutKeser Kumo-position entry-quality research.

The original scan is kept fixed and only the price location relative to the
currently displayed Ichimoku Kumo is separated:
- all (no cloud filter)
- above cloud
- inside cloud
- below cloud

Displayed Kumo semantics are respected without look-ahead: Senkou A/B raw
values are shifted forward 26 bars on the chart, therefore the cloud visible
at bar t is raw_span[t-26] => pandas shift(26).
"""
from __future__ import annotations

import argparse, json, sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_TAVAN = Path(__file__).resolve().parents[1] / "tavan_tarama"
sys.path.insert(0, str(_TAVAN))
from tavan_entry_stage import dmi  # noqa: E402

_BB = Path(__file__).resolve().parents[1] / "bb_squeeze"
sys.path.insert(0, str(_BB))
from bb_squeeze_entry_stage import (  # noqa: E402
    MarketDataStore, PERIODS, WARMUP, structure, metrics, bounds_for, collect
)


def midpoint(h: pd.Series, l: pd.Series, length: int) -> pd.Series:
    return (h.rolling(length, min_periods=length).max() + l.rolling(length, min_periods=length).min()) / 2.0


def atr14(frame: pd.DataFrame) -> pd.Series:
    h = pd.to_numeric(frame['high'], errors='coerce')
    l = pd.to_numeric(frame['low'], errors='coerce')
    c = pd.to_numeric(frame['close'], errors='coerce')
    pc = c.shift(1)
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()


def indicators(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    h = pd.to_numeric(out['high'], errors='coerce')
    l = pd.to_numeric(out['low'], errors='coerce')
    c = pd.to_numeric(out['close'], errors='coerce')
    v = pd.to_numeric(out['volume'], errors='coerce')

    # ADX/DMI
    _, _, adx, _ = dmi(out, 14)
    out['adx14'] = adx

    # Bollinger Bands(20,2)
    basis = c.rolling(20, min_periods=20).mean()
    sd = c.rolling(20, min_periods=20).std(ddof=0)
    out['bb_basis'] = basis
    out['bb_upper'] = basis + 2.0 * sd
    out['bb_lower'] = basis - 2.0 * sd

    # Relative volume using previous 20 same-timeframe bars, current bar excluded.
    rvavg = v.shift(1).rolling(20, min_periods=20).mean()
    out['rvol20'] = v / rvavg.replace(0.0, np.nan)

    # Ichimoku 9,26,52,26
    tenkan = midpoint(h, l, 9)
    kijun = midpoint(h, l, 26)
    span_a_raw = (tenkan + kijun) / 2.0
    span_b_raw = midpoint(h, l, 52)

    # Cloud visible at current bar: values computed 26 bars ago and plotted here.
    span_a_display = span_a_raw.shift(26)
    span_b_display = span_b_raw.shift(26)
    cloud_top = pd.concat([span_a_display, span_b_display], axis=1).max(axis=1)
    cloud_bottom = pd.concat([span_a_display, span_b_display], axis=1).min(axis=1)

    out['tenkan'] = tenkan
    out['kijun'] = kijun
    out['tenkan_cross_up'] = ((tenkan > kijun) & (tenkan.shift(1) <= kijun.shift(1))).fillna(False)
    out['senkou_a_display'] = span_a_display
    out['senkou_b_display'] = span_b_display
    out['cloud_top'] = cloud_top
    out['cloud_bottom'] = cloud_bottom
    out['atr14'] = atr14(out)
    return out


def entry_variants() -> list[dict[str, Any]]:
    return [
        {'name': 'all', 'cloud_position': 'all'},
        {'name': 'above', 'cloud_position': 'above'},
        {'name': 'inside', 'cloud_position': 'inside'},
        {'name': 'below', 'cloud_position': 'below'},
    ]


def entry_events(d: pd.DataFrame, v: dict[str, Any]) -> pd.Series:
    c = pd.to_numeric(d['close'], errors='coerce')
    adx = pd.to_numeric(d['adx14'], errors='coerce')
    rv = pd.to_numeric(d['rvol20'], errors='coerce')
    top = pd.to_numeric(d['cloud_top'], errors='coerce')
    bot = pd.to_numeric(d['cloud_bottom'], errors='coerce')

    common = (
        d['tenkan_cross_up']
        & (adx >= 20.0) & (adx <= 40.0)
        & (c > pd.to_numeric(d['bb_lower'], errors='coerce'))
        & (c < pd.to_numeric(d['bb_upper'], errors='coerce'))
        & (rv > 1.20)
    )

    pos = v['cloud_position']
    if pos == 'all':
        cond = common
    elif pos == 'above':
        cond = common & top.notna() & (c > top)
    elif pos == 'inside':
        cond = common & top.notna() & bot.notna() & (c >= bot) & (c <= top)
    elif pos == 'below':
        cond = common & bot.notna() & (c < bot)
    else:
        raise ValueError(pos)
    return cond.fillna(False)


def initial_stop(d: pd.DataFrame, sp: int, entry: float, p: dict[str, Any]) -> tuple[float, float]:
    a = float(d['atr14'].iloc[sp])
    if not np.isfinite(a) or a <= 0:
        a = max(entry * .02, 1e-6)
    atr_stop = entry - float(p['stop_atr']) * a
    if p['stop_mode'] == 'atr':
        raw = atr_stop
    else:
        start = max(0, sp - int(p['swing']) + 1)
        sw = float(pd.to_numeric(d['low'].iloc[start:sp+1], errors='coerce').min())
        ss = sw - float(p['buffer']) * a
        raw = ss if np.isfinite(ss) and ss < entry else atr_stop
    risk = entry - raw
    risk = min(max(risk, .60*a), 2.60*a)
    return entry-risk, risk


def simulate(d: pd.DataFrame, sp: int, p: dict[str, Any]) -> dict[str, Any] | None:
    ep = sp + 1
    if ep >= len(d):
        return None
    entry = float(d['open'].iloc[ep])
    if not np.isfinite(entry) or entry <= 0:
        return None
    stop, risk = initial_stop(d, sp, entry, p)
    tp1, tp2, tp3 = entry+risk, entry+2*risk, entry+3*risk
    remaining = 1.0; cash = 0.0; h1 = h2 = h3 = False
    trail = False; highest = entry; minlow = entry; maxhigh = entry
    last = min(len(d)-1, ep + int(p['max_hold']) - 1)
    exit_pos = ep; reason = 'TIME'

    for pos in range(ep, last+1):
        row = d.iloc[pos]
        hi = float(row['high']); lo = float(row['low']); cl = float(row['close'])
        highest = max(highest, hi); maxhigh = max(maxhigh, hi); minlow = min(minlow, lo)
        # Conservative ambiguity rule: stop before target.
        if lo <= stop:
            cash += remaining * stop; remaining = 0.0; exit_pos = pos
            reason = 'TRAIL' if trail else 'STOP'; break
        if not h1 and hi >= tp1:
            q = min(remaining, .30); cash += q*tp1; remaining -= q; h1 = True
        if remaining > 1e-12 and not h2 and hi >= tp2:
            q = min(remaining, .30); cash += q*tp2; remaining -= q; h2 = True; trail = True
        if remaining > 1e-12 and not h3 and hi >= tp3:
            q = min(remaining, .20); cash += q*tp3; remaining -= q; h3 = True
        if remaining > 1e-12 and trail:
            a = float(row['atr14'])
            if np.isfinite(a) and a > 0:
                stop = max(stop, highest - float(p['trail'])*a)
        if pos == last and remaining > 1e-12:
            cash += remaining*cl; remaining = 0.0; exit_pos = pos; reason = 'TIME'; break

    pnl = cash - entry
    return {
        'signal_time': pd.Timestamp(d.index[sp]), 'entry_time': pd.Timestamp(d.index[ep]),
        'exit_time': pd.Timestamp(d.index[exit_pos]), 'entry': entry, 'risk': risk,
        'realized_r': pnl/risk, 'mfe_r': (maxhigh-entry)/risk, 'mae_r': (minlow-entry)/risk,
        'tp1_hit': h1, 'tp2_hit': h2, 'tp3_hit': h3, 'exit_reason': reason, 'exit_pos': exit_pos,
    }


def classify(row: dict[str, Any]) -> str:
    m = row['stitched']; n = int(m.get('trades', 0)); pf = float(m.get('profit_factor') or 0); e = float(m.get('expectancy_r', 0))
    pos = row['positive_folds']; worst = row['worst_fold_expectancy_r']
    if n < 30: return 'INSUFFICIENT_SAMPLE'
    if pos == 4 and pf > 1.20 and e > 0.08 and worst > 0: return 'ROBUST_STRONG'
    if pos >= 3 and pf > 1.10 and e > 0: return 'ROBUST_PROMISING'
    if pf > 1 and e > 0: return 'POSITIVE_UNSTABLE'
    return 'REJECT'


def analyze(db: str, period: str) -> dict[str, Any]:
    entries = entry_variants(); p = structure(period)
    frames = []; times = {e['name']: [] for e in entries}; counts = Counter()

    with MarketDataStore(db, read_only=True) as store:
        syms = store.list_symbols('BIST', period)
        for i, sym in enumerate(syms, 1):
            fr = store.load_dataframe(sym, 'BIST', period, limit=0)
            if fr is None or len(fr) <= WARMUP + 22:
                continue
            d = indicators(fr); pbe = {}
            for e in entries:
                ev = entry_events(d, e)
                ps = [int(x) for x in np.flatnonzero(ev.to_numpy(bool)) if x >= WARMUP and x+1 < len(d)]
                pbe[e['name']] = ps
                counts[e['name']] += len(ps)
                times[e['name']].extend(pd.Timestamp(d.index[x]) for x in ps)
            if any(pbe.values()):
                frames.append((sym, d, pbe))
            if i % 100 == 0 or i == len(syms):
                print(f'[{period}] {i}/{len(syms)}', flush=True)

    for k in times:
        times[k].sort()

    rows = []
    for e in entries:
        b = bounds_for(times[e['name']])
        if not b:
            continue
        folds = []; stitched = []
        for fi in range(4):
            tr = collect(frames, e['name'], p, b[fi], b[fi+1])
            stitched.extend(tr)
            folds.append({'fold': fi+1, 'metrics': metrics(tr)})
        sm = metrics(stitched)
        ex = [float(f['metrics'].get('expectancy_r', 0)) for f in folds]
        row = {
            'entry': e, 'signal_count': counts[e['name']], 'folds': folds, 'stitched': sm,
            'positive_folds': sum(x > 0 for x in ex),
            'worst_fold_expectancy_r': float(min(ex)),
            'median_fold_expectancy_r': float(np.median(ex)),
        }
        row['classification'] = classify(row)
        rows.append(row)

    rank = {'ROBUST_STRONG': 4, 'ROBUST_PROMISING': 3, 'POSITIVE_UNSTABLE': 2, 'REJECT': 1, 'INSUFFICIENT_SAMPLE': 0}
    rows.sort(key=lambda r: (rank[r['classification']], r['positive_folds'], r['worst_fold_expectancy_r'], r['median_fold_expectancy_r'], float(r['stitched'].get('expectancy_r', 0))), reverse=True)
    by_name = {r['entry']['name']: r for r in rows}
    return {
        'version': 'bulut-keser-cloud-position-v1', 'period': period,
        'method': 'Original scan fixed; only Kumo position separated; same structural exit; entry-specific four chronological windows; costs included',
        'kumo_semantics': 'Displayed current Kumo = raw Senkou A/B shifted 26 bars; no look-ahead',
        'rows': rows, 'by_name': by_name, 'best': rows[0] if rows else None,
        'warning': 'Historical research on observed data; future unseen bars are true forward validation.'
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True)
    ap.add_argument('--period', choices=PERIODS, required=True)
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    result = analyze(a.db, a.period)
    p = Path(a.output); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
