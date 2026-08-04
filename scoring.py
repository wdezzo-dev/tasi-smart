# -*- coding: utf-8 -*-
"""
محرك التقييم - نظام تقييم أسهم تاسي (0-100)
=================================================
المنهجية (الوزن الإجمالي = 100 نقطة):

1) التجميع الذكي (Smart Accumulation)            ........ 30 نقطة
   - تدفق نقدي تراكمي (Chaikin Money Flow 20)      -> حتى 15 نقطة
   - ميل OBV الصاعد دون قفزة سعرية مقابلة          -> حتى 15 نقطة
     (تجميع هادئ: المال يدخل قبل أن يتحرك السعر)

2) السيولة والمال الذكي (Liquidity & Smart Volume) ........ 20 نقطة
   - نسبة حجم أيام الصعود / حجم أيام النزول (10 جلسات) -> حتى 12 نقطة
   - تسارع متوسط الحجم القصير عن الطويل (5/20)         -> حتى 8 نقطة

3) تشبع البيع والارتداد (Oversold Reversal)        ........ 15 نقطة
   - RSI(14) في منطقة تشبع بيع ويصعد فعلياً          -> حتى 10 نقاط
   - شمعة انعكاسية صعودية حديثة                      -> حتى 5 نقاط

4) الاختراق الفني (Technical Breakout)             ........ 25 نقطة
   - إغلاق فوق أعلى قمة لـ20 جلسة بحجم تأكيدي         -> حتى 15 نقطة
   - تقاطع MACD صعودي حديث                           -> حتى 10 نقاط

5) بنية الاتجاه العام (Trend Structure)            ........ 10 نقاط
   - ترتيب صاعد للمتوسطات (السعر > م50 > م100)        -> حتى 10 نقاط

عقوبة التصريف (Distribution Penalty) - تُطرح من الإجمالي:
   - تدفق نقدي سلبي مستمر رغم ارتفاع السعر            -> حتى 15-
   - هيمنة حجم أيام النزول على الصعود                 -> حتى 10-

الدرجة النهائية = max(0, min(100, مجموع النقاط - عقوبة التصريف))
"""
import numpy as np
import pandas as pd
import indicators as ind


MIN_ROWS = 200  # أقل عدد جلسات مطلوب لحساب موثوق


def _clip(x, lo, hi):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return 0.0
    return float(max(lo, min(hi, x)))


def _scale(x, x0, x1, y0, y1):
    """تحويل خطي لقيمة x من مدى [x0,x1] إلى مدى [y0,y1] مع تحديد الحدود"""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return y0
    if x1 == x0:
        return y0
    t = (x - x0) / (x1 - x0)
    t = max(0.0, min(1.0, t))
    return y0 + t * (y1 - y0)


