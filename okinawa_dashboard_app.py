import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sqlite3

# --- DB接続 ---
conn = sqlite3.connect("properties.db")

st.set_page_config(page_title="沖縄物件ダッシュボード", layout="wide")
st.title("🏠 沖縄・浦添市 物件ダッシュボード")

# --- データ読み込み ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv("report_{}.csv".format(datetime.now().strftime("%Y%m%d")))
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["size"] = pd.to_numeric(df["size"], errors="coerce")
        df = df.dropna(subset=["price", "size"])
        return df
    except FileNotFoundError:
        st.error("CSVファイルが見つかりません。先にスクリプトを実行してください。")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.stop()

if "type" not in df.columns:
    df["type"] = "不明"

@st.cache_data
def load_price_history():
    try:
        conn = sqlite3.connect("properties.db")
        df = pd.read_sql_query("SELECT url, date, price FROM price_history ORDER BY date ASC", conn)
        df["date"] = pd.to_datetime(df["date"])
        return df
    except Exception as e:
        st.error(f"価格履歴の読み込み中にエラーが発生しました: {e}")
        return pd.DataFrame()

# --- デバッグモード切替 ---
debug_mode = st.sidebar.checkbox("🛠 デバッグ表示を有効にする")

# --- サイドバー：フィルター ---
st.sidebar.header("🔎 フィルター")

type_filter = st.sidebar.multiselect(
    "物件種別",
    options=df["type"].unique(),
    default=list(df["type"].unique())
)

# float精度を確保しつつ、ステップサイズを調整
size_range = st.sidebar.slider(
    "面積 (㎡)",
    min_value=float(df["size"].min()),
    max_value=float(df["size"].max()),
    value=(float(df["size"].min()), float(df["size"].max())),
    step=0.1
)

price_range = st.sidebar.slider(
    "価格 (万円)",
    min_value=float(df["price"].min()),
    max_value=float(df["price"].max()),
    value=(float(df["price"].min()), float(df["price"].max())),
    step=10.0
)
# --- フィルタリング ---
filtered = df[
    (df["type"].isin(type_filter)) &
    (df["size"] >= size_range[0]) &
    (df["size"] <= size_range[1]) &
    (df["price"] >= price_range[0]) &
    (df["price"] <= price_range[1])
]

# --- デバッグモードを利用したステータス出力 ---
if debug_mode:
    st.subheader("🛠 デバッグ情報")
    st.write("🔎 フィルター条件との比較:\n")
    for _, row in filtered.iterrows():
        st.write(f"\nタイプ: {row['type']} 面積:{row['size']} 価格:{row['price']}")
    st.write("タイプフィルター:", type_filter)
    st.write("サイズ範囲:", size_range)
    st.write("価格帯:", price_range)

# --- デバッグモードを利用したステータス出力 ---
if debug_mode:
    st.subheader("🛠 デバッグ情報")
    
    # フィルター条件との比較出力
    st.write("🔎 フィルター条件との比較:")
    for _, row in df.iterrows():
        if row["url"] not in filtered["url"].values:
            st.write(f"❌ 非表示物件: {row['url']}")
            st.write(f"タイプ: {row['type']}, 面積: {row['size']}, 価格: {row['price']}")
            st.write(f"→ フィルター条件: type={type_filter}, 面積={size_range}, 価格={price_range}")
    
    # 特定物件の表示確認
    st.markdown("### 🐛 デバッグ用 - 特定物件の表示確認")
    target_url = "https://www.e-uchina.net/bukken/house/h-5465-7230920-0323/detail.html"
    target_df = df[df["url"] == target_url]
    if target_df.empty:
        st.warning("対象物件はデータに存在しません")
    else:
        st.write(target_df)

    # --- デバッグ：フィルタ無視の全件表示 ---
    st.markdown("### 🧪 全物件（フィルタ無視・確認用）")
    df["url_link"] = df["url"].apply(lambda x: f'<a href="{x}" target="_blank">リンク</a>')
    st.write(
        df[["type", "price", "size", "location", "building_name", "madori", "chikunensu", "url_link"]]
        .sort_values("price")
        .rename(columns={
            "type": "種別", "price": "価格(万円)", "size": "面積(㎡)",
            "location": "住所", "building_name": "建物名", "madori": "間取り",
            "chikunensu": "築年数", "url_link": "リンク"
        }).to_html(escape=False, index=False),
        unsafe_allow_html=True
    )

