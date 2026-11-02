import requests
import math
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

TG_TOKEN = '8999488432:AAG5OlXC58i_I4Zqs_Q3r9zZdFYSDePBGLo'
TG_CHAT  = '6037933384'

LUX_H    = 8
LUX_MULT = 3
SL_PCT   = 0.08

ENDPOINTS = [
    'https://data-api.binance.vision/api/v3/klines',
    'https://api.binance.com/api/v3/klines',
]

TF_CONFIG = {
    '30m': {'bars_30d': 1440, 'extra': 600},
    '1h':  {'bars_30d': 720,  'extra': 300},
    '4h':  {'bars_30d': 180,  'extra': 100},
}

SYMS_30M = [
    'BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','NEARUSDT','WLDUSDT',
    'LTCUSDT','PYTHUSDT','UNIUSDT','FILUSDT','APTUSDT','ONDOUSDT','RSRUSDT','TIAUSDT',
    'AVAXUSDT','INJUSDT','STXUSDT','BCHUSDT','SUIUSDT','ZROUSDT',
    'TAOUSDT','TRUMPUSDT','PENGUUSDT','HYPEUSDT','JTOUSDT','VIRTUALUSDT',
    'DASHUSDT','JUPUSDT','XLMUSDT','ETCUSDT','LDOUSDT','CRVUSDT','SANDUSDT','POLUSDT',
    'KAIAUSDT','CFXUSDT','ICPUSDT',
    'ADAUSDT','DOTUSDT','LINKUSDT','OPUSDT','MKRUSDT','WIFUSDT','TONUSDT','EIGENUSDT',
    'MOVEUSDT','ORDIUSDT','ARUSDT','GALAUSDT','MATICUSDT','FETUSDT','RENDERUSDT',
    'APEUSDT','GMTUSDT','FLOWUSDT','EGLDUSDT','VETUSDT','ZILUSDT','RVNUSDT','CHZUSDT'
]
SYMS_1H = [
    'BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','NEARUSDT','WLDUSDT',
    'LTCUSDT','PYTHUSDT','UNIUSDT','FILUSDT','APTUSDT','ONDOUSDT','RSRUSDT','TIAUSDT',
    'AVAXUSDT','INJUSDT','STXUSDT','BCHUSDT','AAVEUSDT','SUIUSDT','ZROUSDT',
    'TAOUSDT','TRUMPUSDT','PENGUUSDT','HYPEUSDT','TRXUSDT','JTOUSDT','VIRTUALUSDT',
    'DASHUSDT','JUPUSDT','XLMUSDT','ETCUSDT','LDOUSDT','CRVUSDT','SANDUSDT','POLUSDT',
    'KAIAUSDT','CFXUSDT','ICPUSDT',
    'ADAUSDT','DOTUSDT','LINKUSDT','OPUSDT','MKRUSDT','WIFUSDT','TONUSDT','EIGENUSDT',
    'MOVEUSDT','ORDIUSDT','ARUSDT','GALAUSDT','MATICUSDT','FETUSDT','RENDERUSDT',
    'APEUSDT','GMTUSDT','FLOWUSDT','EGLDUSDT','VETUSDT','ZILUSDT','RVNUSDT','CHZUSDT'
]
SYMS_4H = [
    'PENGUUSDT','UNIUSDT','PYTHUSDT','WLDUSDT','TAOUSDT','BCHUSDT','APTUSDT','NEARUSDT',
    'INJUSDT','DOGEUSDT','TIAUSDT','ONDOUSDT','FILUSDT','LTCUSDT','BNBUSDT','RSRUSDT',
    'ZROUSDT','VIRTUALUSDT','CRVUSDT','LDOUSDT','JTOUSDT',
    'SANDUSDT','DASHUSDT','RENDERUSDT','ETCUSDT',
    'MKRUSDT','ORDIUSDT','ARUSDT','GALAUSDT','MATICUSDT',
    'APEUSDT','FLOWUSDT','EGLDUSDT','VETUSDT','CHZUSDT',
    'BTCUSDT','ETHUSDT','SOLUSDT','XRPUSDT','ADAUSDT','DOTUSDT','LINKUSDT'
]

SYMS_MAP = {'30m': SYMS_30M, '1h': SYMS_1H, '4h': SYMS_4H}

def fetch_klines_endtime(sym, tf, end_ms, limit=1000):
    for base in ENDPOINTS:
        url = f'{base}?symbol={sym}&interval={tf}&limit={limit}&endTime={end_ms}'
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            pass
    return None

