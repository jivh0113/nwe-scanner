import requests
import math
import time

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
SYMS_30M = [
    'BTCUSDT','ETHUSDT','BNBUSDT','SOLUSDT','XRPUSDT','DOGEUSDT','NEARUSDT','WLDUSDT',
    'LTCUSDT','PYTHUSDT','UNIUSDT','FILUSDT','APTUSDT','ONDOUSDT','RSRUSDT','TIAUSDT',
    'AVAXUSDT','INJUSDT','STXUSDT','BCHUSDT','SUIUSDT','ZROUSDT',
    'TAOUSDT','TRUMPUSDT','PENGUUSDT','HYPEUSDT','JTOUSDT','VIRTUALUSDT',
    'DASHUSDT','JUPUSDT','XLMUSDT','ETCUSDT','LDOUSDT','CRVUSDT','SANDUSDT','POLUSDT',
    'KAIAUSDT','ALGOUSDT','CFXUSDT','ICPUSDT',
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
    'KAIAUSDT','ALGOUSDT','CFXUSDT','ICPUSDT',
    'ADAUSDT','DOTUSDT','LINKUSDT','OPUSDT','MKRUSDT','WIFUSDT','TONUSDT','EIGENUSDT',
    'MOVEUSDT','ORDIUSDT','ARUSDT','GALAUSDT','MATICUSDT','FETUSDT','RENDERUSDT',
    'APEUSDT','GMTUSDT','FLOWUSDT','EGLDUSDT','VETUSDT','ZILUSDT','RVNUSDT','CHZUSDT'
]
SYMS_4H = [
    'PENGUUSDT','UNIUSDT','PYTHUSDT','WLDUSDT','TAOUSDT','BCHUSDT','APTUSDT','NEARUSDT',
    'INJUSDT','DOGEUSDT','TIAUSDT','ONDOUSDT','FILUSDT','LTCUSDT','BNBUSDT','RSRUSDT',
    'ZROUSDT','XMRUSDT','VIRTUALUSDT','CRVUSDT','LDOUSDT','JTOUSDT',
    'SANDUSDT','DASHUSDT','RENDERUSDT','ETCUSDT',
    'ATOMUSDT','MKRUSDT','ORDIUSDT','ARUSDT','GALAUSDT','MATICUSDT',
    'APEUSDT','FLOWUSDT','EGLDUSDT','VETUSDT','CHZUSDT'
]
SYMS_MAP = {'15m': SYMS_15M, '30m': SYMS_30M, '1h': SYMS_1H, '4h': SYMS_4H}

# 每個週期拉 1500 根（API 上限），實際覆蓋天數
TF_DAYS = {'15m': 15, '30m': 31, '1h': 62, '4h': 250}
# 回測用幾根（掃訊號的範圍，留 500 根給後續驗證）
TF_SCAN = {'15m': 1000, '30m': 1000, '1h': 1000, '4h': 1000}

def fetch_klines(sym, tf, limit=1500):
    for base in ENDPOINTS:
        url = f'{base}?symbol={sym}&interval={tf}&limit={limit}'
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
        except:
            pass
    return None

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

def backtest_sym(closes_all, scan_bars):
    n = len(closes_all)
    uppers, lowers = calc_nwe_all(closes_all)
    results = []

    # 掃最近 scan_bars 根，留 500 根給後續驗證
    scan_start = max(100, n - scan_bars - 500)
    scan_end   = n - 500  # 最後 500 根用來驗證

    for i in range(scan_start, scan_end):
        prev_close = closes_all[i - 1]
        cur_close  = closes_all[i]
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

        hit = None
        for j in range(i + 1, min(i + 501, n)):
            c = closes_all[j]
            if is_long:
                if c >= tp:
                    hit = 'win'
                    break
                if c <= sl:
                    hit = 'loss'
                    break
            else:
                if c <= tp:
                    hit = 'win'
                    break
                if c >= sl:
                    hit = 'loss'
                    break

        if hit:
            results.append(hit)

    return results

def send_tg(msg):
    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        requests.post(url, json={'chat_id': TG_CHAT, 'text': msg}, timeout=10)
    except:
        pass

def main():
    tf_stats = {}

    for tf, syms in SYMS_MAP.items():
        scan_bars = TF_SCAN[tf]
        wins_total = 0
        total_total = 0
        print(f'=== {tf.upper()} ===')

        for sym in syms:
            raw = fetch_klines(sym, tf, 1500)
            if not raw or len(raw) < 600:
                continue

            closes = [float(k[4]) for k in raw]
            results = backtest_sym(closes, scan_bars)
            if results:
                w = sum(1 for r in results if r == 'win')
                t = len(results)
                wins_total += w
                total_total += t
                print(f'  {sym.replace("USDT",""):10s}: {w}W/{t-w}L = {w/t*100:.1f}%')
            time.sleep(0.05)

        tf_stats[tf] = (wins_total, total_total)
        if total_total > 0:
            print(f'  小計: {wins_total}W/{total_total-wins_total}L = {wins_total/total_total*100:.1f}%')
        else:
            print(f'  小計: 無訊號')

    # 組 TG 訊息
    lines = ['📊 NWE 回測結果（近30天）\n']
    total_w = 0
    total_t = 0
    for tf, (w, t) in tf_stats.items():
        days = TF_DAYS[tf]
        if t > 0:
            lines.append(f'{tf.upper():4s} (~{days}天): {w}W / {t-w}L = {w/t*100:.1f}%  [{t}次]')
            total_w += w
            total_t += t
        else:
            lines.append(f'{tf.upper():4s} (~{days}天): 無訊號')

    if total_t > 0:
        lines.append(f'\n總計: {total_w}W / {total_t-total_w}L = {total_w/total_t*100:.1f}%  [{total_t}次]')

    msg = '\n'.join(lines)
    print('\n' + msg)
    send_tg(msg)
    print('\nTG 已推送')

if __name__ == '__main__':
    main()
