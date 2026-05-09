import os
import subprocess
import sys

# =================================================================
# 1. 必要なライブラリの自動チェック・インストール
# =================================================================
def manage_libraries():
    required = ["streamlit", "networkx", "pyvis"]
    for lib in required:
        try:
            __import__(lib)
        except ImportError:
            print(f"ライブラリ '{lib}' をインストール中...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

manage_libraries()

import numpy as np
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

# =================================================================
# 2. 設定
# =================================================================
MODEL_PATH = 'jawiki.word_vectors.300d.txt'
BRANCH_COUNTS = [5, 3, 1]

# =================================================================
# 3. word2vecテキスト形式を直接読み込む（起動時に1回だけ）
# =================================================================
@st.cache_resource(show_spinner="単語ベクトルを読み込んでいます（初回のみ1〜3分かかります）...")
def load_word_vectors(path):
    words = []
    vectors = []

    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        first_line = f.readline().strip().split()

        if len(first_line) == 2 and first_line[0].isdigit():
            pass
        else:
            word = first_line[0]
            vec = np.array(first_line[1:], dtype=np.float32)
            if len(vec) > 0:
                words.append(word)
                vectors.append(vec)

        for line in f:
            parts = line.rstrip().split(' ')
            if len(parts) < 2:
                continue
            word = parts[0]
            try:
                vec = np.array(parts[1:], dtype=np.float32)
                words.append(word)
                vectors.append(vec)
            except ValueError:
                continue

    vectors = np.array(vectors, dtype=np.float32)
    word2idx = {w: i for i, w in enumerate(words)}
    return words, vectors, word2idx


def most_similar(word, words, vectors, word2idx, topn=10):
    if word not in word2idx:
        raise KeyError(f"'{word}' は語彙にありません")

    idx = word2idx[word]
    vec = vectors[idx]

    norms = np.linalg.norm(vectors, axis=1)
    norms[norms == 0] = 1e-10
    vec_norm = np.linalg.norm(vec)
    if vec_norm == 0:
        vec_norm = 1e-10

    sims = (vectors @ vec) / (norms * vec_norm)
    sims[idx] = -1

    top_indices = np.argpartition(sims, -topn)[-topn:]
    top_indices = top_indices[np.argsort(sims[top_indices])[::-1]]

    return [(words[i], float(sims[i])) for i in top_indices]


def build_network_html(start_word, words, vectors, word2idx, branch_counts):
    G = nx.Graph()
    queue = [(start_word, 0)]
    G.add_node(start_word, size=45, title="起点", color="#FF4500", label=start_word)
    visited = {start_word}

    while queue:
        current_word, depth = queue.pop(0)
        if depth >= len(branch_counts):
            continue

        try:
            n_branch = branch_counts[depth]
            similar_words = most_similar(current_word, words, vectors, word2idx, topn=n_branch + 5)

            count = 0
            for word, score in similar_words:
                if count >= n_branch:
                    break
                if "[" in word or "Category:" in word or word in visited or len(word) < 2:
                    continue

                node_colors = ["#FFD700", "#87CEEB", "#32CD32"]
                node_sizes = [35, 25, 15]

                G.add_node(word, size=node_sizes[depth], color=node_colors[depth],
                           title=f"関連度: {score:.3f}", label=word)
                G.add_edge(current_word, word, value=score)

                visited.add(word)
                queue.append((word, depth + 1))
                count += 1
        except KeyError:
            continue

    net = Network(height="750px", width="100%", bgcolor="#1a1a1a", font_color="white")
    net.from_nx(G)
    net.toggle_physics(True)

    html_path = "investment_map.html"
    net.write_html(html_path)
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()


# =================================================================
# 4. Streamlit UI
# =================================================================
st.set_page_config(page_title="連想マップ", layout="wide")
st.title("📈 連想ワードマップ")

if not os.path.exists(MODEL_PATH):
    st.error(f"「{MODEL_PATH}」が見つかりません。このスクリプトと同じフォルダに置いてください。")
    st.stop()

words, vectors, word2idx = load_word_vectors(MODEL_PATH)

with st.sidebar:
    st.header("⚙️ 設定")
    start_word = st.text_input("起点ワード", value="半導体", placeholder="例：AI、銀行、自動車")

    st.markdown("---")
    st.markdown("**階層ごとの表示数**")
    b1 = st.slider("1階層目", 1, 10, 5)
    b2 = st.slider("2階層目", 1, 10, 3)
    b3 = st.slider("3階層目", 1,  5, 1)

    run = st.button("🔍 マップを生成", use_container_width=True)

if run:
    if not start_word.strip():
        st.warning("起点ワードを入力してください。")
    elif start_word.strip() not in word2idx:
        st.error(f"「{start_word}」は語彙にありません。別のワードを試してください。")
    else:
        with st.spinner(f"「{start_word}」のネットワークを構築中..."):
            html = build_network_html(start_word.strip(), words, vectors, word2idx, [b1, b2, b3])
        st.success("完成！")
        components.html(html, height=770, scrolling=False)
else:
    st.info("左のサイドバーに起点ワードを入力して「マップを生成」を押してください。")
