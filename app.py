import streamlit as st

# ページの基本設定
st.set_page_config(
    page_title="恋のオラクル AI星譚",
    page_icon="🌙",
    layout="centered", # 中央揃えレイアウト
)

# タイトルを表示
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")

st.write("---") # 区切り線
st.write("ようこそ、星々の導きへ。")
# 本来はGitHub上のファイルから読み込みますが、最初はここに直接書きます
# このリストにあるIDだけがログインできます
VALID_USER_IDS = ["test_user_01", "charo_special_id", "buyer_id_123"]

# 認証状態を保存する場所を準備
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 認証フォームを表示
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")

# まだ認証されていない場合に、ID入力欄を表示
if not st.session_state.authenticated:
    user_id = st.text_input("BOOTHの購入者IDを入力してください", type="default")
    
    if st.button("認証する"):
        if user_id in VALID_USER_IDS:
            st.session_state.authenticated = True
            st.rerun() # ページを再読み込みしてメイン画面へ
        else:
            st.error("認証に失敗しました。正しいIDを入力してください。")

# --- 認証が成功した場合に、ここから下のメインコンテンツを表示 ---

if st.session_state.authenticated:
    st.success("認証に成功しました！ ようこそ！")
    
    # ここからが鑑定アプリの本体になります（今はまだ仮の内容）
    st.header("鑑定を開始します")
    st.write("ここに、キャラクター選択やファイルアップロードの機能が入ります。")