# --- 表示 ---
st.markdown("### 📊 該当物件数: {} 件".format(len(filtered)))

# URLをHTMLリンクに変換
filtered["url_link"] = filtered["url"].apply(lambda x: f'<a href="{x}" target="_blank">リンク</a>')

# HTMLで表示（リンク付き）
st.markdown("### 📊 該当物件一覧（リンク付き）", unsafe_allow_html=True)
st.write(
    filtered[["type", "price", "size", "location", "building_name", "madori", "chikunensu", "url_link"]]
    .sort_values("price")
    .rename(columns={
        "type": "種別", "price": "価格(万円)", "size": "面積(㎡)",
        "location": "住所", "building_name": "建物名", "madori": "間取り",
        "chikunensu": "築年数", "url_link": "リンク"
    }).to_html(escape=False, index=False),
    unsafe_allow_html=True
)

# --- グラフ ---
st.subheader("💹 価格分布（500万円刻み）")
bins = list(range(int(df["price"].min() // 500 * 500), int(df["price"].max() + 500), 500))
fig = px.histogram(filtered, x="price", nbins=len(bins), title="価格ヒストグラム", labels={"price": "価格（万円）"})
fig.update_layout(bargap=0.1)
st.plotly_chart(fig, use_container_width=True)

st.subheader("🏗 面積 vs 価格")
color_map = {"mansion": "#1f77b4", "house": "#d62728"}  # blue / red
fig2 = px.scatter(
    filtered, x="size", y="price", color="type",
    color_discrete_map=color_map,
    hover_data=["location", "building_name"],
    labels={"size": "面積（㎡）", "price": "価格（万円）"}
)

st.plotly_chart(fig2, use_container_width=True)

# --- 新規追加物件 ---
st.subheader("🆕 今日追加された物件")
df_new = df[df["first_seen"] == datetime.now().strftime("%Y-%m-%d")]
if not df_new.empty:
    df_new["url_link"] = df_new["url"].apply(lambda x: f'<a href="{x}" target="_blank">リンク</a>')
    st.write(
        df_new[["type", "price", "size", "location", "building_name", "madori", "chikunensu", "url_link"]]
        .sort_values("price")
        .rename(columns={
            "type": "種別", "price": "価格(万円)", "size": "面積(㎡)",
            "location": "住所", "building_name": "建物名", "madori": "間取り",
            "chikunensu": "築年数", "url_link": "リンク"
        }).to_html(escape=False, index=False),
        unsafe_allow_html=True
    )
else:
    st.info("本日新しく追加された物件はありません。")

# --- 削除された物件一覧 ---
st.subheader("🗑 過去に削除された物件一覧")
df_deleted = pd.read_sql_query(
    "SELECT title, price, size, location, building_name, madori, chikunensu, last_seen, url FROM properties WHERE is_active = 0",
    conn
)
if not df_deleted.empty:
    st.dataframe(
        df_deleted[["price", "size", "location", "building_name", "madori", "chikunensu", "last_seen", "url"]]
        .sort_values("last_seen", ascending=False)
        .rename(columns={
            "price": "価格(万円)", "size": "面積(㎡)", "location": "住所", "building_name": "建物名",
            "madori": "間取り", "chikunensu": "築年数", "last_seen": "最終確認日", "url": "リンク"
        }),
        use_container_width=True
    )
else:
    st.info("現在、削除された物件はありません。")


st.subheader("📈 物件別 価格履歴グラフ")
history_df = load_price_history()
available_urls = history_df["url"].unique()

url_to_label = {
    row["url"]: f"{row['location']} / {row['size']}㎡ / {row['chikunensu']} / {row.get('building_name', '')}"
    for _, row in df.iterrows()
}
label_to_url = {v: k for k, v in url_to_label.items()}
selected_label = st.selectbox("物件を選択してください", options=list(label_to_url.keys()))
selected_url = label_to_url[selected_label]


if selected_url:
    selected_df = history_df[history_df["url"] == selected_url]
    fig3 = px.line(selected_df, x="date", y="price", title="価格推移（万円）", markers=True)
    fig3.update_layout(xaxis=dict(dtick="D1"))  # 横軸を1日単位に
    fig3.update_layout(xaxis_title="日付", yaxis_title="価格（万円）")
    st.plotly_chart(fig3, use_container_width=True)
    
