"""
app.py  ─  1012 極速框量化儀表板（含手動持倉管理）
啟動指令：streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_fetcher import get_all_timeframes
from strategy import run_strategy, get_today_summary, analyze_manual_position

st.set_page_config(
    page_title="1012 極速框儀表板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
div[data-testid="stMetric"] {
    border: 1px solid rgba(128,128,128,0.2);
    border-radius: 10px; padding: 12px 16px;
}
.badge {
    display: inline-block; padding: 2px 10px;
    border-radius: 12px; font-size: 12px; font-weight: 500; margin: 2px;
}
.badge-green  { background:#d1fae5; color:#065f46; }
.badge-blue   { background:#dbeafe; color:#1e3a8a; }
.badge-amber  { background:#fef3c7; color:#92400e; }
.badge-red    { background:#fee2e2; color:#7f1d1d; }
.badge-purple { background:#ede9fe; color:#4c1d95; }
.badge-cyan   { background:#cffafe; color:#164e63; }
.badge-gray   { background:#f3f4f6; color:#374151; }
.pos-card {
    border-radius: 12px; padding: 16px 20px; margin-bottom: 12px;
    border-left: 5px solid;
}
.pos-danger  { background:#fff5f5; border-color:#ef4444; }
.pos-warning { background:#fffbeb; border-color:#f59e0b; }
.pos-success { background:#f0fdf4; border-color:#22c55e; }
.pos-info    { background:#eff6ff; border-color:#3b82f6; }
.pos-title   { font-size:18px; font-weight:600; margin-bottom:4px; }
.pos-sub     { font-size:13px; color:#6b7280; }
.kv-row      { display:flex; gap:32px; margin-top:10px; flex-wrap:wrap; }
.kv-item     { min-width:100px; }
.kv-label    { font-size:11px; color:#9ca3af; margin-bottom:2px; }
.kv-value    { font-size:15px; font-weight:500; }
</style>
""", unsafe_allow_html=True)

# ── Session State ──────────────────────────────────────────────────────
if "results"   not in st.session_state: st.session_state.results   = {}
if "scan_time" not in st.session_state: st.session_state.scan_time = None
if "portfolio" not in st.session_state: st.session_state.portfolio = []

# ── 側邊欄 ────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ 策略設定")
    raw_watchlist = st.text_area(
        "監控清單（每行一個代號）",
        value="2330\n2317\n2454\n2308\n2382\n3711\n6669\n2603\n2881\n2891",
        height=200,
    )
    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        ma_fast  = st.number_input("快均線",   min_value=3,   max_value=50,   value=10,  step=1)
        sb_ratio = st.number_input("目標倍數", min_value=1.0, max_value=20.0, value=5.8, step=0.1)
    with col_b:
        ma_slow = st.number_input("慢均線",   min_value=50,  max_value=500,  value=200, step=10)
        period  = st.selectbox("資料期間", ["1y", "2y", "3y"], index=1)

     # ★ 極速框計算週期選擇器
    tf_display = st.selectbox(
        "⚙️ 極速框計算週期",
        ["1D（日線）", "3D（三日線）", "1W（週線）"],
        index=0,
        help="選擇用哪個週期的 T-1 高低點來計算極速框目標位與 TP1~TP3"
    )
    tf_map     = {"1D（日線）": "1D", "3D（三日線）": "3D", "1W（週線）": "1W"}
    timeframe  = tf_map[tf_display]
    st.divider()
    scan_btn = st.button("🔍 開始掃描", type="primary", use_container_width=True)
    st.caption("每檔約 2–5 秒，掃描期間請耐心等候。")


@st.cache_data(ttl=3600, show_spinner=False)
def cached_analyze(ticker, period, ma_fast, ma_slow, sb_ratio, timeframe):
    data = get_all_timeframes(ticker, period)
    df, _trade_log = run_strategy(          # ★ 解包 tuple
        data["daily"], data["weekly"],
        ma_fast, ma_slow, sb_ratio,
        data["3d"],
        timeframe,
    )
    summ = get_today_summary(df, data["ticker"])
    return df, summ                          # trade_log 回測頁面自己另外呼叫


