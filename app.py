import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager

# ページの基本設定
st.set_page_config(
    page_title="恋のオラクル AI星譚",
    page_icon="🌙",
    layout="centered",
)

# --- クッキーマネージャーの準備 ---
# ユーザーのブラウザに暗号化してデータを保存するための準備
# "some_random_encryption_key"の部分は、後であなただけの秘密の文字列に変更します
cookies = EncryptedCookieManager(
    password="some_random_encryption_key",
)

# --- 認証状態とAPIキーを管理する場所を準備 ---
# st.session_stateに値がない場合、初期値を設定
if "authenticated" not in st.session_state:
    # 最初にクッキーから認証情報を読み込もうと試みる
    st.session_state.authenticated = cookies.get("authenticated", default=False)
if "api_key" not in st.session_state:
    # 同じく、APIキーもクッキーから読み込む
    st.session_state.api_key = cookies.get("api_key", default=None)


# --- 表示する内容をここで決定 ---

# 共通のヘッダー部分
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")

# 認証されていない場合は、ログイン画面を表示
if not st.session_state.authenticated:
    # 本来はGitHub上のファイルから読み込みますが、最初はここに直接書きます
    VALID_USER_IDS = ["test_user_01", "charo_special_id", "buyer_id_123"]

    st.header("ようこそ、鑑定の世界へ")
    user_id = st.text_input("BOOTHの購入者IDを入力してください")
    
    if st.button("認証する"):
        if user_id in VALID_USER_IDS:
            st.session_state.authenticated = True
            cookies.set("authenticated", True) # 認証成功をクッキーに保存
            st.rerun() # ページを再読み込みして次の画面へ
        else:
            st.error("認証に失敗しました。正しいIDを入力してください。")

# 認証が成功した場合
else:
    # --- APIキー設定画面 ---
    # APIキーがまだ設定されていない場合に、この画面を表示
    if not st.session_state.api_key:
        st.success("認証に成功しました！")
        st.header("🔮 AI鑑定師との接続設定")
        st.info("鑑定を始める前に、一度だけAIとの接続設定をお願いします。この設定は、お使いのブラウザに保存され、次回からは不要になります。")

        api_key_possessed = st.radio(
            "Gemini APIキーはお持ちですか？",
            ("持っています", "持っていません / 取得方法がわかりません"),
            horizontal=True,
            index=1
        )

        if api_key_possessed == "持っています":
            api_key_input = st.text_input("Gemini APIキーをここに貼り付けてください", type="password")
            if st.button("APIキーを設定・保存する"):
                if api_key_input:
                    st.session_state.api_key = api_key_input
                    cookies.set("api_key", api_key_input) # APIキーをクッキーに保存
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
    
    # --- APIキーが設定されたら、いよいよアプリ本体へ ---
    else:
        st.success("AI鑑定師との接続が完了しました！")
        
        st.header("鑑定の準備が整いました")
        st.write("ここに、キャラクター選択やファイルアップロードの機能を作っていきましょう！")

        # ログアウト機能（テスト用）
        if st.button("設定をリセット（ログアウト）"):
            cookies.delete("authenticated")
            cookies.delete("api_key")
            st.session_state.authenticated = False
            st.session_state.api_key = None
            st.rerun()
