# -*- coding: utf-8 -*-
"""
لوحة تاسي الذكية - واجهة الويب (Streamlit)
=============================================
تُعرض هذه اللوحة كرابط واحد دائم على Streamlit Community Cloud.
تقرأ البيانات من قاعدة البيانات التاريخية (data/tasi_scores.db) التي
يحدّثها GitHub Actions يومياً تلقائياً (ملف .github/workflows/daily_update.yml).

تشغيل محلي للتجربة فقط:
    streamlit run app.py
"""
import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="تاسي الذكي - التقييم اليومي", page_icon="📊", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { direction: rtl; text-align: right; font-family: 'Tahoma','Segoe UI',sans-serif; }
[data-testid="stMetricLabel"] { direction: rtl; }
[data-testid="stSidebar"] { direction: rtl; }
div[data-testid="stDataFrame"] { direction: rtl; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=600)
def get_available_dates():
    return db.available_dates()


@st.cache_data(ttl=600)
def get_date_data(report_date):
    return db.load_date(report_date)


@st.cache_data(ttl=600)
def get_stock_history(code):
    return db.load_stock_history(code)


CLASS_COLORS = {
    "🚀 اختراق صاعد": "#0a8a3a",
    "📦 تجميع هادئ": "#1f6feb",
    "🔄 ارتداد من تشبع بيع": "#9b59b6",
    "✅ زخم صاعد عام": "#27ae60",
    "⚠️ تصريف/توزيع": "#c0392b",
    "👀 متابعة": "#7f8c8d",
}


def render_header(dates):
    c1, c2 = st.columns([3, 1])
    with c1:
        st.title("📊 تاسي الذكي - تقييم احتمالية بدء موجة صعود")
        st.caption("تحليل فني وكمي يومي لكل أسهم السوق الرئيسية (تاسي) - تجميع، سيولة ذكية، اختراقات، وتشبع بيع")
    with c2:
        if dates:
            st.metric("آخر تحديث", dates[0])
        else:
            st.metric("آخر تحديث", "لا توجد بيانات بعد")


def render_empty_state():
    st.warning(
        "لا توجد بيانات في قاعدة البيانات بعد. إذا كان هذا أول تشغيل، انتظر أول دورة تحديث "
        "تلقائية من GitHub Actions (أو شغّل `python tasi_smart_score.py` يدوياً مرة واحدة)."
    )


def main():
    dates = get_available_dates()
    render_header(dates)

    if not dates:
        render_empty_state()
        return

    with st.sidebar:
        st.header("⚙️ الفلاتر")
        selected_date = st.selectbox("التاريخ", dates, index=0)
        df = get_date_data(selected_date)

        sectors = sorted(df["sector"].dropna().unique().tolist()) if not df.empty else []
        selected_sectors = st.multiselect("القطاع", sectors, default=[])

        classes = sorted(df["classification"].dropna().unique().tolist()) if not df.empty else []
        selected_classes = st.multiselect("التصنيف", classes, default=[])

        min_score = st.slider("أقل درجة", 0, 100, 0, step=5)
        top_n = st.slider("عدد الأسهم المعروضة", 5, 100, 20, step=5)

        st.markdown("---")
        st.caption("🔍 بحث سريع عن سهم لعرض تاريخ درجته")
        search_code = st.text_input("رمز السهم (مثال: 1120)")

    if df.empty:
        st.info("لا توجد بيانات لهذا التاريخ.")
        return

    filtered = df.copy()
    if selected_sectors:
        filtered = filtered[filtered["sector"].isin(selected_sectors)]
    if selected_classes:
        filtered = filtered[filtered["classification"].isin(selected_classes)]
    filtered = filtered[filtered["score"] >= min_score]
    filtered = filtered.sort_values("score", ascending=False).head(top_n)

    # ----- مؤشرات سريعة -----
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("عدد الأسهم المحلَّلة", len(df))
    m2.metric("متوسط الدرجة", round(df["score"].mean(), 1))
    m3.metric("إشارات تجميع/اختراق قوية (≥70)", int((df["score"] >= 70).sum()))
    m4.metric("تحذيرات تصريف", int((df["classification"] == "⚠️ تصريف/توزيع").sum()))

    st.markdown("### 🏆 الترتيب اليومي")
    display_df = filtered[[
        "classification",
        "score",
        "price_chg_20d_pct",
        "price",
        "sector",
        "name",
        "code",
    ]].rename(columns={
        "classification": "التصنيف",
        "score": "الدرجة",
        "price_chg_20d_pct": "تغير 20 يوم %",
        "price": "السعر",
        "sector": "القطاع",
        "name": "الاسم",
        "code": "الرمز",
    })

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "الدرجة": st.column_config.ProgressColumn(
                "الدرجة", min_value=0, max_value=100, format="%.0f"
            ),
            "تغير 20 يوم %": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )

    st.markdown("### 🧠 أسباب الاختيار (تفصيلي)")
    for _, row in filtered.iterrows():
        color = CLASS_COLORS.get(row["classification"], "#888")
        with st.expander(f"{row['code']} - {row['name']}  |  الدرجة: {row['score']:.0f}  |  {row['classification']}"):
            st.markdown(
                f"<span style='color:{color}; font-weight:bold'>{row['classification']}</span>",
                unsafe_allow_html=True,
            )
            st.write(f"**القطاع:** {row['sector']}  |  **السعر:** {row['price']}  |  **RSI(14):** {row['rsi14']}")
            st.write("**الإشارات المرصودة:**")
            reasons = (row["reasons"] or "").split(" | ")
            for r in reasons:
                if r:
                    st.markdown(f"- {r}")

    # ----- تاريخ سهم محدد -----
    if search_code.strip():
        st.markdown(f"### 📈 تاريخ درجة السهم {search_code.strip()}")
        hist = get_stock_history(search_code.strip())
        if hist.empty:
            st.info("لا يوجد سجل تاريخي لهذا الرمز بعد.")
        else:
            hist_chart = hist.set_index("report_date")[["score"]]
            st.line_chart(hist_chart)
            st.dataframe(
                hist[["report_date", "price", "score", "classification", "reasons"]],
                use_container_width=True, hide_index=True,
            )

    st.markdown("---")
    st.caption(
        "⚠️ هذا تحليل فني وكمي إحصائي وليس توصية استثمارية أو ضمانة لأي تحرك سعري. "
        "البيانات من Yahoo Finance وتُحدَّث تلقائياً يومياً بعد إغلاق السوق."
    )


if __name__ == "__main__":
    main()