if scan_btn:
    watchlist = [t.strip() for t in raw_watchlist.strip().split("\n") if t.strip()]
    if not watchlist:
        st.sidebar.error("請至少輸入一個代號！")
    else:
        prog    = st.sidebar.progress(0, text="初始化…")
        errors  = []
        results = {}
        for i, raw_ticker in enumerate(watchlist):
            prog.progress((i+1)/len(watchlist), text=f"分析 {raw_ticker}…")
            try:
                df, summ = cached_analyze(raw_ticker, period, ma_fast, ma_slow, sb_ratio, timeframe)  # ★
                results[summ["ticker"]] = {"df": df, "summary": summ}
            except Exception as e:
                errors.append(f"❌ {raw_ticker}：{e}")
        prog.empty()
        st.session_state.results   = results
        st.session_state.scan_time = pd.Timestamp.now()
        if errors:
            with st.sidebar.expander("⚠️ 部分標的失敗", expanded=True):
                for e in errors: st.markdown(e)

# ── 主標題 ────────────────────────────────────────────────────────────
st.title("📊 1012 極速框量化儀表板")
results = st.session_state.results
if not results:
    st.info("👈 請在左側設定監控清單，點擊「開始掃描」後結果將顯示於此。")
    st.stop()

scan_time = st.session_state.scan_time
if scan_time:
    st.caption(f"最後掃描：{scan_time.strftime('%Y-%m-%d %H:%M:%S')} ｜ 共 {len(results)} 檔")

summaries = [v["summary"] for v in results.values()]
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("🟢 今日進場",   sum(s["signal_1012"]  for s in summaries))
c2.metric("🔷 極速框中",   sum(s["sb_active"]    for s in summaries))
c3.metric("⭐ 極速框成立", sum(s["speed_box_ok"] for s in summaries))
c4.metric("🔴 觸發停損",   sum(s["weekly_sl"] or s["sb_stop"] for s in summaries))
c5.metric("💰 停利訊號",   sum(s["weekly_tp"]    for s in summaries))
c6.metric("🔁 V轉Reload",  sum(s["v_reload"]     for s in summaries))

# ── 聽牌雷達 ──────────────────────────────────────────────────────────
on_deck_list = [
    s for s in summaries
    if s.get("is_on_deck") and not s.get("in_position")
]

if on_deck_list:
    st.markdown("---")
    st.markdown("### 👀 聽牌雷達 — 明日可能觸發進場")
    cols = st.columns(min(len(on_deck_list), 4))

    for ci, s in enumerate(on_deck_list):
        close   = s["close"]
        trigger = s["target_trigger_price"]
        ticker  = s["ticker"]

        if trigger is None:
            continue

        gap_pct = (trigger - close) / close * 100

        if close >= trigger:
            status_color = "#16a34a"
            status_bg    = "#f0fdf4"
            status_border= "#22c55e"
            status_text  = "🟢 若收盤維持此價位，即將確認進場！"
            gap_str      = f"<span style='color:#16a34a;font-weight:600;'>現價已超觸發價</span>"
        else:
            status_color = "#b45309"
            status_bg    = "#fffbeb"
            status_border= "#f59e0b"
            status_text  = "👀 聽牌注意！明日若強勢收盤可觸發 1012"
            gap_str      = f"<span style='color:#b45309;font-weight:600;'>距觸發價還差 {gap_pct:.2f}%</span>"

        with cols[ci % 4]:
            st.markdown(f"""
<div style="
    background:{status_bg};
    border:1.5px solid {status_border};
    border-radius:12px;
    padding:14px 16px;
    margin-bottom:8px;
">
  <div style="font-size:16px;font-weight:700;color:{status_color};">{ticker}</div>
  <div style="font-size:12px;color:#6b7280;margin-bottom:8px;">{status_text}</div>
  <div style="display:flex;gap:20px;flex-wrap:wrap;">
    <div>
      <div style="font-size:10px;color:#9ca3af;">現價</div>
      <div style="font-size:15px;font-weight:600;">{close:.2f}</div>
    </div>
    <div>
      <div style="font-size:10px;color:#9ca3af;">預計觸發價</div>
      <div style="font-size:15px;font-weight:600;color:{status_color};">{trigger:.2f}</div>
    </div>
  </div>
  <div style="margin-top:8px;font-size:12px;">{gap_str}</div>
</div>
""", unsafe_allow_html=True)

st.divider()

tab_scan, tab_port, tab_chart = st.tabs([
    "📋 全市場掃描列表", "💼 持倉管理", "📈 個股 K 線圖"
])


