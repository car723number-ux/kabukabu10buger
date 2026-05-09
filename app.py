import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collector import generate_sample_data
from strategy import detect_attack_points

st.set_page_config(layout="wide", page_title="Algo-Hunter Pro X10")

st.sidebar.header("📊 Market Selector")
ticker  = st.sidebar.text_input("証券コード", value="7203")
p_map   = {"3ヶ月": "3mo", "1年": "1y", "5年": "5y"}
sel_p   = st.sidebar.selectbox("期間", list(p_map.keys()), index=1)

raw_df = generate_sample_data(ticker, period=p_map[sel_p])

if raw_df is not None and not raw_df.empty:
    df, poc_info, reasons = detect_attack_points(raw_df)

    st.title(f"CODE: {ticker}")

    # ----------------------------------------------------------
    # チャート描画
    # ----------------------------------------------------------
    fig = make_subplots(
        rows=3, cols=2,
        shared_xaxes=True,
        row_heights=[0.7, 0.15, 0.15],
        column_widths=[0.85, 0.15],
        vertical_spacing=0.03,
        horizontal_spacing=0.01,
        specs=[
            [{"secondary_y": True},  {"rowspan": 1}],
            [{"secondary_y": False}, {"rowspan": 1}],
            [{"secondary_y": False}, {"rowspan": 1}],
        ],
    )

    # 背景：出来高
    v_colors = [
        'rgba(255, 82, 82, 0.15)' if df['Close'].iloc[i] >= df['Open'].iloc[i]
        else 'rgba(33, 150, 243, 0.15)'
        for i in range(len(df))
    ]
    fig.add_trace(
        go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors, showlegend=False),
        row=1, col=1, secondary_y=True,
    )

    # フィボナッチ
    for label, val in poc_info["fib"].items():
        fig.add_trace(
            go.Scatter(
                x=[df.index[0], df.index[-1]], y=[val, val],
                mode="lines+text", text=[label], textposition="top right",
                line=dict(color="rgba(200,200,200,0.2)", dash="dot"), showlegend=False,
            ),
            row=1, col=1,
        )

    # ローソク足
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="Price",
        ),
        row=1, col=1, secondary_y=False,
    )

    # VWAP / POC
    fig.add_trace(
        go.Scatter(x=df.index, y=df["VWAP_ALL"],
                   line=dict(color="cyan", width=1), name="VWAP"),
        row=1, col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[df.index[0], df.index[-1]],
            y=[poc_info["poc_long"], poc_info["poc_long"]],
            line=dict(color="orange", dash="dash"), name="POC",
        ),
        row=1, col=1,
    )

    # ---- 心理的ライン（キリ番）----
    for pl in poc_info["psych_lines"]:
        fig.add_trace(
            go.Scatter(
                x=[df.index[0], df.index[-1]], y=[pl, pl],
                mode="lines",
                line=dict(color="rgba(255,255,0,0.18)", dash="dot", width=1),
                showlegend=False, name=f"psych {pl}",
            ),
            row=1, col=1,
        )

    # ---- 損切りゾーン（買い勢 / 売り勢）----
    sz_low  = poc_info["stop_zone_low"]
    sz_high = poc_info["stop_zone_high"]
    fig.add_hrect(
        y0=sz_low[0],  y1=sz_low[1],
        fillcolor="rgba(0,200,100,0.08)", line_width=0,
        annotation_text="買い損切ゾーン", annotation_position="top left",
        row=1, col=1,
    )
    fig.add_hrect(
        y0=sz_high[0], y1=sz_high[1],
        fillcolor="rgba(255,50,50,0.08)", line_width=0,
        annotation_text="売り損切ゾーン", annotation_position="top left",
        row=1, col=1,
    )

    # ---- 塩漬けゾーン ----
    ti = poc_info["trapped_info"]
    fig.add_hrect(
        y0=ti["zone_bottom"], y1=ti["zone_top"],
        fillcolor="rgba(255,165,0,0.06)", line_width=0,
        annotation_text="塩漬けゾーン", annotation_position="top right",
        row=1, col=1,
    )

    # ---- Stop Hunt フラグ ----
    for flag in poc_info["hunt_flags"]:
        color  = "lime"   if flag["type"] == "bullish_hunt" else "red"
        symbol = "triangle-up" if flag["type"] == "bullish_hunt" else "triangle-down"
        fig.add_trace(
            go.Scatter(
                x=[flag["index"]], y=[flag["price"]],
                mode="markers",
                marker=dict(symbol=symbol, size=10, color=color, opacity=0.85),
                showlegend=False, name="Stop Hunt",
            ),
            row=1, col=1,
        )

    # 右側：価格帯別出来高
    fig.add_trace(
        go.Histogram(
            y=df["Close"], nbinsy=40, orientation='h',
            marker_color="rgba(100,100,100,0.3)",
        ),
        row=1, col=2,
    )

    # MACD / RSI
    fig.add_trace(
        go.Bar(x=df.index, y=df["MACD"] - df["Signal"],
               marker_color="gray", name="MACD"),
        row=2, col=1,
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df["RSI"],
                   line=dict(color="gold"), name="RSI"),
        row=3, col=1,
    )

    fig.update_yaxes(
        range=[0, df['Volume'].max() * 5],
        showticklabels=False, secondary_y=True, row=1, col=1,
    )
    fig.update_layout(
        template="plotly_dark", height=900,
        xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------------
    # 分析パネル
    # ----------------------------------------------------------
    st.markdown("---")

    tab1, tab2 = st.tabs(["🕵️ 基本10項目診断", "🎯 Stop Hunt 戦略診断"])

    with tab1:
        st.subheader(f"10項目・多角的戦略診断 (Score: {poc_info['score']}/100)")
        col1, col2 = st.columns([2, 1])
        with col1:
            if poc_info['score'] >= 80:
                st.success("🚀 非常に強力な買いシグナルが点灯中です")
            elif poc_info['score'] >= 50:
                st.info("📈 緩やかな上昇傾向ですが、慎重さも必要です")
            else:
                st.warning("⚠️ 弱気相場または調整局面。エントリーは待機を推奨")
            for txt in reasons[:10]:
                st.write(txt)
        with col2:
            st.metric("Total Score", f"{poc_info['score']} / 100")
            st.progress(poc_info['score'] / 100)
            st.write("※各項目10点満点で算出")

    with tab2:
        sh = poc_info['sh_score']
        st.subheader(f"🎯 Stop Hunt 戦略スコア: {sh} pt")
        col3, col4 = st.columns([2, 1])
        with col3:
            if sh >= 35:
                st.success("🔥 強力なストップハント後の反発エントリー機会です")
            elif sh >= 20:
                st.info("⚡ ストップハントの兆候あり。確認足を待ってエントリー検討")
            else:
                st.warning("👀 現時点ではストップハントシグナルは弱い。待機推奨")

            for txt in poc_info['sh_reasons']:
                st.write(txt)

            # ---- 損切りライン詳細テーブル ----
            st.markdown("#### 📌 損切りゾーン詳細")
            ti = poc_info['trapped_info']
            data = {
                "項目": [
                    "買い勢の損切りゾーン（下）",
                    "売り勢の損切りゾーン（上）",
                    "塩漬けゾーン下限",
                    "塩漬けゾーン上限（直近高値）",
                    "塩漬け出来高比率",
                    "ATR（ノイズバッファ）",
                ],
                "値": [
                    f"{poc_info['stop_zone_low'][0]:.0f} 〜 {poc_info['stop_zone_low'][1]:.0f} 円",
                    f"{poc_info['stop_zone_high'][0]:.0f} 〜 {poc_info['stop_zone_high'][1]:.0f} 円",
                    f"{ti['zone_bottom']:.0f} 円",
                    f"{ti['zone_top']:.0f} 円",
                    f"{ti['pct_of_total']*100:.1f} %",
                    f"{poc_info['atr_now']:.1f} 円",
                ],
            }
            import pandas as pd
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

            # ---- 心理的ライン一覧 ----
            st.markdown("#### 🔢 心理的ライン（キリ番）一覧")
            c_now = float(df["Close"].iloc[-1])
            for pl in poc_info['psych_lines']:
                dist = (pl - c_now) / c_now * 100
                marker = "◀ 現在値" if abs(dist) < 0.5 else ""
                st.write(f"  {pl:,.0f} 円  ({dist:+.2f}%)  {marker}")

            # ---- 検出したストップハントフラグ ----
            if poc_info['hunt_flags']:
                st.markdown("#### 🚩 検出されたStop Huntイベント")
                for f in poc_info['hunt_flags']:
                    kind = "⬆️ 買い（下ヒゲ狩り）" if f['type'] == "bullish_hunt" else "⬇️ 売り（上ヒゲ狩り）"
                    st.write(f"  {f['index'].date()}  |  {kind}  |  価格: {f['price']:.0f} 円")

        with col4:
            st.metric("Stop Hunt Score", f"{sh} pt")
            st.progress(min(sh / 50, 1.0))
            st.write("※最大50pt")
            st.markdown("---")
            st.metric("基本スコア", f"{poc_info['score']} / 100")
            combined = poc_info['score'] + sh
            st.metric("総合スコア", f"{combined} pt", delta=f"+{sh} pt (SH)")

else:
    st.error("データ取得エラー。コードを確認してください。")
