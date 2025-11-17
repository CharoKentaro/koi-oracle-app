import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
import time
import re
from datetime import datetime
from collections import Counter
import io # ファイルをメモリ上で扱うために必要

# AIとデータ分析関連のライブラリ
import google.generativeai as genai
import matplotlib.pyplot as plt
import japanize_matplotlib # 日本語化
from wordcloud import WordCloud
from fpdf import FPDF

# ---------------------------------------------------------------------
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
if "authenticated" not in st.session_state:
    st.session_state.authenticated = cookies.get("authenticated", False)
if "api_key" not in st.session_state:
    st.session_state.api_key = cookies.get("api_key", None)
if "cookie_update_needed" not in st.session_state:
    st.session_state.cookie_update_needed = False
if "logout_in_progress" not in st.session_state:
    st.session_state.logout_in_progress = False

# ---------------------------------------------------------------------
# 画面描画関数
# ---------------------------------------------------------------------

def show_login_screen():
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
    st.success("認証に成功しました！")
    st.header("🔮 AI鑑定師との接続設定")
    st.info("鑑定を始める前に、一度だけAIとの接続設定をお願いします。この設定は、お使いのブラウザに保存され、次回からは不要になります。")
    api_key_possessed = st.radio(
        "Gemini APIキーはお持ちですか？", ("持っています", "持っていません / 取得方法がわかりません"),
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
            # (ガイドの詳細は省略)

def show_main_app():
    """メインの鑑定アプリ画面を表示する関数"""
    st.success("AI鑑定師との接続が完了しました！")
    
    # --- パーソナライズ設定 ---
    st.header("Step 1: 鑑定の準備")
    character = st.selectbox(
        "🔮 どの鑑定師に占ってもらいますか？",
        ("優しく包み込む、お姉さん系", "ロジカルに鋭く分析する、専門家系", "星の言葉で語る、ミステリアスな占い師系")
    )
    tone = st.select_slider(
        "🗣️ どんな雰囲気で伝えてほしいですか？",
        options=["癒し 100%", "癒し 50% × 論理 50%", "冷静にロジカル"],
        value="癒し 50% × 論理 50%"
    )
    your_name = st.text_input("💬 あなたのLINEでの名前を教えてください")
    partner_name = st.text_input("💬 お相手のLINEでの名前を教えてください")
    counseling_text = st.text_area(
        "💬 今回、お相手との関係で、特にどんなことが気になりますか？",
        placeholder="例：最近返信が遅い、デートに誘いたい、など"
    )

    st.write("---")
    
    # --- ファイルアップロードと鑑定実行 ---
    st.header("Step 2: トーク履歴をアップロード")
    uploaded_file = st.file_uploader(
        "LINEのトーク履歴ファイル（.txt）をここにアップロードしてください。", type="txt"
    )
    st.info("どんなに長いトーク履歴でも大丈夫。AIが自動で大切な部分だけを読み取って分析します。")

    if uploaded_file is not None:
        # ミニ分析プレビュー
        with st.spinner("トーク履歴を読み込み中..."):
            talk_text = uploaded_file.getvalue().decode("utf-8")
            words = " ".join(re.findall(r'\b\w+\b', talk_text.lower()))
            if words:
                 wordcloud = WordCloud(background_color="white", colormap="viridis", font_path="ipaexg.ttf").generate(words)
                 fig, ax = plt.subplots()
                 ax.imshow(wordcloud, interpolation='bilinear')
                 ax.axis("off")
                 st.pyplot(fig)
        
        if st.button("鑑定を開始する", type="primary"):
            with st.spinner("星々からのメッセージを読み解いています...🔮"):
                # --- ここで本来は全ての分析処理を行う ---
                # ラピッドプロトタイプのため、ダミーデータとダミーAI応答を使用
                
                # ダミーの温度グラフ生成
                fig, ax = plt.subplots()
                days = range(1, 11)
                temp = [5, 6, 8, 7, 9, 10, 9, 8, 7, 8]
                ax.plot(days, temp, marker='o', linestyle='-', color='pink')
                ax.set_title("二人の恋の温度グラフ💖")
                ax.set_xlabel("経過日数")
                ax.set_ylabel("会話の温度")
                ax.grid(True, linestyle='--', alpha=0.6)
                st.pyplot(fig)

                # ダミーのAI応答
                ai_response_text = get_dummy_ai_response(your_name, partner_name)
                st.markdown(ai_response_text)

                # PDFダウンロードボタン
                pdf_data = create_pdf(ai_response_text, fig)
                st.download_button(
                    label="鑑定書をPDFでダウンロード",
                    data=pdf_data,
                    file_name=f"恋の鑑定書_{your_name}さん.pdf",
                    mime="application/pdf"
                )

    # ログアウト機能
    with st.expander("設定"):
        if st.button("設定をリセット（ログアウト）"):
            st.session_state.logout_in_progress = True
            st.rerun()

def get_dummy_ai_response(your_name, partner_name):
    """ダミーのAI応答を生成する関数"""
    return f"""
### 脈あり度：75%

こんにちは、{your_name}さん。{partner_name}さんとの素敵なメッセージ、拝見しました。
お二人の間には、温かくて心地よい光が灯っているのを感じますよ。

### 恋の心理レポート
最近のやり取りには、特にポジティブな感情の交換が増えているようです。これは、{partner_name}さんが{your_name}さんとの会話に安心感を抱いている証拠かもしれませんね。

### 恋の未来予測
このままのペースで、お互いを思いやる気持ちを大切に育んでいけば、1ヶ月後には、もっと深い話題についても自然に話せる関係になっている可能性があります。

### 恋の処方箋・アクションチェックリスト
- **今日送ると効果的なメッセージ例**: 「この前の話、すごく面白かった！また聞かせてね😊」
- **心に刺さるキーワード**: 「さすがだね」「頼りになる」
- **今は控えるべきNG行動**: 焦って結論を求めること
- **次回鑑定のおすすめタイミング**: 何か小さなイベントがあった後
"""

def create_pdf(text, fig):
    """鑑定結果からPDFを生成する関数"""
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font('ipaexg', '', 'ipaexg.ttf', uni=True)
    pdf.set_font('ipaexg', '', 12)
    
    # ダミーのヘッダー
    pdf.cell(0, 10, "恋のオラクル AI星譚 - 鑑定書", ln=True, align='C')
    
    # テキストを書き込み
    # FPDFはMarkdownを直接は解釈しないので、単純なテキストとして書き込む
    cleaned_text = text.replace("### ", "").replace("- ", "  - ")
    pdf.multi_cell(0, 10, cleaned_text)

    # グラフを画像として保存し、PDFに追加
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format='png', dpi=300)
    img_buffer.seek(0)
    pdf.image(img_buffer, x=10, y=pdf.get_y() + 10, w=180)
    
    return pdf.output(dest='S').encode('latin1')

# ---------------------------------------------------------------------
# --- メインの実行ロジック ---
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

# --- スクリプトの最後にクッキー操作をまとめる ---
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