def fetch_klines_tf(sym, tf, need):
    all_raw = []
    end_ms = int(time.time() * 1000)
    while len(all_raw) < need:
        batch = fetch_klines_endtime(sym, tf, end_ms=end_ms, limit=1000)
        if not batch:
            break
        all_raw = batch + all_raw
        end_ms = int(batch[0][0]) - 1
        if len(batch) < 1000:
            break
        time.sleep(0.1)
    return all_raw if all_raw else None

def find_round_tp(price, is_bull):
    mag = 10 ** (math.floor(math.log10(price)) - 1)
    raw = math.ceil(price / mag) * mag if is_bull else math.floor(price / mag) * mag
    cap = price * 1.03 if is_bull else price * 0.97
    return min(raw, cap) if is_bull else max(raw, cap)

def calc_nwe_all(closes):
    n = len(closes)
    coefs = [math.exp(-(i*i) / (LUX_H*LUX_H*2)) for i in range(n)]
    outs = []
    for bar in range(n):
        o, d = 0, 0
        for i in range(bar+1):
            o += closes[bar-i] * coefs[i]
            d += coefs[i]
        outs.append(o/d)
    mae = sum(abs(closes[i] - outs[i]) for i in range(n)) / n * LUX_MULT
    uppers = [o + mae for o in outs]
    lowers = [o - mae for o in outs]
    return uppers, lowers, outs

def tp_bucket(pct):
    if pct < 1.0: return '0-1%'
    if pct < 2.0: return '1-2%'
    return '2-3%'

def breakout_bucket(pct):
    if pct < 0.5: return '小(<0.5%)'
    if pct < 1.5: return '中(0.5-1.5%)'
    return '大(>1.5%)'

def nwe_slope(outs, i, lookback=5):
    if i < lookback:
        return 'unknown'
    slope = outs[i] - outs[i - lookback]
    return '上升' if slope > 0 else '下降'

def backtest_sym(sym, raw, bars_30d):
    n = len(raw)
    closes = [float(k[4]) for k in raw]
    open_times = [int(k[0]) for k in raw]
    uppers, lowers, outs = calc_nwe_all(closes)

    scan_start = max(100, n - bars_30d - 500)
    scan_end   = n - 500

    results = []
    for i in range(scan_start, scan_end):
        prev_close = closes[i - 1]
        upper = uppers[i - 1]
        lower = lowers[i - 1]

        is_long  = prev_close < lower
        is_short = prev_close > upper
        if not is_long and not is_short:
            continue

        entry = closes[i]
        tp = find_round_tp(entry, is_long)
        tp_pct = abs(tp - entry) / entry * 100
        if tp_pct <= 0.1:
            continue

        sl = entry * (1 - SL_PCT) if is_long else entry * (1 + SL_PCT)

        if is_long:
            breakout_pct = abs(prev_close - lower) / lower * 100
        else:
            breakout_pct = abs(prev_close - upper) / upper * 100

        slope = nwe_slope(outs, i - 1)

        sig_dt = datetime.fromtimestamp(open_times[i] / 1000, tz=timezone(timedelta(hours=8)))
        hour = sig_dt.hour

        hit = None
        for j in range(i + 1, min(i + 501, n)):
            c = closes[j]
            if is_long:
                if c >= tp: hit = 'win'; break
                if c <= sl: hit = 'loss'; break
            else:
                if c <= tp: hit = 'win'; break
                if c >= sl: hit = 'loss'; break

        if hit:
            results.append({
                'sym': sym,
                'direction': 'long' if is_long else 'short',
                'hour': hour,
                'tp_bucket': tp_bucket(tp_pct),
                'breakout': breakout_bucket(breakout_pct),
                'slope': slope,
                'result': hit,
            })

    return results

