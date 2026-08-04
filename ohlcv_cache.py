# -*- coding: utf-8 -*-
"""
ذاكرة OHLCV للبيانات اللحظية (1h)
==================================
تخزين تاريخ الأسعار لكل سهم في ملف CSV داخل data/prices_1h/
بحيث يُجلب التاريخ الكامل مرة واحدة (بذر) ثم تُحدَّث الزيادة فقط (delta).

الملفات غير مرفوعة إلى git (انظر .gitignore) ويتم الاحتفاظ بها عبر
GitHub Actions cache بين التشغيلات.
"""
import os

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "prices_1h")
SEED_PERIOD = "6mo"
DELTA_PERIOD = "10d"
MIN_ROWS_FOR_DELTA = 100
PRUNE_DAYS = 200
COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _path(symbol):
    safe = symbol.replace(".", "_")
    return os.path.join(CACHE_DIR, f"{safe}.csv")


def load(symbol):
    """يرجع DataFrame بفهرس Datetime (UTC) أو None إن لم يوجد ملف كافٍ"""
    p = _path(symbol)
    if not os.path.exists(p):
        return None
    try:
        df = pd.read_csv(p)
    except Exception:
        return None
    if df.empty:
        return None
    try:
        df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
    except Exception:
        return None
    df = df.set_index("Datetime")
    return df


def save(symbol, df):
    os.makedirs(CACHE_DIR, exist_ok=True)
    if df is None or df.empty:
        return
    cols = [c for c in COLUMNS if c in df.columns]
    out = df[cols].dropna(subset=["Close", "Volume"])
    out.index = pd.to_datetime(out.index, utc=True)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.to_csv(_path(symbol), index_label="Datetime")


def merge(existing, new):
    """دمج التاريخ الكامل مع الجديد، مع إزالة التكرار بالطابع الزمني"""
    if existing is None or existing.empty:
        return new
    if new is None or new.empty:
        return existing
    cols = [c for c in COLUMNS if c in new.columns]
    if not cols:
        return existing
    combined = pd.concat([existing[cols], new[cols]])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined.dropna(subset=["Close", "Volume"])


def prune(df, days=PRUNE_DAYS):
    """إبقاء آخر ~6 أشهر فقط لمنع تضخم الملفات"""
    if df is None or df.empty:
        return df
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index >= cutoff]
