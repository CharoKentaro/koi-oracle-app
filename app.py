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
            st.session_state.cookie_update_needed = True
            st.rerun()
        else:
            st.error("認証に失敗しました。正しいIDを入力してください。")


def show_api_key_screen():
    """APIキー設定画面を表示する関数"""
    st.success("認証に成功しました！")
    st.header("🔮 AI鑑定師との接続設定")
    # (この関数の中身は変更なし)
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
                st.session_state.cookie_update_needed = True
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
    
    # --- ここからがパーソナライズ設定 ---
    st.header("Step 1: 鑑定の準備")
    
    # 鑑定師キャラクター選択
    character = st.selectbox(
        "🔮 どの鑑定師に占ってもらいますか？",
        ("優しく包み込む、お姉さん系", "ロジカルに鋭く分析する、専門家系", "星の言葉で語る、ミステリアスな占い師系"),
        key="character_select"
    )

    # 鑑定スタイルの微調整（トーン選択）
    tone = st.select_slider(
        "🗣️ どんな雰囲気で伝えてほしいですか？",
        options=["癒し 100%", "癒し 50% × 論理 50%", "冷静にロジカル"],
        value="癒し 50% × 論理 50%", # デフォルト値
        key="tone_select"
    )

    # ミニカウンセリング
    your_name = st.text_input("💬 あなたのLINEでの名前を教えてください", key="your_name")
    partner_name = st.text_input("💬 お相手のLINEでの名前を教えてください", key="partner_name")
    counseling_text = st.text_area(
        "💬 今回、お相手との関係で、特にどんなことが気になりますか？",
        placeholder="例：最近返信が遅い、デートに誘いたい、など",
        key="counseling_input"
    )

    st.write("---")
    
    # --- ここからがファイルアップロードと鑑定実行 ---
    st.header("Step 2: トーク履歴をアップロード")
    
    uploaded_file = st.file_uploader(
        "LINEのトーク履歴ファイル（.txt）をここにアップロードしてください。",
        type="txt",
        key="file_uploader"
    )
    st.info("どんなに長いトーク履歴でも大丈夫。AIが自動で大切な部分だけを読み取って分析しますので、そのままアップロードしてくださいね。")

    if uploaded_file is not None:
        # ここにミニ分析プレビューの処理が入る（次のステップで実装！）
        st.write("ファイルを受け付けました！")
        
        if st.button("鑑定を開始する", type="primary", key="start_analysis_button"):
            # ここに本格的なAI分析の処理が入る（さらに次のステップで！）
            st.write(f"キャラクター: {character}")
            st.write(f"トーン: {tone}")
            st.write(f"あなたの名前: {your_name}")
            st.write(f"相手の名前: {partner_name}")
            st.write(f"相談内容: {counseling_text}")
            st.write("---")
            st.balloons()
            st.success("鑑定を開始します！(現在はまだ開発中です)")
            
    # ログアウト機能
    with st.expander("設定"):
        if st.button("設定をリセット（ログアウト）", key="logout_button"):
            st.session_state.logout_in_progress = True
            st.rerun()

# ---------------------------------------------------------------------
# メインの実行ロジック
# ---------------------------------------------------------------------

# 共通のヘッダー
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅盤 Edition -")
st.write("---")

# 状態に応じて表示する画面を切り替える
if not st.session_state.authenticated:
    show_login_screen()
elif not st.session_state.api_key:
    show_api_key_screen()
else:
    show_main_app()

# ---------------------------------------------------------------------
# スクリプトの最後にクッキー操作をまとめる
# ---------------------------------------------------------------------

if st.session_state.cookie_update_needed:
    cookies.set("authenticated", st.session_state.authenticated)
    cookies.set("api_key", st.session_state.api_key)
    st.session_state.cookie_update_needed = False

if st.session_state.logout_in_progress:
    cookies.delete("authenticated")
    cookies.delete("api_key")
    st.session_state.authenticated = False
    st.session_state.api_key = None
    st.session_state.logout_in_progress = False
    time.sleep(0.5)
    st.rerun()
