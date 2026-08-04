# -*- coding: utf-8 -*-
"""
وحدة قاعدة البيانات - تخزين تاريخي لنتائج التقييم اليومي
==========================================================
تستخدم SQLite (ملف واحد، بدون أي إعداد خادم) - مناسبة لهذا النطاق
(عشرات آلاف الصفوف سنوياً) وتُقرأ مباشرة من لوحة Streamlit.
"""
import os
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tasi_scores.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_scores (
    report_date TEXT NOT NULL,
    code TEXT NOT NULL,
    name TEXT,
    sector TEXT,
    price REAL,
    price_chg_20d_pct REAL,
    rsi14 REAL,
    score REAL,
    classification TEXT,
    score_accumulation REAL,
    score_liquidity REAL,
    score_reversal REAL,
    score_breakout REAL,
    score_trend REAL,
    distribution_penalty REAL,
    reasons TEXT,
    PRIMARY KEY (report_date, code)
);
CREATE INDEX IF NOT EXISTS idx_daily_scores_date ON daily_scores(report_date);
CREATE INDEX IF NOT EXISTS idx_daily_scores_code ON daily_scores(code);
"""


def init_db(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def save_report(report_df: pd.DataFrame, report_date: str, db_path=DB_PATH):
    """يحفظ/يحدّث (upsert) نتائج يوم واحد. report_df بنفس أعمدة tasi_smart_score.build_report"""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows = []
    for _, r in report_df.iterrows():
        rows.append((
            report_date, r["الرمز"], r["الاسم"], r["القطاع"],
            r["السعر"], r["التغير_20ساعة_%"], r["RSI14"], r["الدرجة"],
            r["التصنيف"], r["تجميع_ذكي"], r["سيولة_ذكية"], r["تشبع_بيع_وارتداد"],
            r["اختراق_فني"], r["بنية_الاتجاه"], r["عقوبة_تصريف"], r["أسباب_الاختيار (بناءً على 1h)"],
        ))
    cur.executemany("""
        INSERT INTO daily_scores (
            report_date, code, name, sector, price, price_chg_20d_pct, rsi14,
            score, classification, score_accumulation, score_liquidity,
            score_reversal, score_breakout, score_trend, distribution_penalty, reasons
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(report_date, code) DO UPDATE SET
            name=excluded.name, sector=excluded.sector, price=excluded.price,
            price_chg_20d_pct=excluded.price_chg_20d_pct, rsi14=excluded.rsi14,
            score=excluded.score, classification=excluded.classification,
            score_accumulation=excluded.score_accumulation,
            score_liquidity=excluded.score_liquidity,
            score_reversal=excluded.score_reversal,
            score_breakout=excluded.score_breakout,
            score_trend=excluded.score_trend,
            distribution_penalty=excluded.distribution_penalty,
            reasons=excluded.reasons
    """, rows)
    conn.commit()
    conn.close()
    return len(rows)


def available_dates(db_path=DB_PATH):
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    dates = pd.read_sql(
        "SELECT DISTINCT report_date FROM daily_scores ORDER BY report_date DESC", conn
    )["report_date"].tolist()
    conn.close()
    return dates


def load_date(report_date, db_path=DB_PATH):
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT * FROM daily_scores WHERE report_date = ? ORDER BY score DESC",
        conn, params=(report_date,)
    )
    conn.close()
    return df


def load_stock_history(code, db_path=DB_PATH):
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql(
        "SELECT * FROM daily_scores WHERE code = ? ORDER BY report_date ASC",
        conn, params=(str(code),)
    )
    conn.close()
    return df


def load_all(db_path=DB_PATH):
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    df = pd.read_sql("SELECT * FROM daily_scores", conn)
    conn.close()
    return df
