"""
企業財務診断ダッシュボード Pro
機能: 個別分析 / 複数銘柄比較 / 業界平均比較 / AIコメント（ルールベース拡張版） / スクリーニング
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
import pandas as pd
import numpy as np
import time

# =============================================
# ページ設定
# =============================================
st.set_page_config(layout="wide", page_title="企業財務診断ダッシュボード Pro", page_icon="📊")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .section-header {
        font-size: 1.05rem; font-weight: 700; letter-spacing: 0.08em;
        color: #58a6ff; border-left: 3px solid #58a6ff;
        padding-left: 10px; margin: 24px 0 12px 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #161b22 0%, #1c2230 100%);
        border: 1px solid #30363d; border-radius: 12px;
        padding: 14px 16px; text-align: center;
    }
    .metric-label { font-size: 0.68rem; color: #8b949e; letter-spacing: 0.1em; text-transform: uppercase; }
    .metric-value { font-size: 1.35rem; font-weight: 700; color: #e6edf3; }
    .metric-sub   { font-size: 0.72rem; color: #8b949e; margin-top: 2px; }
    .ai-box {
        background: linear-gradient(135deg, #0d1f12 0%, #0d1525 100%);
        border: 1px solid #238636; border-radius: 12px;
        padding: 20px 24px; margin-top: 8px; line-height: 1.9;
        font-size: 0.92rem; color: #c9d1d9;
    }
    .biz-summary {
        background-color: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 15px; margin-bottom: 15px;
        font-size: 0.85rem; color: #8b949e;
    }
    .stButton > button {
        background: linear-gradient(135deg, #238636, #2ea043);
        color: white; border: none; border-radius: 8px;
        padding: 8px 20px; font-weight: 700; width: 100%;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #2ea043, #3fb950); }
</style>
""", unsafe_allow_html=True)

# =============================================
# 定数
# =============================================
PLOTLY_LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(22,27,34,0.8)',
    font=dict(family='Noto Sans JP', color='#c9d1d9', size=12),
    margin=dict(t=50, b=40, l=50, r=30),
    legend=dict(bgcolor='rgba(22,27,34,0.8)', bordercolor='#30363d', borderwidth=1, font=dict(size=11))
)
C = dict(
    blue='#58a6ff', green='#3fb950', orange='#f78166', yellow='#e3b341',
    purple='#bc8cff', teal='#39d353', red='#f85149', grid='#21262d', axis='#30363d',
)
PALETTE = [C['blue'], C['green'], C['yellow'], C['purple'], C['orange'], C['teal']]

INDUSTRY_GROUPS = {
    "自動車":   ["7203", "7267", "7269", "7270", "7201", "7202"],
    "電機・精密": ["6758", "6752", "6971", "6954", "7751", "6501"],
    "商社":     ["8058", "8053", "8001",