def compute_score(df: pd.DataFrame):
    """
    df: DataFrame بأعمدة Open, High, Low, Close, Volume مرتبة تصاعدياً بالتاريخ
    يرجع dict فيه: total, sub_scores, penalty, signals (قائمة شروحات عربية), classification
    """
    if df is None or len(df) < MIN_ROWS:
        return None

    df = df.dropna(subset=["Close", "Volume"]).copy()
    if len(df) < MIN_ROWS:
        return None

    o, h, l, c, v = df["Open"], df["High"], df["Low"], df["Close"], df["Volume"]

    signals = []
    sub_scores = {}

    # ---------- 1) التجميع الذكي (30) ----------
    cmf20 = ind.cmf(h, l, c, v, period=20)
    cmf_recent = cmf20.tail(10).mean()
    cmf_score = _scale(cmf_recent, -0.10, 0.20, 0.0, 15.0)

    obv_series = ind.obv(c, v)
    obv_slope = ind.linreg_slope(obv_series, 20)
    price_chg_20 = ind.pct_change_n(c, 20)
    # تجميع هادئ: ميل OBV صاعد بوضوح بينما السعر لم يتحرك كثيراً (أقل من 4%)
    quiet_accum_bonus = 1.0
    if not np.isnan(price_chg_20) and abs(price_chg_20) < 0.04:
        quiet_accum_bonus = 1.3
    obv_score = _clip(_scale(obv_slope, 0.0, 0.05, 0.0, 15.0) * quiet_accum_bonus, 0, 15)

    accumulation_score = _clip(cmf_score + obv_score, 0, 30)
    sub_scores["تجميع_ذكي"] = round(accumulation_score, 1)

    if cmf_recent is not None and not np.isnan(cmf_recent) and cmf_recent > 0.05:
        signals.append(f"📦 تدفق نقدي إيجابي مستمر (CMF≈{cmf_recent:+.2f}) يدل على تجميع")
    if obv_slope is not None and not np.isnan(obv_slope) and obv_slope > 0.01:
        tag = " مع تماسك سعري هادئ (تجميع بصمت)" if quiet_accum_bonus > 1 else ""
        signals.append(f"📈 مؤشر OBV في صعود مستمر خلال 20 جلسة{tag}")

    # ---------- 2) السيولة والمال الذكي (20) ----------
    udv = ind.up_down_volume_ratio(c, v, period=10)
    udv_last = udv.iloc[-1] if len(udv) else np.nan
    udv_score = _scale(udv_last, 0.6, 1.8, 0.0, 12.0)

    vol5 = v.rolling(5).mean()
    vol20 = v.rolling(20).mean()
    vol_accel = (vol5.iloc[-1] / vol20.iloc[-1]) if vol20.iloc[-1] not in (0, np.nan) else np.nan
    vol_accel_score = _scale(vol_accel, 0.8, 1.8, 0.0, 8.0)

    liquidity_score = _clip(udv_score + vol_accel_score, 0, 20)
    sub_scores["سيولة_ذكية"] = round(liquidity_score, 1)

    if udv_last is not None and not np.isnan(udv_last) and udv_last > 1.2:
        signals.append(f"💧 حجم أيام الصعود أعلى من النزول بنسبة {udv_last:.1f}x خلال 10 جلسات")
    if vol_accel is not None and not np.isnan(vol_accel) and vol_accel > 1.2:
        signals.append(f"🔊 تسارع نشاط التداول: متوسط 5 أيام أعلى من متوسط 20 يوماً بـ{vol_accel:.1f}x")

    # ---------- 3) تشبع البيع والارتداد (15) ----------
    rsi14 = ind.rsi(c, 14)
    rsi_last = rsi14.iloc[-1]
    rsi_prev3 = rsi14.iloc[-4] if len(rsi14) > 4 else np.nan
    rsi_turning_up = (not np.isnan(rsi_prev3)) and (rsi_last > rsi_prev3)

    oversold_score = 0.0
    if rsi_last <= 45:
        base = _scale(rsi_last, 45, 20, 0.0, 10.0)  # كلما انخفض RSI زادت النقاط
        oversold_score = base if rsi_turning_up else base * 0.4
    sub_scores_rsi_note = rsi_last

    bullish_candle = ind.is_bullish_candle_reversal(o, h, l, c)
    candle_recent = bool(bullish_candle.tail(3).any())
    candle_score = 5.0 if candle_recent else 0.0

    reversal_score = _clip(oversold_score + candle_score, 0, 15)
    sub_scores["تشبع_بيع_وارتداد"] = round(reversal_score, 1)

    if rsi_last <= 40 and rsi_turning_up:
        signals.append(f"🔄 ارتداد من تشبع بيع: RSI عند {rsi_last:.0f} ويتجه للصعود")
    elif rsi_last <= 30:
        signals.append(f"⏳ تشبع بيع واضح: RSI عند {rsi_last:.0f} (بانتظار تأكيد الارتداد)")
    if candle_recent:
        signals.append("🕯️ شمعة انعكاسية صعودية (ذيل سفلي طويل + إغلاق قوي) خلال آخر 3 جلسات")

    # ---------- 4) الاختراق الفني (25) ----------
    prior_high20 = ind.rolling_max_excl_last(h, 20)
    close_last = c.iloc[-1]
    prior_high_last = prior_high20.iloc[-1]
    vol_ratio_today = v.iloc[-1] / vol20.iloc[-1] if vol20.iloc[-1] not in (0, np.nan) else np.nan

    breakout_score = 0.0
    if not np.isnan(prior_high_last) and prior_high_last > 0:
        if close_last > prior_high_last:
            confirm = _scale(vol_ratio_today, 1.0, 2.0, 7.0, 15.0)
            breakout_score = confirm
            signals.append(
                f"🚀 اختراق فني: إغلاق فوق أعلى قمة لـ20 جلسة بحجم {vol_ratio_today:.1f}x المتوسط"
            )
        elif close_last > prior_high_last * 0.985:
            breakout_score = 5.0
            signals.append("👀 السهم يقترب من اختراق قمة 20 جلسة")

    macd_line, signal_line, hist = ind.macd(c)
    macd_cross_up = (
        len(hist) > 2
        and hist.iloc[-1] > 0
        and hist.iloc[-2] <= 0
    )
    macd_recent_cross = bool((hist.tail(3) > 0).iloc[-1] and (hist.tail(4) <= 0).any())
    macd_score = 10.0 if (macd_cross_up or macd_recent_cross) else (5.0 if hist.iloc[-1] > 0 else 0.0)

    breakout_total = _clip(breakout_score + macd_score, 0, 25)
    sub_scores["اختراق_فني"] = round(breakout_total, 1)

    if macd_cross_up or macd_recent_cross:
        signals.append("📊 تقاطع MACD صعودي حديث (زخم إيجابي متجدد)")

    # ---------- 5) بنية الاتجاه (10) ----------
    sma50 = ind.sma(c, 50)
    sma100 = ind.sma(c, 100) if len(c) >= 100 else pd.Series([np.nan] * len(c), index=c.index)
    trend_score = 0.0
    if not np.isnan(sma50.iloc[-1]):
        if close_last > sma50.iloc[-1] and not np.isnan(sma100.iloc[-1]) and sma50.iloc[-1] > sma100.iloc[-1]:
            trend_score = 10.0
            signals.append("📐 ترتيب صاعد للمتوسطات: السعر > متوسط 50 > متوسط 100 يوم")
        elif close_last > sma50.iloc[-1]:
            trend_score = 5.0
            signals.append("📐 السعر أعلى من المتوسط المتحرك 50 يوم")
    sub_scores["بنية_الاتجاه"] = round(trend_score, 1)

    base_total = accumulation_score + liquidity_score + reversal_score + breakout_total + trend_score

    # ---------- عقوبة التصريف ----------
    penalty = 0.0
    price_chg_10 = ind.pct_change_n(c, 10)
    if cmf_recent is not None and not np.isnan(cmf_recent) and cmf_recent < -0.05 and \
            price_chg_10 is not None and not np.isnan(price_chg_10) and price_chg_10 > 0:
        penalty += _scale(-cmf_recent, 0.05, 0.20, 5.0, 15.0)
        signals.append(f"⚠️ تحذير تصريف: تدفق نقدي سلبي (CMF≈{cmf_recent:+.2f}) رغم ارتفاع السعر مؤخراً")

    if udv_last is not None and not np.isnan(udv_last) and udv_last < 0.7:
        penalty += _scale(0.7 - udv_last, 0.0, 0.4, 0.0, 10.0)
        signals.append(f"⚠️ هيمنة حجم أيام النزول على الصعود (نسبة {udv_last:.1f}x) - ضغط بيعي")

    final_score = _clip(base_total - penalty, 0, 100)

    # ---------- التصنيف ----------
    if breakout_total >= 15 and final_score >= 55:
        classification = "🚀 اختراق صاعد"
    elif penalty >= 6 and final_score < 50:
        classification = "⚠️ تصريف/توزيع"
    elif accumulation_score >= 18 and abs(price_chg_20 or 0) < 0.06:
        classification = "📦 تجميع هادئ"
    elif reversal_score >= 9:
        classification = "🔄 ارتداد من تشبع بيع"
    elif final_score >= 60:
        classification = "✅ زخم صاعد عام"
    else:
        classification = "👀 متابعة"

    return {
        "total": round(final_score, 1),
        "base_before_penalty": round(base_total, 1),
        "penalty": round(penalty, 1),
        "sub_scores": sub_scores,
        "classification": classification,
        "signals": signals,
        "rsi14": round(float(rsi_last), 1) if not np.isnan(rsi_last) else None,
        "close": round(float(close_last), 2),
        "vol_ratio_today": round(float(vol_ratio_today), 2) if vol_ratio_today is not None and not np.isnan(vol_ratio_today) else None,
        "price_chg_20d_pct": round(float(price_chg_20) * 100, 1) if price_chg_20 is not None and not np.isnan(price_chg_20) else None,
    }
