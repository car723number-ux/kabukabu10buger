import numpy as np
import pandas as pd


# ============================================================
# ユーティリティ
# ============================================================

def _round_to_psych(price, unit=None):
    """最も近いキリ番単位を返す"""
    if unit is None:
        if price >= 10000: unit = 1000
        elif price >= 1000: unit = 100
        elif price >= 100: unit = 50
        else: unit = 10
    return round(price / unit) * unit


def _get_poc(d, period):
    try:
        t = d.tail(period)
        h, e = np.histogram((t["High"] + t["Low"]) / 2, bins=50, weights=t["Volume"])
        return float(e[np.argmax(h)])
    except:
        return float(d["Close"].iloc[-1])


# ============================================================
# メイン関数
# ============================================================

def detect_attack_points(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"].astype(float)
    high  = df["High"].astype(float)
    low   = df["Low"].astype(float)
    vol   = df["Volume"].astype(float)

    # ----------------------------------------------------------
    # 基本指標
    # ----------------------------------------------------------
    tp = (high + low + close) / 3
    df["VWAP_ALL"] = (tp * vol).cumsum() / vol.cumsum()
    df["SMA5"]  = close.rolling(5).mean()
    df["SMA25"] = close.rolling(25).mean()

    df["MACD"]   = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    df["Signal"] = df["MACD"].ewm(span=9).mean()

    delta = close.diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean().replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + gain / loss))

    std25 = close.rolling(25).std()
    df["BB_Upper"] = df["SMA25"] + std25 * 2
    df["BB_Lower"] = df["SMA25"] - std25 * 2

    tr = pd.concat(
        [high - low,
         (high - close.shift()).abs(),
         (low  - close.shift()).abs()],
        axis=1
    ).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # ----------------------------------------------------------
    # ① 心理的損切りライン（キリ番クラスター）
    # ----------------------------------------------------------
    c_now   = float(close.iloc[-1])
    atr_now = float(df["ATR"].iloc[-1]) if not np.isnan(df["ATR"].iloc[-1]) else c_now * 0.02

    psych_base  = _round_to_psych(c_now)
    psych_lines = sorted({
        psych_base - (_round_to_psych(c_now) % (_round_to_psych(c_now, 1000) or 1)) * 0,  # placeholder
        psych_base,
        psych_base + (_round_to_psych(c_now, None) if False else 0),
    })
    # シンプルに現在値周辺の±3キリ番を列挙
    unit = 1000 if c_now >= 10000 else 100 if c_now >= 1000 else 50 if c_now >= 100 else 10
    psych_lines = [psych_base + unit * i for i in range(-3, 4)]

    # ----------------------------------------------------------
    # ② 直近高値・安値の損切りゾーン（±ATR*0.5以内）
    # ----------------------------------------------------------
    recent_high  = float(high.tail(20).max())
    recent_low   = float(low.tail(20).min())
    stop_buffer  = atr_now * 0.5

    stop_zone_high = (recent_high - stop_buffer, recent_high + stop_buffer)   # 売り勢の損切り圏
    stop_zone_low  = (recent_low  - stop_buffer, recent_low  + stop_buffer)   # 買い勢の損切り圏

    # ----------------------------------------------------------
    # ③ ストップハント（フェイクアウト）検出
    # ----------------------------------------------------------
    def _detect_stop_hunt(window=5):
        """
        直近window本の中で：
        - ヒゲが実体の2倍以上
        - BBブレイク→翌足で内側に戻る
        - 出来高スパイク（5日平均の1.5倍超）＋翌足逆行
        の3条件を検出し、フラグと詳細を返す
        """
        flags = []
        w = df.tail(window + 1).copy()
        w_close = w["Close"].astype(float)
        w_high  = w["High"].astype(float)
        w_low   = w["Low"].astype(float)
        w_open  = w["Open"].astype(float)
        w_vol   = w["Volume"].astype(float)
        w_vol_ma = w_vol.rolling(5).mean()

        for i in range(1, len(w)):
            body   = abs(w_close.iloc[i] - w_open.iloc[i])
            upper  = w_high.iloc[i]  - max(w_close.iloc[i], w_open.iloc[i])
            lower  = min(w_close.iloc[i], w_open.iloc[i]) - w_low.iloc[i]
            total  = w_high.iloc[i] - w_low.iloc[i]
            if total == 0:
                continue

            # 条件A: ピンバー（ヒゲ比率）
            is_pin_upper = upper > body * 2 and upper / total > 0.6
            is_pin_lower = lower > body * 2 and lower / total > 0.6

            # 条件B: BB外→内戻り
            bb_u = float(df["BB_Upper"].iloc[-(window + 1 - i)])
            bb_l = float(df["BB_Lower"].iloc[-(window + 1 - i)])
            bb_breakout_up   = w_high.iloc[i - 1] > bb_u and w_close.iloc[i] < bb_u
            bb_breakout_down = w_low.iloc[i - 1]  < bb_l and w_close.iloc[i] > bb_l

            # 条件C: 出来高スパイク＋逆行
            vol_spike = (w_vol_ma.iloc[i] > 0) and (w_vol.iloc[i] > w_vol_ma.iloc[i] * 1.5)
            reversal_up   = (w_close.iloc[i - 1] < w_open.iloc[i - 1]) and (w_close.iloc[i] > w_open.iloc[i])
            reversal_down = (w_close.iloc[i - 1] > w_open.iloc[i - 1]) and (w_close.iloc[i] < w_open.iloc[i])

            if is_pin_lower or bb_breakout_down or (vol_spike and reversal_up):
                flags.append({"type": "bullish_hunt", "index": w.index[i],
                               "price": float(w_low.iloc[i])})
            if is_pin_upper or bb_breakout_up or (vol_spike and reversal_down):
                flags.append({"type": "bearish_hunt", "index": w.index[i],
                               "price": float(w_high.iloc[i])})
        return flags

    hunt_flags = _detect_stop_hunt(window=10)

    # ----------------------------------------------------------
    # ④ 含み損ゾーン推定（塩漬け勢の損切り待ちライン）
    # ----------------------------------------------------------
    def _estimate_trapped_zones(lookback=60):
        """
        直近N日の高値付近（close > 直近高値 × 0.95）に積み上がった出来高を
        「含み損の塩漬けゾーン」として推定する
        """
        w = df.tail(lookback).copy()
        recent_peak = float(w["High"].max())
        threshold   = recent_peak * 0.95
        trapped     = w[w["Close"].astype(float) >= threshold]
        trapped_vol = float(trapped["Volume"].sum()) if not trapped.empty else 0.0
        return {
            "zone_top":    recent_peak,
            "zone_bottom": threshold,
            "trapped_vol": trapped_vol,
            "pct_of_total": trapped_vol / float(vol.sum()) if float(vol.sum()) > 0 else 0,
        }

    trapped_info = _estimate_trapped_zones()

    # ----------------------------------------------------------
    # ⑤ 10項目スコアリング（既存）
    # ----------------------------------------------------------
    score   = 0
    reasons = []

    if c_now > df["VWAP_ALL"].iloc[-1]:
        score += 10; reasons.append("✅ 価格がVWAPを上回る強気相場")
    if c_now > df["SMA5"].iloc[-1]:
        score += 10; reasons.append("✅ 5日線の上をキープ")
    if df["SMA5"].iloc[-1] > df["SMA25"].iloc[-1]:
        score += 10; reasons.append("✅ 短中期MAのGC（ゴールデンクロス）状態")
    if df["MACD"].iloc[-1] > df["Signal"].iloc[-1]:
        score += 10; reasons.append("✅ MACDがシグナルを上抜け中")
    if 30 <= df["RSI"].iloc[-1] <= 50:
        score += 10; reasons.append("✅ RSIが30-50の間で、反発余地が大きい")
    if df["RSI"].iloc[-1] < 70:
        score += 10; reasons.append("✅ RSIが70以下で過熱感なし")
    if vol.iloc[-1] > vol.rolling(5).mean().iloc[-1]:
        score += 10; reasons.append("✅ 出来高が5日平均を超えて増加")
    if c_now < df["BB_Upper"].iloc[-1]:
        score += 10; reasons.append("✅ ボリンジャーバンド+2σ以内で過度な過熱なし")
    if c_now > low.tail(5).min():
        score += 10; reasons.append("✅ 直近5日間の最安値を下回っていない")
    if df["ATR"].iloc[-1] > df["ATR"].rolling(20).mean().iloc[-1]:
        score += 10; reasons.append("✅ ボラティリティが拡大し、値動きが活発")

    # ----------------------------------------------------------
    # ⑥ Stop Hunt ボーナス評価（追加スコア）
    # ----------------------------------------------------------
    sh_score   = 0
    sh_reasons = []

    # 直近5本以内に bullish_hunt があるか
    recent_bull_hunts = [f for f in hunt_flags if f["type"] == "bullish_hunt"]
    if recent_bull_hunts:
        sh_score += 20
        sh_reasons.append(f"🎯 直近でストップハント（下ヒゲ狩り）を{len(recent_bull_hunts)}回検出 → 反発期待大")

    # 現在値が損切りゾーン（安値圏）の上にいるか
    if c_now > stop_zone_low[1]:
        sh_score += 15
        sh_reasons.append(f"🎯 買い勢の損切りゾーン（{stop_zone_low[0]:.0f}〜{stop_zone_low[1]:.0f}）を上抜け維持中")

    # 塩漬けゾーンが薄い（=上値が軽い）
    if trapped_info["pct_of_total"] < 0.15:
        sh_score += 10
        sh_reasons.append(f"🎯 上値の塩漬けゾーンが薄い（全出来高の{trapped_info['pct_of_total']*100:.1f}%）→ 上抜けしやすい")
    elif trapped_info["pct_of_total"] >= 0.30:
        sh_reasons.append(f"⚠️ 塩漬けゾーンが厚い（全出来高の{trapped_info['pct_of_total']*100:.1f}%）→ 戻り売り圧力に注意")

    # 心理的ラインが近い（エントリーorブレイク判断）
    nearest_psych = min(psych_lines, key=lambda x: abs(x - c_now))
    dist_pct = abs(nearest_psych - c_now) / c_now * 100
    if dist_pct < 1.0:
        sh_reasons.append(f"📌 心理的ライン {nearest_psych:.0f}円 まで {dist_pct:.2f}% — ブレイク/反発の分岐点")

    # ----------------------------------------------------------
    # フィボナッチ / POC
    # ----------------------------------------------------------
    max_p, min_p = high.max(), low.min()
    diff = max_p - min_p
    fib_levels = {
        "61.8%": float(max_p - diff * 0.382),
        "50.0%": float(max_p - diff * 0.5),
        "38.2%": float(max_p - diff * 0.618),
    }

    poc_info = {
        "poc_short":    _get_poc(df, 20),
        "poc_long":     _get_poc(df, 120),
        "fib":          fib_levels,
        "score":        score,
        # --- 追加情報 ---
        "sh_score":     sh_score,
        "sh_reasons":   sh_reasons,
        "hunt_flags":   hunt_flags,
        "psych_lines":  psych_lines,
        "stop_zone_high": stop_zone_high,
        "stop_zone_low":  stop_zone_low,
        "trapped_info": trapped_info,
        "atr_now":      atr_now,
    }

    all_reasons = reasons + sh_reasons
    return df, poc_info, all_reasons