def send_tg(msg):
    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        requests.post(url, json={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    except:
        pass

def stats(records):
    w = sum(1 for r in records if r['result'] == 'win')
    t = len(records)
    return w, t, w/t*100 if t else 0

def dim_table(all_results, key, title, min_count=20):
    groups = defaultdict(list)
    for r in all_results:
        groups[r[key]].append(r)
    rows = []
    for k, v in sorted(groups.items(), key=lambda x: -stats(x[1])[2]):
        w, t, wr = stats(v)
        if t < min_count:
            continue
        rows.append((k, t, w, t-w, wr))
    lines = [f'<b>▶ {title}</b>']
    for k, t, w, l, wr in rows:
        bar = '█' * int(wr/10) + '░' * (10 - int(wr/10))
        lines.append(f'{str(k):12s} {wr:5.1f}% {bar} [{t}次 {w}W/{l}L]')
    return '\n'.join(lines)

def run_tf(tf):
    syms = SYMS_MAP[tf]
    cfg = TF_CONFIG[tf]
    bars_30d = cfg['bars_30d']
    need = bars_30d + cfg['extra']

    all_results = []
    for sym in syms:
        raw = fetch_klines_tf(sym, tf, need)
        if not raw or len(raw) < bars_30d + 100:
            print(f'{sym}: 資料不足')
            continue
        res = backtest_sym(sym, raw, bars_30d)
        all_results.extend(res)
        print(f'{sym}: {len(res)} 筆')
        time.sleep(0.05)

    if not all_results:
        send_tg(f'[{tf}] 無資料')
        return

    total_w, total_t, total_wr = stats(all_results)
    print(f'\n[{tf}] 總計: {total_w}W/{total_t-total_w}L = {total_wr:.1f}% [{total_t}次]')

    msg1 = f'📊 <b>NWE {tf.upper()} 深度回測（近30天）</b>\n總計: {total_w}W/{total_t-total_w}L = {total_wr:.1f}%  [{total_t}次]\n\n'
    msg1 += dim_table(all_results, 'direction', '方向')
    send_tg(msg1)
    time.sleep(1)

    send_tg(dim_table(all_results, 'tp_bucket', 'TP距離'))
    time.sleep(1)

    send_tg(dim_table(all_results, 'breakout', '突破幅度'))
    time.sleep(1)

    send_tg(dim_table(all_results, 'slope', 'NWE趨勢方向'))
    time.sleep(1)

    # 幣種排名
    sym_groups = defaultdict(list)
    for r in all_results:
        sym_groups[r['sym']].append(r)
    sym_rows = []
    for sym, v in sym_groups.items():
        w, t, wr = stats(v)
        if t >= 20:
            sym_rows.append((sym.replace('USDT',''), t, w, t-w, wr))
    sym_rows.sort(key=lambda x: -x[4])

    lines = [f'<b>▶ [{tf.upper()}] 幣種勝率排名（≥20次）</b>']
    for name, t, w, l, wr in sym_rows:
        mark = '🏆' if wr >= 93 else ('⚠️' if wr < 80 else '')
        lines.append(f'{mark}{name:10s} {wr:5.1f}%  [{t}次 {w}W/{l}L]')
    send_tg('\n'.join(lines))
    time.sleep(1)

    # 小時排名
    hour_groups = defaultdict(list)
    for r in all_results:
        hour_groups[r['hour']].append(r)
    hour_rows = []
    for h in range(24):
        v = hour_groups[h]
        if not v: continue
        w, t, wr = stats(v)
        hour_rows.append((h, t, w, t-w, wr))
    hour_rows.sort(key=lambda x: -x[4])

    lines = [f'<b>▶ [{tf.upper()}] 小時勝率 TOP5 / BOTTOM5</b>\n【最佳時段】']
    for h, t, w, l, wr in hour_rows[:5]:
        lines.append(f'{h:02d}時  {wr:5.1f}%  [{t}次]')
    lines.append('\n【最差時段】')
    for h, t, w, l, wr in hour_rows[-5:]:
        lines.append(f'{h:02d}時  {wr:5.1f}%  [{t}次]')
    send_tg('\n'.join(lines))
    time.sleep(1)

    # 黃金組合
    combo_groups = defaultdict(list)
    for r in all_results:
        k = f"{r['direction']} + TP{r['tp_bucket']}"
        combo_groups[k].append(r)
    combo_rows = []
    for k, v in combo_groups.items():
        w, t, wr = stats(v)
        if t >= 20:
            combo_rows.append((k, t, w, t-w, wr))
    combo_rows.sort(key=lambda x: -x[4])

    lines = [f'<b>▶ [{tf.upper()}] 黃金組合（方向 × TP距離）</b>']
    for k, t, w, l, wr in combo_rows[:8]:
        mark = '🏆' if wr >= 92 else ''
        lines.append(f'{mark}{k:22s} {wr:.1f}%  [{t}次]')
    send_tg('\n'.join(lines))

    print(f'[{tf}] ✅ TG 推送完成')

def main():
    for tf in ['30m', '1h', '4h']:
        print(f'\n===== {tf} =====')
        run_tf(tf)
        time.sleep(2)

    print('\n✅ 全部完成')

if __name__ == '__main__':
    main()
