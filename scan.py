import requests
import math
import time
from datetime import datetime, timezone, timedelta

TG_TOKEN = '8999488432:AAG5OlXC58i_I4Zqs_Q3r9zZdFYSDePBGLo'
TG_CHAT  = '6037933384'

LUX_H    = 8
LUX_MULT = 3
SL_PCT   = 0.08
TF_MAX_BARS = {'15m': 5, '30m': 5, '1h': 5, '4h': 2}
TF_MS       = {'15m': 15*60, '30m': 30*60, '1h': 60*60, '4h': 240*60}

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

def find_round_tp(price, is_bull):
    mag = 10 ** (math.floor(math.log10(price)) - 1)
    raw = math.ceil(price / mag) * mag if is_bull else math.floor(price / mag) * mag
    cap = price * 1.03 if is_bull else price * 0.97
    return min(raw, cap) if is_bull else max(raw, cap)

def fetch_klines(sym, tf, limit=1502):
    url = f'https://api.binance.com/api/v3/klines?symbol={sym}&interval={tf}&limit={limit}'
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def calc_nwe(closes):
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
    return outs, mae

def scan_tf(tf):
    syms = SYMS_MAP[tf]
    signals = []
    now_ts = int(time.time())
    max_age = TF_MAX_BARS[tf] * TF_MS[tf]

    for sym in syms:
        raw = fetch_klines(sym, tf, 1502)
        if not raw or len(raw) < 100:
            continue

        closes = [float(k[4]) for k in raw]
        sig_ts = raw[-2][6] / 1000  # 前一根K線收盤時間(秒)

        # debug
        if sym == 'TIAUSDT' and tf == '4h':
            age = now_ts - sig_ts
            print(f'DEBUG TIAUSDT 4h: now={now_ts}, sig_ts={sig_ts}, age={age}s, max_age={max_age}s, pass={age<=max_age}')

        # 時效過濾
        if now_ts - sig_ts > max_age:
            continue

        # debug NWE
        if sym == 'TIAUSDT' and tf == '4h':
            src2 = closes[-1501:-1]
            outs2, mae2 = calc_nwe(src2)
            out2 = outs2[-1]
            print(f'DEBUG TIAUSDT 4h NWE: out={out2:.6f}, mae={mae2:.6f}, upper={out2+mae2:.6f}, lower={out2-mae2:.6f}, prev_close={src2[-1]:.6f}, cur_close={closes[-1]:.6f}')

        src = closes[-1501:-1]
        n = len(src)
        if n < 100:
            continue

        outs, mae = calc_nwe(src)
        out = outs[-1]
        upper = out + mae
        lower = out - mae
        prev_close = src[-1]
        cur_close  = closes[-1]

        is_long  = prev_close < lower
        is_short = prev_close > upper
        if not is_long and not is_short:
            continue

        tp = find_round_tp(cur_close, is_long)
        if abs(tp - cur_close) / cur_close <= 0.001:
            continue

        sl = cur_close * (1 - SL_PCT) if is_long else cur_close * (1 + SL_PCT)
        direction = '做多 🟢' if is_long else '做空 🔴'

        # 格式化時間 UTC+8
        sig_dt = datetime.fromtimestamp(sig_ts, tz=timezone(timedelta(hours=8)))
        sig_time = sig_dt.strftime('%m/%d %H:%M')

        tp_pct = (tp - cur_close) / cur_close * 100
        lev_pct = tp_pct * 12

        signals.append({
            'sym': sym.replace('USDT',''),
            'tf': tf,
            'direction': direction,
            'price': cur_close,
            'tp': tp,
            'sl': sl,
            'tp_pct': tp_pct,
            'lev_pct': lev_pct,
            'time': sig_time,
        })
        time.sleep(0.05)  # 避免打太快

    return signals

def send_tg(msg):
    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        requests.post(url, json={'chat_id': TG_CHAT, 'text': msg}, timeout=10)
    except:
        pass

def main():
    all_signals = []
    for tf in ['15m','30m','1h','4h']:
        sigs = scan_tf(tf)
        all_signals.extend(sigs)
        print(f'{tf}: {len(sigs)} signals')

    if not all_signals:
        print('No signals')
        return

    for s in all_signals:
        msg = (
            f"📡 NWE訊號 [{s['tf'].upper()}]\n"
            f"{s['sym']} {s['direction']}\n"
            f"進場: {s['price']}\n"
            f"TP: {s['tp']:.4f}  ({s['tp_pct']:+.1f}%  12x: {s['lev_pct']:+.0f}%)\n"
            f"SL: {s['sl']:.4f}\n"
            f"訊號時間: {s['time']}"
        )
        send_tg(msg)
        print(f"Sent: {s['sym']} {s['tf']} {s['direction']}")
        time.sleep(0.3)

if __name__ == '__main__':
    main()
