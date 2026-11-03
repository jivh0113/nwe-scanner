"""
NWE 小時勝率回測
分析各 TF 在一天中哪個小時（UTC+8）訊號勝率最高
"""
import requests, math, time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

TG_TOKEN = '8999488432:AAG5OlXC58i_I4Zqs_Q3r9zZdFYSDePBGLo'
TG_CHAT  = '6037933384'
TZ8 = timezone(timedelta(hours=8))

LUX_H    = 8
LUX_MULT = 3
SL_PCT   = 0.08

ENDPOINTS = [
    'https://data-api.binance.vision/api/v3/klines',
    'https://api.binance.com/api/v3/klines',
]

TF_CONFIG = {
    '15m': {'limit': 2000, 'bars_30d': 2880, 'scan_bars': 500},
    '30m': {'limit': 2000, 'bars_30d': 1440, 'scan_bars': 500},
    '1h':  {'limit': 2000, 'bars_30d': 720,  'scan_bars': 300},
}

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
SYMS_MAP = {'15m': SYMS_15M, '30m': SYMS_30M, '1h': SYMS_1H}

def send_tg(msg):
    url = f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage'
    try:
        requests.post(url, json={'chat_id': TG_CHAT, 'text': msg}, timeout=10)
    except:
        pass

def fetch_klines(sym, tf, limit=2000):
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

def backtest_hourly(tf):
    cfg = TF_CONFIG[tf]
    syms = SYMS_MAP[tf]
    limit = cfg['limit']
    scan_bars = cfg['scan_bars']
    forward = 500  # 最多往後看500根

    # hour_stats[h] = {'wins': 0, 'total': 0}
    hour_stats = {h: {'wins': 0, 'total': 0} for h in range(24)}

    print(f"\n=== {tf} 開始 ({len(syms)} 幣) ===")
    send_tg(f"⏳ 開始 {tf} 小時分析...")

    for idx, sym in enumerate(syms):
        raw = fetch_klines(sym, tf, limit)
        if not raw or len(raw) < 200:
            continue

        closes = [float(k[4]) for k in raw]
        timestamps = [k[6] for k in raw]  # 收盤時間戳(ms)
        n = len(closes)

        # NWE 用全部資料
        outs, mae = calc_nwe(closes)

        # scan 範圍：從 100 到 n-forward-1
        scan_start = 100
        scan_end = n - forward - 1
        if scan_end <= scan_start:
            continue

        for i in range(scan_start, scan_end):
            upper = outs[i] + mae
            lower = outs[i] - mae
            prev_close = closes[i]

            is_long  = prev_close < lower
            is_short = prev_close > upper
            if not is_long and not is_short:
                continue

            entry = closes[i+1]  # 下一根開盤進場（用收盤替代）
            tp = find_round_tp(entry, is_long)
            if abs(tp - entry) / entry <= 0.001:
                continue

            sl = entry * (1 - SL_PCT) if is_long else entry * (1 + SL_PCT)

            # 訊號時間（UTC+8）
            ts_ms = timestamps[i]
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=TZ8)
            hour = dt.hour

            # 判斷勝負
            hit = None
            for j in range(i+2, min(i+2+forward, n)):
                c = closes[j]
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
                hour_stats[hour]['total'] += 1
                if hit == 'win':
                    hour_stats[hour]['wins'] += 1

        if (idx+1) % 10 == 0:
            print(f"  {idx+1}/{len(syms)} 完成")
        time.sleep(0.05)

    return hour_stats

def format_result(tf, hour_stats):
    total_all = sum(v['total'] for v in hour_stats.values())
    wins_all  = sum(v['wins']  for v in hour_stats.values())
    overall_wr = wins_all / total_all * 100 if total_all else 0

    lines = [f"📊 {tf.upper()} 小時勝率分析\n整體: {overall_wr:.1f}% ({total_all}次)\n"]
    lines.append("時段  勝率    次數  評級")
    lines.append("─" * 28)

    for h in range(24):
        s = hour_stats[h]
        if s['total'] < 5:
            rating = '—'
            wr_str = f"({'樣本不足':^6})"
        else:
            wr = s['wins'] / s['total'] * 100
            wr_str = f"{wr:.1f}%"
            if wr >= 92:
                rating = '🏆🏆'
            elif wr >= 90:
                rating = '🏆'
            elif wr >= 87:
                rating = '✅'
            elif wr >= 83:
                rating = '🔶'
            else:
                rating = '❌'
        lines.append(f"{h:02d}:00  {wr_str:<7} {s['total']:>4}次  {rating}")

    return '\n'.join(lines)

def main():
    send_tg("🔬 NWE 小時勝率回測開始（15m/30m/1h）")

    for tf in ['15m', '30m', '1h']:
        hour_stats = backtest_hourly(tf)
        msg = format_result(tf, hour_stats)
        print(msg)
        send_tg(msg)
        time.sleep(1)

    send_tg("✅ 小時勝率回測完成！")
    print("\n全部完成")

if __name__ == '__main__':
    main()