# ══ Tab 1：掃描列表 ══════════════════════════════════════════════════
with tab_scan:
    with st.expander("📖 如何判斷進場時機？", expanded=False):
        st.markdown("""
**策略訊號解讀指南**

| 訊號 | 代表意義 | 建議行動 |
|------|----------|----------|
| 🟢 **1012 進場** | T-0 收盤確認：三根K棒組合成立，站上 MA10 & MA200 | **當日或次日開盤進場**，停損設 T-0 最低點 |
| 🔷 **極速框確認中** | 進場後連續上漲，尚未觸及目標或出現黑吞 | **持倉等待**，不要輕易出場 |
| ⭐ **極速框成立** | 連漲觸及 5.8 倍目標位 | 可考慮**分批停利**或移動停損保護 |
| 🟠 **極速框失效** | 出現黑吞（收 < 開），動能中斷 | **謹慎持倉**，觀察次日是否恢復 |
| 🔴 **週K停損** | 週黑吞 + 收盤低於進場價 | **出場**，等待下次訊號 |
| 💰 **週K停利** | 週黑吞 + 收盤高於進場價（保護獲利） | **停利出場** |
| 🔁 **V轉Reload** | 停損後回升站回進場收盤價，且無三段破低 | **可重新進場**，同樣設停損 |

> **每日使用步驟：**
> 1. 按左側「開始掃描」→ 篩選「今日進場」
> 2. 切換「個股 K 線圖」確認型態是否清晰
> 3. 進場後到「持倉管理」登錄成本，讓系統盯停損
        """)

    filter_opt = st.radio("快速篩選",
        ["全部","今日進場","聽牌中","極速框確認中","極速框成立","觸發停損","停利訊號","V轉Reload","持倉中"],
        horizontal=True, label_visibility="collapsed")

    filter_fn = {
        "全部":         lambda s: True,
        "今日進場":     lambda s: s["signal_1012"],
        "聽牌中":       lambda s: s.get("is_on_deck", False) and not s.get("in_position", False),
        "極速框確認中": lambda s: s["sb_active"],
        "極速框成立":   lambda s: s["speed_box_ok"],
        "觸發停損":     lambda s: s["weekly_sl"] or s["sb_stop"],
        "停利訊號":     lambda s: s["weekly_tp"],
        "V轉Reload":    lambda s: s["v_reload"],
        "持倉中":       lambda s: s["in_position"],
    }[filter_opt]

    rows = []
    for s in summaries:
        if not filter_fn(s): continue
        badges = []
        if s["signal_1012"]:    badges.append("🟢 1012進場")
        if s["sb_active"]:      badges.append("🔷 極速框確認")
        if s["speed_box_ok"]:   badges.append("⭐ 極速框成立")
        if s["speed_box_fail"]: badges.append("🟠 極速框失效")
        if s["sb_stop"]:        badges.append("🔴 底線停損")
        if s["weekly_sl"]:      badges.append("🔴 週K停損")
        if s["weekly_tp"]:      badges.append("💰 週K停利")
        if s["v_reload"]:       badges.append("🔁 V轉Reload")
        if s["v_blocked"]:      badges.append("⛔ V轉封鎖")
        if not badges and s["in_position"]: badges.append("📌 持倉中")
        if s.get("is_on_deck") and not s.get("in_position"):
            badges.append("👀 聽牌中")
        if not badges: badges.append("— 觀察中")
        # 回踩訊號
        if s.get("sb_pb_entry"):
            et = s.get("sb_pb_entry_type","")
            badges.append(f"🟣 回踩進場（{et}）")
        if s.get("sb_pb_monitoring") and not s.get("sb_pb_entry"):
            badges.append("🔍 回踩監控中")
        if s.get("sb_pb_dead"):
            badges.append("💀 回踩趨勢破壞")
        if s.get("sb_pb_ma_break") and not s.get("sb_pb_dead"):
            badges.append("🟠 回踩破均線")
        rows.append({
            "代號": s["ticker"], "日期": s["date"], "收盤價": round(s["close"], 2),
            "今日狀態": " | ".join(badges),
            "進場參考價": round(s["entry_price"], 2) if s["entry_price"] else "—",
            "停損參考":   round(s["stop_loss"],   2) if s["stop_loss"]   else "—",
            "極速框目標": round(s["sb_target"],   2) if s["sb_target"]   else "—",
            "防守底線":   round(s["sb_param0"],   2) if s["sb_param0"]   else "—",
        })

    if rows:
        df_table = pd.DataFrame(rows)
        def highlight_row(row):
            s = row["今日狀態"]
            if "1012" in s or "V轉Reload" in s: return ["background-color:#d1fae5"]*len(row)
            if "停損" in s:  return ["background-color:#fee2e2"]*len(row)
            if "停利" in s or "極速框成立" in s: return ["background-color:#fef3c7"]*len(row)
            if "極速框確認" in s: return ["background-color:#dbeafe"]*len(row)
            return [""]*len(row)
        st.dataframe(df_table.style.apply(highlight_row, axis=1),
                     use_container_width=True, hide_index=True,
                     height=min(700, 56+len(df_table)*38))
    else:
        st.info("目前篩選條件下無符合標的。")

    # ★ 今日觸發進場的快訊文案（與 if rows 平齊，不在裡面）
    alert_stocks = [s for s in summaries if s.get("alert_message", "")]
    if alert_stocks:
        st.markdown("---")
        st.markdown("### 🚀 今日進場快訊（可一鍵複製）")
        for s in alert_stocks:
            ticker   = s["ticker"]
            full_msg = f"[{ticker}] {s['alert_message']}"
            st.markdown(f"**{ticker}**")
            st.code(full_msg, language=None)
    else:
        st.info("目前篩選條件下無符合標的。")


