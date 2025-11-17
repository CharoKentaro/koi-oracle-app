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
    prefix="oracle_app/",
    password="my_super_secret_password_12345",
)

if not cookies.ready():
    st.stop()

# --- 初期化: Cookieからセッション状態へロード ---
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    # Cookieから値を読み込み
    st.session_state.authenticated = cookies.get("authenticated") == "True"
    st.session_state.api_key = cookies.get("api_key")
    if st.session_state.api_key == "None":
        st.session_state.api_key = None

# --- 定数 ---
VALID_USER_IDS = ["test_user_01", "charo_special_id", "buyer_id_123"]

# ---------------------------------------------------------------------
# 画面描画関数
# ---------------------------------------------------------------------

def show_login_screen():
    """ログイン画面を表示する関数"""
    st.header("🌙 ようこそ、鑑定の世界へ")
    st.write("BOOTHでご購入いただき、ありがとうございます。")
    
    user_id = st.text_input("BOOTHの購入者IDを入力してください", key="login_user_id")

    if st.button("認証する", key="login_button"):
        if user_id in VALID_USER_IDS:
            # 認証成功
            st.session_state.authenticated = True
            cookies["authenticated"] = "True"
            cookies.save()
            st.success("認証に成功しました！")
            time.sleep(1)
            st.rerun()
        else:
            st.error("❌ 認証に失敗しました。正しいIDを入力してください。")


def show_api_key_screen():
    """APIキー設定画面を表示する関数"""
    st.success("✅ 認証に成功しました！")
    st.header("🔮 AI鑑定師との接続設定")
    st.info("鑑定を始める前に、一度だけAIとの接続設定をお願いします。この設定は、お使いのブラウザに保存され、次回からは不要になります。")

    api_key_possessed = st.radio(
        "**Gemini APIキーはお持ちですか？**",
        ("持っています", "持っていません / 取得方法がわかりません"),
        horizontal=True,
        index=1,
        key="api_radio"
    )

    if api_key_possessed == "持っています":
        api_key_input = st.text_input(
            "Gemini APIキーをここに貼り付けてください", 
            type="password", 
            key="api_input"
        )
        
        if st.button("✨ APIキーを設定・保存する", key="api_save_button"):
            if api_key_input and len(api_key_input) > 10:
                # APIキーを保存
                st.session_state.api_key = api_key_input
                cookies["api_key"] = api_key_input
                cookies.save()
                st.success("APIキーが保存されました！")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("⚠️ 有効なAPIキーを入力してください。")
    else:
        with st.expander("📖 図解付き：APIキーの取得方法を見る", expanded=True):
            st.write("### ステップ1: Google AI Studioにアクセス")
            st.link_button("🔗 Google AI Studioを開く", "https://aistudio.google.com/")
            
            st.write("### ステップ2: APIキーを作成する")
            st.image("https://i.imgur.com/3i2z622.png", caption="左側のメニューから `Get API key` をクリックします。")
            st.image("https://i.imgur.com/w2m5f2e.png", caption="次に、`Create API key` という青いボタンをクリックします。")
            
            st.write("### ステップ3: APIキーをコピーする")
            st.image("https://i.imgur.com/6a2gG4a.png", caption="表示された文字列があなたのAPIキーです。コピーボタンを押して、上の入力欄に貼り付けてください。")
            st.warning("⚠️ このキーは他人に教えないように大切に保管してくださいね。")


def show_main_app():
    """メインの鑑定アプリ画面を表示する関数"""
    st.success("✨ AI鑑定師との接続が完了しました！")
    st.header("🔮 鑑定の準備が整いました")
    
    # --- ステップ3: 鑑定のパーソナライズ ---
    st.subheader("1️⃣ 鑑定師を選んでください")
    character = st.selectbox(
        "🔮 どの鑑定師に占ってもらいますか？",
        [
            "優しく包み込む、お姉さん系 (淡いピンク)",
            "ロジカルに鋭く分析する、専門家系 (知的なブルー)",
            "星の言葉で語る、ミステリアスな占い師系 (神秘的なパープル)"
        ],
        key="character_select"
    )
    
    st.subheader("2️⃣ 鑑定のトーンを選んでください")
    tone = st.select_slider(
        "🗣️ どんな雰囲気で伝えてほしいですか？",
        options=[
            "癒し 100%（とにかく優しく）",
            "癒し 50% × 論理 50%（バランス型）",
            "冷静にロジカル（事実重視）"
        ],
        value="癒し 50% × 論理 50%（バランス型）",
        key="tone_select"
    )
    
    st.subheader("3️⃣ ミニカウンセリング")
    concern = st.text_area(
        "💬 今回、お相手との関係で、特にどんなことが気になりますか？",
        placeholder="例：最近返信が遅い、デートに誘いたい、など",
        height=100,
        key="concern_input"
    )
    
    st.subheader("4️⃣ あなたとお相手の情報")
    col1, col2 = st.columns(2)
    with col1:
        your_name = st.text_input("あなたの名前", key="your_name")
    with col2:
        partner_name = st.text_input("お相手の名前", key="partner_name")
    
    # --- ステップ4: ファイルアップロード ---
    st.subheader("5️⃣ トーク履歴をアップロード")
    st.info("💡 どんなに長いトーク履歴でも大丈夫。AIが自動で大切な部分だけを読み取って分析しますので、そのままアップロードしてくださいね。")
    
    uploaded_file = st.file_uploader(
        "LINEトーク履歴ファイル (.txt) を選択",
        type=["txt"],
        key="file_uploader"
    )
    
    if uploaded_file is not None:
        st.success(f"📁 ファイル「{uploaded_file.name}」がアップロードされました！")
        
        # TODO: ミニ分析プレビュー機能を実装
        # - ワードクラウド
        # - 平均返信速度
        
    # --- 鑑定開始ボタン ---
    st.write("---")
    if st.button("✨ 鑑定を開始する", type="primary", key="start_analysis"):
        if not your_name or not partner_name:
            st.warning("⚠️ あなたとお相手の名前を入力してください。")
        elif not uploaded_file:
            st.warning("⚠️ トーク履歴ファイルをアップロードしてください。")
        else:
            # TODO: 鑑定処理を実装
            with st.spinner("🔮 AI鑑定師が星に問いかけています..."):
                time.sleep(2)  # デモ用
                st.success("鑑定が完了しました！")
                st.balloons()
                # TODO: 結果表示とPDFダウンロード機能
    
    # --- ログアウトボタン ---
    st.write("---")
    if st.button("🔄 設定をリセット（ログアウト）", key="logout_button"):
        st.session_state.authenticated = False
        st.session_state.api_key = None
        cookies["authenticated"] = "False"
        cookies["api_key"] = ""
        cookies.save()
        st.info("ログアウトしました。ページを更新します...")
        time.sleep(1)
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
