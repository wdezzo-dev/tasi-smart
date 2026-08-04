# -*- coding: utf-8 -*-
"""
النظام الرئيسي — تاسي الذكي
يحلل السوق السعودي والأمريكي ويرسل التنبيهات لتيليجرام
"""
import os
import sys
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd

import scoring
import db
import notify
import ohlcv_cache

warnings.filterwarnings("ignore")

try:
    import yfinance as yf
except ImportError:
    print("الحزمة yfinance غير مثبتة.")
    sys.exit(1)

TICKERS_FILE      = os.path.join(os.path.dirname(__file__), "tickers_tasi.csv")
OUTPUT_DIR        = os.path.join(os.path.dirname(__file__), "reports")
HISTORY_PERIOD    = "6mo"
INTERVAL          = "1h"
BATCH_SIZE        = 10
TOP_N             = 20
REQUEST_PAUSE_SEC = 2.0


def load_universe(path=TICKERS_FILE):
    df = pd.read_csv(path, dtype=str)
    df["yahoo_symbol"] = df["code"].str.strip() + ".SR"
    return df


def _download(symbols, period):
    if not symbols:
        return {}
    data = yf.download(
        tickers=" ".join(symbols),
        period=period,
        interval=INTERVAL,
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )
    result = {}
    if len(symbols) == 1:
        sym = symbols[0]
        if not data.empty:
            result[sym] = data
        return result
    for sym in symbols:
        try:
            sub = data[sym].dropna(how="all")
            if not sub.empty:
                result[sym] = sub
        except Exception:
            continue
    return result


def fetch_batch(symbols, seed_period=HISTORY_PERIOD, delta_period=ohlcv_cache.DELTA_PERIOD):
    """يجلب بذرة كاملة للسهم بدون ذاكرة، وزيادة (delta) للسهم المخزّن، ثم يدمج ويحفظ"""
    existing = {s: ohlcv_cache.load(s) for s in symbols}
    to_seed = [s for s in symbols
               if existing[s] is None or len(existing[s]) < ohlcv_cache.MIN_ROWS_FOR_DELTA]
    to_delta = [s for s in symbols if s not in to_seed]

    result = {}
    if to_seed:
        result.update(_download(to_seed, seed_period))
    if to_delta:
        result.update(_download(to_delta, delta_period))

    for sym in symbols:
        df = result.get(sym)
        if df is None or df.empty:
            continue
        merged = ohlcv_cache.merge(existing[sym], df)
        merged = ohlcv_cache.prune(merged)
        if merged is None or merged.empty:
            result.pop(sym, None)
            continue
        ohlcv_cache.save(sym, merged)
        result[sym] = merged
    return result


def build_report(universe_df):
    rows   = []
    failed = []
    symbols = universe_df["yahoo_symbol"].tolist()

    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        print(f"🇸🇦 جلب تاسي دفعة {i//BATCH_SIZE+1} "
              f"({i+1}-{min(i+BATCH_SIZE, len(symbols))} من {len(symbols)})...")
        try:
            batch_data = fetch_batch(batch)
        except Exception as e:
            print(f"  خطأ: {e}")
            failed.extend(batch)
            continue

        for sym in batch:
            df = batch_data.get(sym)
            if df is None or df.empty:
                failed.append(sym); continue
            try:
                result = scoring.compute_score(df)
            except Exception:
                failed.append(sym); continue
            if result is None:
                failed.append(sym); continue

            code = sym.replace(".SR", "")
            meta = universe_df.loc[universe_df["yahoo_symbol"] == sym].iloc[0]
            rows.append({
                "الرمز":             code,
                "الاسم":             meta["name"],
                "القطاع":            meta["sector"],
                "السعر":             result["close"],
                "التغير_20ساعة_%":    result["price_chg_20d_pct"],
                "RSI14":             result["rsi14"],
                "الدرجة":            result["total"],
                "التصنيف":           result["classification"],
                "تجميع_ذكي":        result["sub_scores"]["تجميع_ذكي"],
                "سيولة_ذكية":       result["sub_scores"]["سيولة_ذكية"],
                "تشبع_بيع_وارتداد": result["sub_scores"]["تشبع_بيع_وارتداد"],
                "اختراق_فني":        result["sub_scores"]["اختراق_فني"],
                "بنية_الاتجاه":     result["sub_scores"]["بنية_الاتجاه"],
                "عقوبة_تصريف":      result["penalty"],
                "أسباب_الاختيار (بناءً على 1h)":   " | ".join(result["signals"]) if result["signals"] else "لا توجد إشارات",
            })
        time.sleep(REQUEST_PAUSE_SEC)

    report_df = pd.DataFrame(rows)
    if not report_df.empty:
        report_df = report_df.sort_values("الدرجة", ascending=False).reset_index(drop=True)
        report_df.index += 1
        report_df.index.name = "الترتيب"

    print(f"\n✅ تاسي: تم تحليل {len(rows)} سهم. فشل {len(failed)}.")
    return report_df


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    is_last_run = datetime.utcnow().hour == 13  # تنبيهات تيليجرام مرة واحدة يومياً (آخر تشغيل 13:00 UTC)

    # ══════════════════════════════
    # 1) السوق السعودي (تاسي)
    # ══════════════════════════════
    print("=" * 50)
    print("🇸🇦 بدء تحليل السوق السعودي (تاسي)...")
    print("=" * 50)
    universe = load_universe()
    print(f"عدد الأسهم: {len(universe)}")

    report_df = build_report(universe)
    if not report_df.empty:
        n_saved = db.save_report(report_df, today_str)
        print(f"تم حفظ {n_saved} سهم في قاعدة البيانات.")
        if is_last_run:
            top_sa = report_df.head(TOP_N).to_dict("records")
            notify.send_daily_alerts(top_sa, today_str)
        csv_path = os.path.join(OUTPUT_DIR, f"tasi_report_{today_str}.csv")
        report_df.to_csv(csv_path, encoding="utf-8-sig")
        print(f"تم حفظ CSV: {csv_path}")
    else:
        print("لم تُنتج نتائج للسوق السعودي.")

    # ══════════════════════════════
    # 2) السوق الأمريكي (مرة واحدة يومياً في آخر تشغيل)
    # ══════════════════════════════
    if is_last_run:
        print("\n" + "=" * 50)
        print("🇺🇸 بدء تحليل السوق الأمريكي...")
        print("=" * 50)
        try:
            import us_smart_score
            us_smart_score.run_us_analysis(today_str)
        except Exception as e:
            print(f"⚠️ خطأ في تحليل السوق الأمريكي: {e}")

    print("\n✅ اكتمل التحليل اليومي.")


if __name__ == "__main__":
    main()