# ══ Tab 2：持倉管理 ══════════════════════════════════════════════════
with tab_port:
    st.subheader("💼 我的持倉")

    with st.expander("➕ 新增持倉", expanded=(len(st.session_state.portfolio) == 0)):
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        with col1:
            new_ticker = st.text_input("股票代號", placeholder="如：2330 或 3088")
        with col2:
            new_entry  = st.number_input("進場成本（元/股）", min_value=0.1, value=100.0, step=0.1, format="%.2f")
        with col3:
            # ★ 改為股數（支援零股）
            new_shares = st.number_input(
                "持有股數（股）",
                min_value=1,
                value=1000,
                step=1,
                help="整張 = 1000 股，零股直接輸入實際股數，例如持有 50 股就填 50"
            )
        with col4:
            st.markdown("<br>", unsafe_allow_html=True)
            add_btn = st.button("新增", type="primary", use_container_width=True)

        # 快速換算提示
        st.caption(f"📌 目前輸入：{new_shares} 股 ＝ {new_shares/1000:.3f} 張　｜　市值約 {new_entry * new_shares:,.0f} 元")

        if add_btn and new_ticker.strip():
            existing = [p["ticker_raw"] for p in st.session_state.portfolio]
            if new_ticker.strip() in existing:
                st.warning(f"{new_ticker.strip()} 已在清單中，請先刪除再重新新增。")
            else:
                st.session_state.portfolio.append({
                    "ticker_raw": new_ticker.strip(),
                    "entry":      new_entry,
                    "shares":     int(new_shares),   # ★ 直接存股數，不乘 1000
                })
                st.success(f"已新增 {new_ticker.strip()}，成本 {new_entry:.2f} 元，{int(new_shares)} 股")
                st.rerun()

    portfolio = st.session_state.portfolio
    if not portfolio:
        st.info("尚無持倉。請點擊上方「新增持倉」輸入你的股票代號與進場成本。")
    else:
        _, del_col = st.columns([4, 1])
        with del_col:
            del_ticker = st.selectbox("刪除",
                ["—"] + [p["ticker_raw"] for p in portfolio],
                label_visibility="collapsed")
            if st.button("刪除選取", use_container_width=True) and del_ticker != "—":
                st.session_state.portfolio = [
                    p for p in portfolio if p["ticker_raw"] != del_ticker
                ]
                st.rerun()

        for pos in portfolio:
            raw_t  = pos["ticker_raw"]
            entry  = pos["entry"]
            shares = pos["shares"]   # ★ 現在是股數

            # 找資料
            df_pos = None
            if raw_t in results:
                df_pos = results[raw_t]["df"]
            else:
                for suffix in ["", ".TW", ".TWO"]:
                    key = raw_t + suffix if suffix else raw_t
                    if key in results:
                        df_pos = results[key]["df"]
                        break

            if df_pos is None:
                with st.spinner(f"正在拉取 {raw_t} 資料…"):
                    try:
                        data   = get_all_timeframes(raw_t, period)
                        df_pos, _ = run_strategy(    # ★ 解包，_ 忽略 trade_log
                            data["daily"], data["weekly"], ma_fast, ma_slow, sb_ratio
                        )
                        results[data["ticker"]] = {
                            "df": df_pos,
                            "summary": get_today_summary(df_pos, data["ticker"]),
                        }
                        st.session_state.results = results
                    except Exception as e:
                        st.error(f"無法取得 {raw_t} 資料：{e}")
                        continue

            a = analyze_manual_position(df_pos, raw_t, entry, shares, ma_fast, sb_ratio)

            pnl_color  = "#22c55e" if a["pnl_amount"] >= 0 else "#ef4444"
            pnl_sign   = "+" if a["pnl_amount"] >= 0 else ""
            card_class = f"pos-{a['action_level']}"
            wo_warn    = "⚠️ 本週黑吞！" if a["weekly_washout"] else ""
            targets_html = " ｜ ".join([f"<b>{k}</b>" for k in a["targets"].keys()])
            rr_str = f"下一目標 {a['rr_to_next']}R" if a.get("rr_to_next") else "—"   # ← 修正這行
            r_info = f"每股風險 R = {a['R']} 元　｜　現處 {a['current_r']}R" if a.get("R") and a.get("current_r") is not None else ""

            shares_display = f"{shares} 股"
            if shares >= 1000:
                shares_display += f"（{shares/1000:.1f} 張）"

            st.markdown(f"""
<div class="pos-card {card_class}">
  <div class="pos-title">
    {raw_t}
    &nbsp;<span style="font-size:13px;color:{pnl_color};">{pnl_sign}{a['pnl_pct']}%</span>
    &nbsp;<span style="font-size:13px;font-weight:400;color:#6b7280;">
      ({pnl_sign}{a['pnl_amount']:,.0f} 元 ｜ {shares_display})
    </span>
    {"&nbsp;<span style='font-size:12px;background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:8px;'>" + wo_warn + "</span>" if wo_warn else ""}
  </div>
  <div class="pos-sub">{a['action']}</div>
  {"<div style='font-size:12px;color:#7c3aed;margin-top:4px;'>" + r_info + "</div>" if r_info else ""}
  <div class="kv-row">
    <div class="kv-item">
      <div class="kv-label">現價</div><div class="kv-value">{a['close']:.2f}</div>
    </div>
    <div class="kv-item">
      <div class="kv-label">進場成本</div><div class="kv-value">{entry:.2f}</div>
    </div>
    <div class="kv-item" style="border-left:2px solid #ef4444;padding-left:12px;">
      <div class="kv-label">建議停損</div>
      <div class="kv-value" style="color:#ef4444;">{a['recommended_stop']:.2f}</div>
    </div>
    <div class="kv-item">
      <div class="kv-label">停損依據</div>
      <div class="kv-value" style="font-size:12px;color:#6b7280;">{a['stop_basis']}</div>
    </div>
    <div class="kv-item" style="border-left:2px solid #22c55e;padding-left:12px;">
      <div class="kv-label">停利目標（R 倍數）</div>
      <div class="kv-value" style="color:#22c55e;font-size:13px;">{"　".join([f"<b>{k}</b>" for k in a["targets"].keys()])}</div>
    </div>
    <div class="kv-item">
      <div class="kv-label">{rr_str}</div>
      <div class="kv-value">MA{ma_fast} {a['ma10_now'] or '—'}</div>
    </div>
  </div>
  <div style="margin-top:8px;font-size:11px;color:#9ca3af;">
    近5日低 {a['recent_low_5']} ｜ 近10日低 {a['recent_low_10']} ｜ 近20日低 {a['recent_low_20']}
    {f"｜ 極速框底線 {a['sb_param0']}" if a['sb_param0'] else ""}
    {f"｜ 回踩進場訊號：{a['pb_entry_type']}" if a.get('pb_entry') else ""}
    {f"｜ ⚠️ 回踩趨勢破壞" if a.get('pb_dead') else ""}
  </div>
</div>
""", unsafe_allow_html=True)

        # 彙總表
        with st.expander("📊 持倉彙總表", expanded=True):
            summary_rows = []
            for pos in portfolio:
                raw_t  = pos["ticker_raw"]
                df_pos = None
                for suffix in ["", ".TW", ".TWO"]:
                    key = raw_t + suffix if suffix else raw_t
                    if key in results:
                        df_pos = results[key]["df"]
                        break
                if df_pos is None: continue

                a = analyze_manual_position(
                    df_pos, raw_t, pos["entry"], pos["shares"], ma_fast, sb_ratio
                )
                shares = pos["shares"]
                shares_str = f"{shares} 股" + (f"（{shares/1000:.1f}張）" if shares >= 1000 else "")

                summary_rows.append({
                    "代號":     raw_t,
                    "成本/股":  pos["entry"],
                    "現價":     a["close"],
                    "持有股數": shares_str,
                    "損益%":    a["pnl_pct"],
                    "損益金額": a["pnl_amount"],
                    "建議停損": a["recommended_stop"],
                    "停損依據": a["stop_basis"],
                    "主要目標": list(a["targets"].values())[0] if a["targets"] else None,
                    "週黑吞":   "⚠️" if a["weekly_washout"] else "—",
                    "行動":     a["action"],
                })

            if summary_rows:
                df_s = pd.DataFrame(summary_rows)
                def cp(v):
                    if isinstance(v, (int, float)):
                        return "color:#22c55e" if v >= 0 else "color:#ef4444"
                    return ""
                def ca(v):
                    if "停損" in str(v) or "出場" in str(v): return "background:#fee2e2"
                    if "獲利" in str(v) or "停利" in str(v): return "background:#d1fae5"
                    return ""
                st.dataframe(
                    df_s.style.applymap(cp, subset=["損益%","損益金額"])
                               .applymap(ca, subset=["行動"]),
                    use_container_width=True, hide_index=True,
                )


