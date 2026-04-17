"""
pages/1_📈_策略回測.py
1012 極速框策略歷史回測頁面
使用方式：放在 pages/ 資料夾，Streamlit 自動識別為多頁面
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_fetcher import get_all_timeframes
from strategy import run_strategy

st.set_page_config(
    page_title="策略回測 | 1012 極速框",
    page_icon="📈",
    layout="wide",
)

st.title("📈 策略歷史回測")
st.caption("驗證 1012、V轉Reload、回踩進場的真實勝率與風報比")

# ─────────────────────────────────────────────────────────────────────
# 側邊欄
# ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 回測設定")
    raw_tickers = st.text_area(
        "回測標的（每行一個）",
        value="2330\n2317\n2454\n8028\n3376",
        height=160,
    )
    col1, col2 = st.columns(2)
    with col1:
        ma_fast  = st.number_input("快均線",   min_value=3,  max_value=50,  value=10, step=1)
        sb_ratio = st.number_input("目標倍數", min_value=1.0, max_value=20.0, value=5.8, step=0.1)
    with col2:
        ma_slow = st.number_input("慢均線",   min_value=50, max_value=500, value=200, step=10)
        period  = st.selectbox("回測期間", ["1y", "2y", "3y"], index=1)

    init_capital = st.number_input(
        "初始資金（元）", min_value=100000, max_value=10000000,
        value=1000000, step=100000,
        format="%d",
    )
    run_btn = st.button("🚀 開始回測", type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────────────
# 快取：獨立呼叫 run_strategy（不依賴主頁快取）
# ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_backtest(ticker, period, ma_fast, ma_slow, sb_ratio):
    try:
        data = get_all_timeframes(ticker, period)
        df, trade_log = run_strategy(
            data["daily"], data["weekly"],
            ma_fast, ma_slow, sb_ratio,
            data["3d"],
        )
        return trade_log, data["ticker"]
    except Exception as e:
        return [], ticker


# ─────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────
if not run_btn:
    st.info("👈 設定回測標的與參數，點擊「開始回測」")
    st.stop()

tickers  = [t.strip() for t in raw_tickers.strip().split("\n") if t.strip()]
all_logs = []
errors   = []

prog = st.progress(0, text="回測中…")
for i, raw_t in enumerate(tickers):
    prog.progress((i+1)/len(tickers), text=f"回測 {raw_t}…")
    log, resolved = run_backtest(raw_t, period, ma_fast, ma_slow, sb_ratio)
    for trade in log:
        trade["標的"] = resolved
    all_logs.extend(log)
    if not log:
        errors.append(raw_t)
prog.empty()

if errors:
    st.warning(f"以下標的無資料或無交易紀錄：{', '.join(errors)}")

if not all_logs:
    st.error("回測期間內無任何交易紀錄，請更換標的或延長期間。")
    st.stop()

df_log = pd.DataFrame(all_logs)

# 確保數值欄位型別正確
df_log["報酬率(%)"] = pd.to_numeric(df_log["報酬率(%)"], errors="coerce")
df_log["R倍數"]     = pd.to_numeric(df_log["R倍數"],     errors="coerce")
df_log["進場日期"]  = pd.to_datetime(df_log["進場日期"])
df_log["出場日期"]  = pd.to_datetime(df_log["出場日期"])
df_log = df_log.sort_values("出場日期").reset_index(drop=True)

# 過濾掉「持倉中未結算」的紀錄（不計入勝率）
df_closed = df_log[df_log["出場原因"] != "持倉中（未結算）"].copy()

# ─────────────────────────────────────────────────────────────────────
# 計算統計
# ─────────────────────────────────────────────────────────────────────
total_trades  = len(df_closed)
win_trades    = (df_closed["報酬率(%)"] > 0).sum()
lose_trades   = total_trades - win_trades
win_rate      = win_trades / total_trades * 100 if total_trades > 0 else 0
avg_win       = df_closed.loc[df_closed["報酬率(%)"] > 0, "報酬率(%)"].mean()
avg_lose      = df_closed.loc[df_closed["報酬率(%)"] <= 0, "報酬率(%)"].mean()
avg_r         = df_closed["R倍數"].mean()
# 系統期望值 = 勝率 × 平均獲利 + 敗率 × 平均虧損
expect_val    = (win_rate/100 * (avg_win or 0) +
                 (1 - win_rate/100) * (avg_lose or 0))

# ─────────────────────────────────────────────────────────────────────
# 戰情總覽
# ─────────────────────────────────────────────────────────────────────
st.subheader("🎯 戰情總覽")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("總交易次數", total_trades)
c2.metric("獲利次數",   f"{win_trades} 次")
c3.metric("整體勝率",   f"{win_rate:.1f}%",
          delta=f"{'正期望' if expect_val > 0 else '負期望'}")
c4.metric("平均 R 倍數", f"{avg_r:.2f}R" if pd.notna(avg_r) else "—")
c5.metric("平均獲利",
          f"{avg_win:.1f}%" if pd.notna(avg_win) else "—")
c6.metric("系統期望值",
          f"{expect_val:.2f}%",
          delta="正期望值 ✅" if expect_val > 0 else "負期望值 ⚠️")

st.divider()

# ─────────────────────────────────────────────────────────────────────
# 策略細分比較
# ─────────────────────────────────────────────────────────────────────
st.subheader("📊 策略類型細分")

strategy_stats = []
for entry_type in df_closed["進場類型"].unique():
    sub = df_closed[df_closed["進場類型"] == entry_type]
    wins = (sub["報酬率(%)"] > 0).sum()
    total = len(sub)
    wr   = wins / total * 100 if total > 0 else 0
    ar   = sub["R倍數"].mean()
    ap   = sub["報酬率(%)"].mean()
    ev   = (wr/100 * sub.loc[sub["報酬率(%)"]>0,"報酬率(%)"].mean() or 0) + \
           ((1-wr/100) * sub.loc[sub["報酬率(%)"]<=0,"報酬率(%)"].mean() or 0)
    strategy_stats.append({
        "進場策略":   entry_type,
        "交易次數":   total,
        "勝率(%)":    round(wr, 1),
        "平均R倍數":  round(ar, 2) if pd.notna(ar) else None,
        "平均報酬(%)":round(ap, 2) if pd.notna(ap) else None,
        "期望值(%)":  round(ev, 2),
    })

df_strat = pd.DataFrame(strategy_stats)

def color_wr(val):
    if isinstance(val, (int, float)):
        if val >= 60: return "color:#16a34a;font-weight:600"
        if val >= 45: return "color:#b45309"
        return "color:#dc2626"
    return ""

def color_ev(val):
    if isinstance(val, (int, float)):
        return "color:#16a34a" if val > 0 else "color:#dc2626"
    return ""

st.dataframe(
    df_strat.style
        .applymap(color_wr, subset=["勝率(%)"])
        .applymap(color_ev, subset=["期望值(%)"]),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ─────────────────────────────────────────────────────────────────────
# 資金曲線
# ─────────────────────────────────────────────────────────────────────
st.subheader("📈 資金曲線（Equity Curve）")

# 假設每筆交易固定投入 10% 資金（可調整）
position_pct = st.slider("每筆交易投入比例 (%)", 5, 30, 10, 5)

capital = float(init_capital)
equity  = [capital]
dates   = [df_closed["進場日期"].iloc[0] if not df_closed.empty else pd.Timestamp.now()]

for _, trade in df_closed.iterrows():
    pnl_pct = trade["報酬率(%)"] / 100
    trade_pnl = capital * (position_pct / 100) * pnl_pct
    capital   = capital + trade_pnl
    equity.append(capital)
    dates.append(trade["出場日期"])

fig_eq = go.Figure()
fig_eq.add_trace(go.Scatter(
    x=dates, y=equity,
    mode="lines+markers",
    name="資金水位",
    line=dict(color="#3b82f6", width=2),
    marker=dict(size=5),
    fill="tozeroy",
    fillcolor="rgba(59,130,246,0.08)",
    hovertemplate="日期：%{x|%Y-%m-%d}<br>資金：%{y:,.0f} 元<extra></extra>",
))

# 標注最高點與最低點
max_idx = equity.index(max(equity))
min_idx = equity.index(min(equity))
for i, label, color in [(max_idx, "最高", "#16a34a"), (min_idx, "最低", "#dc2626")]:
    fig_eq.add_annotation(
        x=dates[i], y=equity[i],
        text=f"{label}<br>{equity[i]:,.0f}",
        font=dict(color=color, size=10),
        showarrow=True, arrowhead=2, arrowcolor=color,
        ax=0, ay=-30,
    )

# 初始資金水平線
fig_eq.add_hline(
    y=init_capital,
    line=dict(color="rgba(107,114,128,0.5)", dash="dash", width=1),
    annotation_text=f"初始資金 {init_capital:,.0f}",
    annotation_font_size=10,
)

fig_eq.update_layout(
    height=400,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=20, t=20, b=10),
    yaxis=dict(tickformat=",.0f", gridcolor="rgba(128,128,128,0.12)"),
    xaxis=dict(gridcolor="rgba(128,128,128,0.12)"),
    showlegend=False,
)
st.plotly_chart(fig_eq, use_container_width=True)

# 最終資金摘要
final_cap   = equity[-1]
total_return = (final_cap - init_capital) / init_capital * 100
col_a, col_b, col_c = st.columns(3)
col_a.metric("最終資金",   f"{final_cap:,.0f} 元")
col_b.metric("總報酬",     f"{total_return:.1f}%",
             delta=f"{final_cap-init_capital:+,.0f} 元")
col_c.metric("最大回撤",
             f"{min(equity)/max(equity[:equity.index(max(equity))+1])*100-100:.1f}%"
             if len(equity) > 1 else "—")

st.divider()

# ─────────────────────────────────────────────────────────────────────
# 交易明細表
# ─────────────────────────────────────────────────────────────────────
st.subheader("📋 完整交易明細")

# 篩選器
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filter_type = st.multiselect(
        "進場策略",
        df_log["進場類型"].unique().tolist(),
        default=df_log["進場類型"].unique().tolist(),
    )
with col_f2:
    filter_result = st.radio(
        "勝負篩選",
        ["全部", "只看獲利", "只看虧損"],
        horizontal=True,
    )
with col_f3:
    if len(tickers) > 1:
        filter_ticker = st.multiselect(
            "標的",
            df_log["標的"].unique().tolist(),
            default=df_log["標的"].unique().tolist(),
        )
    else:
        filter_ticker = df_log["標的"].unique().tolist()

df_display = df_log[
    df_log["進場類型"].isin(filter_type) &
    df_log["標的"].isin(filter_ticker)
].copy()

if filter_result == "只看獲利":
    df_display = df_display[df_display["報酬率(%)"] > 0]
elif filter_result == "只看虧損":
    df_display = df_display[df_display["報酬率(%)"] <= 0]

# 格式化顯示
df_display["進場日期"] = df_display["進場日期"].dt.strftime("%Y-%m-%d")
df_display["出場日期"] = df_display["出場日期"].dt.strftime("%Y-%m-%d")

def color_pnl(val):
    if isinstance(val, (int, float)):
        return "color:#16a34a;font-weight:600" if val > 0 else "color:#dc2626;font-weight:600"
    return ""

col_order = ["標的","進場日期","出場日期","進場類型","進場價","出場價",
             "出場原因","報酬率(%)","R倍數","勝負"]
col_order = [c for c in col_order if c in df_display.columns]

st.dataframe(
    df_display[col_order].style
        .applymap(color_pnl, subset=["報酬率(%)","R倍數"]),
    use_container_width=True,
    hide_index=True,
    height=min(600, 56 + len(df_display) * 38),
)

# 下載按鈕
csv = df_display[col_order].to_csv(index=False, encoding="utf-8-sig")
st.download_button(
    label="⬇️ 下載交易明細 CSV",
    data=csv,
    file_name="1012_backtest_log.csv",
    mime="text/csv",
)