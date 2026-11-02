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

SYMS_15M = [
    'BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','NEARUSDT','WLDUSDT',
    'LTCUSDT','PYTHUSDT','UNIUSDT','FILUSDT','APTUSDT','ONDOUSDT','RSRUSDT','TIAUSDT',
    'AVAXUSDT','INJUSDT','STXUSDT','BCHUSDT','AAVEUSDT','SUIUSDT','ZROUSDT',
    'TAOUSDT','TRUMPUSDT','PENGUUSDT','HYPEUSDT','JTOUSDT','VIRTUALUSDT',
    'DASHUSDT','JUPUSDT','XLMUSDT','ETCUSDT','LDOUSDT','CRVUSDT','SANDUSDT','POLUSDT',
    'KAIAUSDT','CFXUSDT','ICPUSDT',
    'ADAUSDT','DOTUSDT','LINKUSDT','OPUSDT','MKRUSDT','WIFUSDT','TONUSDT','EIGENUSDT',
    'MOVEUSDT','ORDIUSDT','ARUSDT','GALAUSDT','MATICUSDT','FETUSDT','RENDERUSDT',
    'APEUSDT','GMTUSDT','FLOWUSDT','EGLDUSDT','VETUSDT','ZILUSDT','RVNUSDT','CHZUSDT'
]

BARS_30D = 2880  # 15m × 30天

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

def fetch_klines_30d(sym):
    need = BARS_30D + 600
    all_raw = []
    end_ms = int(time.time() * 1000)
    while len(all_raw) < need:
        batch = fetch_klines_endtime(sym, '15m', end_ms=end_ms, limit=1000)
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
    return uppers, lowers

def backtest_15m(raw):
    n = len(raw)
    closes = [float(k[4]) for k in raw]
    open_times = [int(k[0]) for k in raw]  # ms
    uppers, lowers = calc_nwe_all(closes)

    scan_start = max(100, n - BARS_30D - 500)
    scan_end   = n - 500

    results = []
    for i in range(scan_start, scan_end):
        prev_close = closes[i - 1]
        cur_close  = closes[i]
        upper = uppers[i - 1]
        lower = lowers[i - 1]

        is_long  = prev_close < lower
        is_short = prev_close > upper
        if not is_long and not is_short:
            continue

        entry = cur_close
        tp = find_round_tp(entry, is_long)
        if abs(tp - entry) / entry <= 0.001:
            continue

        sl = entry * (1 - SL_PCT) if is_long else entry * (1 + SL_PCT)

        # 訊號時間 UTC+8 小時
        sig_dt = datetime.fromtimestamp(open_times[i] / 1000, tz=timezone(timedelta(hours=8)))
        hour = sig_dt.hour

        hit = None
        bars_to_tp = None
        for j in range(i + 1, min(i + 501, n)):
            c = closes[j]
            if is_long:
                if c >= tp:
                    hit = 'win'
                    bars_to_tp = j - i
                    break
                if c <= sl:
                    hit = 'loss'
                    break
            else:
                if c <= tp:
                    hit = 'win'
                    bars_to_tp = j - i
                    break
                if c >= sl:
                    hit = 'loss'
                    break

        if hit:
            results.append({
                'hour': hour,
                'result': hit,
                'bars_to_tp': bars_to_tp,  # None if loss
            })

    return results

def send_tg(msg):
    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        requests.post(url, json={'chat_id': TG_CHAT, 'text': msg}, timeout=10)
    except:
        pass

def main():
    all_results = []

    for sym in SYMS_15M:
        raw = fetch_klines_30d(sym)
        if not raw or len(raw) < BARS_30D + 100:
            print(f'{sym}: 資料不足，跳過')
            continue
        res = backtest_15m(raw)
        all_results.extend(res)
        print(f'{sym}: {len(res)} 筆')
        time.sleep(0.05)

    if not all_results:
        print('無資料')
        return

    # 統計各小時
    hour_wins   = defaultdict(int)
    hour_total  = defaultdict(int)
    hour_tp_bars = defaultdict(list)

    for r in all_results:
        h = r['hour']
        hour_total[h] += 1
        if r['result'] == 'win':
            hour_wins[h] += 1
            if r['bars_to_tp']:
                hour_tp_bars[h].append(r['bars_to_tp'])

    # 全局 TP 平均時間
    all_tp_bars = [r['bars_to_tp'] for r in all_results if r['result'] == 'win' and r['bars_to_tp']]
    avg_tp_min = sum(all_tp_bars) / len(all_tp_bars) * 15 if all_tp_bars else 0

    # 組 TG 訊息
    total_w = sum(hour_wins.values())
    total_t = sum(hour_total.values())

    lines = [f'📊 NWE 15M 30天統計\n總計: {total_w}W/{total_t-total_w}L = {total_w/total_t*100:.1f}%  [{total_t}次]']
    lines.append(f'打到TP平均時間: {avg_tp_min:.0f}分鐘 ({avg_tp_min/60:.1f}小時)\n')
    lines.append('各小時訊號數 & 勝率 (UTC+8):')

    for h in range(24):
        t = hour_total[h]
        if t == 0:
            continue
        w = hour_wins[h]
        wr = w / t * 100
        tp_bars = hour_tp_bars[h]
        avg_min = sum(tp_bars) / len(tp_bars) * 15 if tp_bars else 0
        tp_str = f'{avg_min:.0f}分' if tp_bars else '-'
        lines.append(f'{h:02d}時: {t:3d}次  勝率{wr:5.1f}%  TP均{tp_str}')

    msg = '\n'.join(lines)
    print('\n' + msg)
    send_tg(msg)
    print('\nTG 已推送')

if __name__ == '__main__':
    main()