# ══ Tab 3：個股 K 線圖 ═══════════════════════════════════════════════
with tab_chart:
    tickers = list(results.keys())
    if not tickers: st.info("無資料"); st.stop()

    col_sel, col_bars = st.columns([3, 2])
    with col_sel: selected = st.selectbox("選擇標的", tickers)
    with col_bars: display_bars = st.slider("顯示 K 棒數量", 60, 600, 240, 20)

    df_plot = results[selected]["df"]
    summ    = results[selected]["summary"]
    df_show = df_plot.tail(display_bars).copy()

    badge_html = []
    if summ["signal_1012"]:    badge_html.append('<span class="badge badge-green">🟢 1012進場</span>')
    if summ["sb_active"]:      badge_html.append('<span class="badge badge-blue">🔷 極速框確認中</span>')
    if summ["speed_box_ok"]:   badge_html.append('<span class="badge badge-green">⭐ 極速框成立</span>')
    if summ["speed_box_fail"]: badge_html.append('<span class="badge badge-amber">🟠 極速框失效</span>')
    if summ["sb_stop"]:        badge_html.append('<span class="badge badge-red">🔴 底線停損</span>')
    if summ["weekly_sl"]:      badge_html.append('<span class="badge badge-red">🔴 週K停損</span>')
    if summ["weekly_tp"]:      badge_html.append('<span class="badge badge-purple">💰 週K停利</span>')
    if summ["v_reload"]:       badge_html.append('<span class="badge badge-cyan">🔁 V轉Reload</span>')
    if not badge_html and summ["in_position"]:
        badge_html.append('<span class="badge badge-gray">📌 持倉中</span>')
    if not badge_html:
        badge_html.append('<span class="badge badge-gray">— 觀察中</span>')

    line = "　".join(badge_html)
    if summ["entry_price"]: line += f'　<span style="font-size:13px;color:#6b7280;">進場價 {summ["entry_price"]:.2f}</span>'
    if summ["sb_target"]:   line += f'　<span style="font-size:13px;color:#22c55e;">目標 {summ["sb_target"]:.2f}</span>'
    if summ["sb_param0"]:   line += f'　<span style="font-size:13px;color:#ef4444;">底線 {summ["sb_param0"]:.2f}</span>'
    st.markdown(line, unsafe_allow_html=True)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.75, 0.25], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=df_show.index, open=df_show["open"], high=df_show["high"],
        low=df_show["low"], close=df_show["close"], name="K線",
        increasing_line_color="#ef5350", decreasing_line_color="#26a69a",
        increasing_fillcolor="#ef5350",  decreasing_fillcolor="#26a69a",
    ), row=1, col=1)

    maf_col = f"ma{ma_fast}"; mas_col = f"ma{ma_slow}"
    if maf_col in df_show:
        fig.add_trace(go.Scatter(x=df_show.index, y=df_show[maf_col],
            name=f"MA{ma_fast}", mode="lines",
            line=dict(color="#f59e0b", width=1.5)), row=1, col=1)
    if mas_col in df_show:
        fig.add_trace(go.Scatter(x=df_show.index, y=df_show[mas_col],
            name=f"MA{ma_slow}", mode="lines",
            line=dict(color="#f87171", width=1.5)), row=1, col=1)

    def add_markers(col, label, symbol, color, ref_col, offset, tpos):
        mask = df_show.get(col, pd.Series(False, index=df_show.index)) == True
        if mask.any():
            fig.add_trace(go.Scatter(
                x=df_show.index[mask],
                y=df_show.loc[mask, ref_col] * (1 + offset),
                mode="markers+text", name=label,
                marker=dict(symbol=symbol, size=15, color=color,
                            line=dict(color="white", width=1)),
                text=[label]*mask.sum(), textposition=tpos,
                textfont=dict(size=9, color=color),
            ), row=1, col=1)

    add_markers("signal_1012",   "1012進場",  "triangle-up",  "#22c55e", "low",  -0.025, "bottom center")
    add_markers("v_reload",      "V轉",        "triangle-up",  "#06b6d4", "low",  -0.025, "bottom center")
    add_markers("speed_box_ok",  "極速框成立","star",          "#facc15", "high",  0.015, "top center")
    add_markers("speed_box_fail","極速框失效","x-thin-open",  "#f97316", "high",  0.010, "top center")
    add_markers("sb_stop",       "底線停損",  "triangle-down","#ef4444", "low",  -0.025, "bottom center")
    add_markers("weekly_sl",     "週K停損",   "triangle-down","#7c3aed", "low",  -0.015, "bottom center")
    add_markers("weekly_tp",     "週K停利",   "diamond",      "#10b981", "high",  0.015, "top center")
    add_markers("sb_pb_entry",    "回踩進場",  "circle",        "#a855f7", "low",  -0.025, "bottom center")
    add_markers("sb_pb_black_3d", "3D黑吞",    "square-open",   "#6b7280", "high",  0.010, "top center")
    add_markers("sb_pb_dead",     "趨勢破壞",  "x",             "#dc2626", "low",  -0.030, "bottom center")

    sb_dates = df_show[df_show.get("sb_active", False) == True].index
    if len(sb_dates) > 0:
        t  = df_show.loc[sb_dates, "sb_target"].dropna()
        p  = df_show.loc[sb_dates, "sb_param0"].dropna()
        x0, x1 = sb_dates[0], sb_dates[-1]
        if not t.empty:
            tv = t.iloc[-1]
            fig.add_shape(type="line", x0=x0, x1=x1, y0=tv, y1=tv,
                          line=dict(color="#22c55e", dash="dash", width=1.2), row=1, col=1)
            fig.add_annotation(x=x1, y=tv, text=f"目標 {tv:.2f}",
                               font=dict(color="#22c55e", size=10),
                               showarrow=False, xanchor="left", row=1, col=1)
        if not p.empty:
            pv = p.iloc[-1]
            fig.add_shape(type="line", x0=x0, x1=x1, y0=pv, y1=pv,
                          line=dict(color="#ef4444", dash="dash", width=1.2), row=1, col=1)
            fig.add_annotation(x=x1, y=pv, text=f"底線 {pv:.2f}",
                               font=dict(color="#ef4444", size=10),
                               showarrow=False, xanchor="left", row=1, col=1)
    
    # ── TP1 / TP2 / TP3 分批停利線 ───────────────────────────────────
    # 條件：極速框追蹤中 or 極速框已成立（sb_tp1 欄有值即畫）
    tp_series = {
        "sb_tp1": ("TP1 (2.618)", "#facc15", "dash"),    # 黃色
        "sb_tp2": ("TP2 (4.8)",   "#f97316", "dot"),     # 橘色
        "sb_tp3": ("TP3 終極目標","#ef4444", "dashdot"), # 紅色
    }

    for col, (label, color, dash_style) in tp_series.items():
        if col not in df_show.columns:
            continue
        tp_vals = df_show[col].dropna()
        if tp_vals.empty:
            continue

        tp_val  = tp_vals.iloc[-1]
        tp_x0   = tp_vals.index[0]
        tp_x1   = tp_vals.index[-1]

        # 線段（只畫極速框追蹤期間，不延伸到整張圖）
        fig.add_shape(
            type="line",
            x0=tp_x0, x1=tp_x1,
            y0=tp_val, y1=tp_val,
            line=dict(color=color, dash=dash_style, width=1.5),
            row=1, col=1,
        )
        # 右側標籤（xanchor="left" 讓文字不遮擋 K 棒）
        fig.add_annotation(
            x=tp_x1, y=tp_val,
            text=f"{label}  {tp_val:.2f}",
            font=dict(color=color, size=10),
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            row=1, col=1,
        )
        # 若現價已超越該目標，加打勾標記
        current_close = float(df_show["close"].iloc[-1])
        if current_close >= tp_val:
            fig.add_annotation(
                x=tp_x1, y=tp_val,
                text="✅",
                font=dict(size=12),
                showarrow=False,
                xanchor="right",
                yanchor="middle",
                xshift=-4,
                row=1, col=1,
            )
     # ── 3D 階梯支撐壓力線 ────────────────────────────────────────────
    if "Prev_3D_High" in df_show.columns and df_show["Prev_3D_High"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df_show.index,
                y=df_show["Prev_3D_High"],
                mode="lines",
                name="前一3D高點（壓力）",
                line=dict(
                    color="rgba(239, 68, 68, 0.35)",
                    width=1,
                    dash="dash",
                ),
                line_shape="hv",
                showlegend=True,
                hovertemplate="前3D高: %{y:.2f}<extra></extra>",
            ),
            row=1, col=1,
        )

    if "Prev_3D_Low" in df_show.columns and df_show["Prev_3D_Low"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df_show.index,
                y=df_show["Prev_3D_Low"],
                mode="lines",
                name="前一3D低點（支撐）",
                line=dict(
                    color="rgba(34, 197, 94, 0.35)",
                    width=1,
                    dash="dash",
                ),
                line_shape="hv",
                showlegend=True,
                hovertemplate="前3D低: %{y:.2f}<extra></extra>",
            ),
            row=1, col=1,
        )
        
    # 手動持倉成本線
    for pos in st.session_state.portfolio:
        code = pos["ticker_raw"].split(".")[0]
        if code in selected or pos["ticker_raw"] == selected:
            fig.add_hline(
                y=pos["entry"],
                line=dict(color="#8b5cf6", dash="dot", width=1.5),
                annotation_text=f"持倉成本 {pos['entry']:.2f}（{pos['shares']}股）",
                annotation_position="left",
                row=1, col=1,
            )

    vol_colors = ["#ef5350" if c >= o else "#26a69a"
                  for c, o in zip(df_show["close"], df_show["open"])]
    fig.add_trace(go.Bar(x=df_show.index, y=df_show["volume"],
                         name="成交量", marker_color=vol_colors, opacity=0.6), row=2, col=1)

    fig.update_layout(
        height=700, showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0, font=dict(size=11)),
        xaxis_rangeslider_visible=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=80, t=30, b=10), font=dict(size=12),
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(128,128,128,0.12)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(128,128,128,0.12)")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📋 歷史訊號紀錄"):
        sig_cols = ["open","high","low","close", maf_col, mas_col,
                    "signal_1012","speed_box_ok","speed_box_fail",
                    "sb_stop","weekly_sl","weekly_tp","v_reload",
                    "in_position","sb_active","entry_price","sb_param0","sb_target"]
        exist = [c for c in sig_cols if c in df_show.columns]
        trg   = [c for c in ["signal_1012","speed_box_ok","speed_box_fail",
                              "sb_stop","weekly_sl","weekly_tp","v_reload"]
                 if c in df_show.columns]
        df_sig = df_show.loc[df_show[trg].any(axis=1), exist].copy()
        for fc in ["open","high","low","close", maf_col, mas_col,
                   "entry_price","sb_param0","sb_target"]:
            if fc in df_sig: df_sig[fc] = df_sig[fc].round(2)
        if df_sig.empty:
            st.info("此期間內無訊號紀錄。")
        else:
            st.dataframe(df_sig, use_container_width=True)
