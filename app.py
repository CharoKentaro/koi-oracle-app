import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
import time

# --- ページの基本設定 ---
st.set_page_config(
    page_title="恋のオラクル AI星譚",
    page_icon="🌙",
    layout="centered",
)

# --- クッキーマネージャーの準備 ---
cookies = EncryptedCookieManager(
    password="my_super_secret_password_12345",
)
if not cookies.ready():
    st.stop()

# --- 状態管理フラグ ---
# st.session_stateに値がなければ初期化
if "authenticated" not in st.session_state:
    st.session_state.authenticated = cookies.get("authenticated", False)
if "api_key" not in st.session_state:
    st.session_state.api_key = cookies.get("api_key", None)

# クッキーに書き込むべきデータを一時的に保持するフラグ
if "cookie_update_needed" not in st.session_state:
    st.session_state.cookie_update_needed = False
if "logout_in_progress" not in st.session_state:
    st.session_state.logout_in_progress = False

# ---------------------------------------------------------------------
# 画面描画関数
# ---------------------------------------------------------------------

def show_login_screen():
    """ログイン画面を表示する関数"""
    st.header("ようこそ、鑑定の世界へ")
    user_id = st.text_input("BOOTHの購入者IDを入力してください", key="login_user_id")

    if st.button("認証する", key="login_button"):
        VALID_USER_IDS = ["test_user_01", "charo_special_id", "buyer_id_123"]
        if user_id in VALID_USER_IDS:
            st.session_state.authenticated = True
            st.session_state.cookie_update_needed = True # クッキー更新フラグを立てる
            st.rerun()
        else:
            st.error("認証に失敗しました。正しいIDを入力してください。")


def show_api_key_screen():
    """APIキー設定画面を表示する関数"""
    st.success("認証に成功しました！")
    st.header("🔮 AI鑑定師との接続設定")
    st.info("鑑定を始める前に、一度だけAIとの接続設定をお願いします。この設定は、お使いのブラウザに保存され、次回からは不要になります。")

    api_key_possessed = st.radio(
        "Gemini APIキーはお持ちですか？",
        ("持っています", "持っていません / 取得方法がわかりません"),
        horizontal=True, index=1, key="api_radio"
    )

    if api_key_possessed == "持っています":
        api_key_input = st.text_input("Gemini APIキーをここに貼り付けてください", type="password", key="api_input")
        if st.button("APIキーを設定・保存する", key="api_save_button"):
            if api_key_input:
                st.session_state.api_key = api_key_input
                st.session_state.cookie_update_needed = True # クッキー更新フラグを立てる
                st.rerun()
            else:
                st.warning("APIキーを入力してください。")
    else:
        with st.expander("図解付き：APIキーの取得方法を見る"):
            st.write("### ステップ1: Google AI Studioにアクセス")
            st.link_button("Google AI Studioを開く", "https://aistudio.google.com/")
            st.write("### ステップ2: APIキーを作成する")
            st.image("https://i.imgur.com/3i2z622.png", caption="左側のメニューから `Get API key` をクリックします。")
            st.image("https://i.imgur.com/w2m5f2e.png", caption="次に、`Create API key` という青いボタンをクリックします。")
            st.write("### ステップ3: APIキーをコピーする")
            st.image("https://i.imgur.com/6a2gG4a.png", caption="表示された文字列があなたのAPIキーです。コピーボタンを押して、上の入力欄に貼り付けてください。")
            st.warning("このキーは他人に教えないように大切に保管してくださいね。")


def show_main_app():
    """メインの鑑定アプリ画面を表示する関数"""
    st.success("AI鑑定師との接続が完了しました！")
    st.header("鑑定の準備が整いました")
    st.write("ここに、キャラクター選択やファイルアップロードの機能を作っていきましょう！")

    if st.button("設定をリセット（ログアウト）", key="logout_button"):
        st.session_state.logout_in_progress = True # ログアウトフラグを立てる
        st.rerun()

# ---------------------------------------------------------------------
# メインの実行ロジック
# ---------------------------------------------------------------------

# 共通のヘッダー
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")

# 状態に応じて表示する画面を切り替える
if not st.session_state.authenticated:
    show_login_screen()
elif not st.session_state.api_key:
    show_api_key_screen()
else:
    show_main_app()

# ---------------------------------------------------------------------
# ★★★ ここが重要！スクリプトの最後にクッキー操作をまとめる ★★★
# ---------------------------------------------------------------------

if st.session_state.cookie_update_needed:
    # 認証情報とAPIキーの両方を、現在のsession_stateの内容で上書き保存
    cookies.set("authenticated", st.session_state.authenticated)
    cookies.set("api_key", st.session_state.api_key)
    st.session_state.cookie_update_needed = False # フラグをリセット

if st.session_state.logout_in_progress:
    cookies.delete("authenticated")
    cookies.delete("api_key")
    # セッション状態もクリア
    st.session_state.authenticated = False
    st.session_state.api_key = None
    st.session_state.logout_in_progress = False # フラグをリセット
    # ログアウトメッセージは不要なら消してもOK
    st.info("ログアウトしました。ページを更新してください。")
    time.sleep(1)
    st.rerun()
