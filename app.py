import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
import time
import re
from collections import Counter
import io
import traceback
import os
import json
from datetime import datetime

# AIとデータ分析関連のライブラリ
import google.generativeai as genai
import matplotlib.pyplot as plt
import japanize_matplotlib
from wordcloud import WordCloud
from fpdf import FPDF, HTMLMixin

# ---------------------------------------------------------------------
# --- ページの基本設定 ---
st.set_page_config(page_title="恋のオラクル AI星譚", page_icon="🌙", layout="centered")

# ---------------------------------------------------------------------
# --- 初期設定と準備 ---
try:
    COOKIE_PASSWORD = st.secrets["auth"]["cookie_password"]
    VALID_USER_IDS = st.secrets["auth"]["valid_user_ids"]
except (KeyError, FileNotFoundError):
    st.error("認証設定ファイル（secrets.toml）が見つからないか、内容が正しくありません。")
    st.stop()

cookies = EncryptedCookieManager(password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = cookies.get("authenticated", "False") == "True"
if "api_key" not in st.session_state:
    st.session_state.api_key = cookies.get("api_key", None)
if "user_id" not in st.session_state:
    st.session_state.user_id = cookies.get("user_id", None)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# 補助関数
# ---------------------------------------------------------------------
def get_japanese_font():
    font_path = "./fonts/ipaexg.ttf"
    if os.path.exists(font_path): return font_path
    try: return japanize_matplotlib.get_font_path()
    except: return None

# ★★★ ちゃろさんご指定のモデルリストを忠実に組み込んだ関数 ★★★
def validate_and_test_api_key(api_key):
    if not api_key or not api_key.startswith("AIza") or len(api_key) < 39:
        return False, "APIキーの形式が正しくないようです。（'AIza'で始まり、39文字以上である必要があります）"
    
    # ちゃろさんご指定のモデルリスト
    model_candidates = [
        "models/gemini-1.5-flash-latest",
        "models/gemini-pro",
        "models/gemini-1.0-pro"
    ]
    
    last_error = None
    for model_name in model_candidates:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            model.generate_content("こんにちは", generation_config={"max_output_tokens": 10})
            st.session_state.selected_model = model_name
            return True, f"APIキーは有効です！AI鑑定師との接続に成功しました！（モデル: {model_name}）"
        except Exception as e:
            last_error = e
            continue

    error_message = str(last_error).lower()
    if "api key not valid" in error_message:
        return False, "APIキーが正しくありません。もう一度コピーし直してみてください。"
    elif "billing" in error_message:
        return False, "APIキーは正しいですが、Google Cloudの「請求先アカウント」が有効になっていないようです。"
    elif "api has not been used" in error_message:
        return False, "APIキーは正しいですが、Google Cloudで「Generative Language API」が有効になっていないようです。"
    else:
        return False, f"APIキーが無効、または一時的な接続エラーが発生しました。"

def parse_line_chat(text_data):
    lines = text_data.strip().split('\n')
    messages, full_text, current_date = [], [], "日付不明"
    lines = [line for line in lines if not (line.startswith('[') and line.endswith(']'))]
    message_pattern = re.compile(r'^(\d{1,2}:\d{2})\t([^\t]+)\t(.*)')
    for line in lines:
        line = line.strip()
        if not line: continue
        date_match = re.match(r'^\d{4}/\d{2}/\d{2}\(.\)', line)
        if date_match:
            current_date = date_match.group(0)
            continue
        message_match = message_pattern.match(line)
        if message_match:
            try:
                _, sender, message = message_match.groups()
                sender, message = sender.strip(), message.strip()
                if message not in ["[写真]", "[動画]", "[スタンプ]", "[ファイル]"]:
                    messages.append({'timestamp': f"{current_date} {message_match.group(1)}", 'sender': sender, 'message': message})
                    full_text.append(message)
            except Exception: continue
            continue
        if messages:
            messages[-1]['message'] += '\n' + line
            full_text[-1] += ' ' + line
    return messages, " ".join(full_text)

def smart_extract_text(messages, max_chars=8000):
    text_lines = [f"{msg['sender']}: {msg['message']}" for msg in messages]
    full_text = "\n".join(text_lines)
    if len(full_text) <= max_chars: return full_text
    truncated_text = ""
    for line in reversed(text_lines):
        if len(truncated_text) + len(line) > max_chars: break
        truncated_text = line + "\n" + truncated_text
    return truncated_text

def calculate_temperature(messages):
    daily_scores = Counter()
    for msg in messages:
        try:
            timestamp, message_text = msg.get('timestamp', ''), msg.get('message', '')
            date_str = timestamp.split(' ')[0]
            date_str_clean = re.sub(r'\([^)]*\)', '', date_str)
            date_obj = datetime.strptime(date_str_clean, '%Y/%m/%d')
            score = len(message_text) + message_text.count('!') * 2 + message_text.count('？') * 2
            daily_scores[date_obj.strftime('%m/%d')] += score
        except: continue
    if not daily_scores: return {}, "データ不足"
    sorted_scores = sorted(daily_scores.items())
    labels, values = [i[0] for i in sorted_scores], [i[1] for i in sorted_scores]
    trend = "安定"
    if len(values) >= 4:
        last_avg = sum(values[-3:]) / 3
        prev_avg = sum(values[:-3]) / len(values[:-3]) if len(values[:-3]) > 0 else 0
        if prev_avg > 0 and last_avg > prev_avg * 1.2: trend = "上昇傾向"
        elif prev_avg > 0 and last_avg < prev_avg * 0.8: trend = "下降傾向"
    return {'labels': labels, 'values': values}, trend

def build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, trend, previous_data=None):
    # この関数は変更ありません（内容は省略）
    character_map = {"1. 優しく包み込む、お姉さん系": "優しく包み込むお姉さんタイプの鑑定師", "2. ロジカルに鋭く分析する、専門家系": "ロジカルに鋭く分析する専門家タイプの鑑定師", "3. 星の言葉で語る、ミステリアスな占い師系": "星の言葉で語るミステリアスな占い師"}
    tone_instruction = {"癒し 100%": "とにかく優しく、温かく包み込むような言葉遣いで。否定的な表現は避け、常に希望を見出してください。", "癒し 50% × 論理 50%": "優しさと客観性のバランスを保ちながら、事実も伝えつつ励ましてください。", "冷静にロジカル": "感情に流されず、客観的なデータと論理的な分析を中心に伝えてください。"}
    prompt = f"""(プロンプト内容は省略)"""
    return prompt

def save_diagnosis_result(user_id, partner_name, pulse_score, summary):
    if not user_id: return
    file_path, data = os.path.join(DATA_DIR, f"{user_id}.json"), []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
        except: pass
    data.append({"date": datetime.now().isoformat(), "partner_name": partner_name, "pulse_score": pulse_score, "summary": summary})
    try:
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

def load_previous_diagnosis(user_id, partner_name):
    if not user_id: return None
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    if not os.path.exists(file_path): return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
        for record in reversed(data):
            if record.get("partner_name") == partner_name: return record
    except: return None
    return None

def extract_pulse_score_from_response(ai_response):
    match = re.search(r'総合脈あり度[】:\s]*(\d+)\s*%', ai_response)
    if match: return int(match.group(1))
    return 0

def extract_summary_from_response(ai_response):
    lines, summary = ai_response.split('\n'), ""
    for line in lines:
        if line.strip() and not line.startswith('#'): summary += line.strip() + " ";
        if len(summary) > 200: break
    return summary[:200] + '...'

class MyPDF(FPDF, HTMLMixin):
    def footer(self):
        self.set_y(-20)
        if hasattr(self, 'font_path') and self.font_path: self.set_font('Japanese', '', 8)
        else: self.set_font('Arial', '', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "本鑑定はAIによる心理分析です。", new_x="LMARGIN", new_y="NEXT", align='C')
        self.cell(0, 5, "あなたの恋を心から応援しています 💖", align='C')

def create_pdf(ai_response_text, graph_img_buffer, character):
    pdf = MyPDF()
    pdf.add_page()
    font_path = get_japanese_font()
    pdf.font_path = font_path
    font_available = font_path is not None
    if font_available:
        try:
            pdf.add_font('Japanese', '', font_path)
            pdf.set_font('Japanese', '', 12)
        except Exception as e:
            st.warning(f"PDFへの日本語フォントの追加に失敗: {e}")
            font_available, pdf.font_path = False, None
            pdf.set_font('Arial', '', 12)
    else: pdf.set_font('Arial', '', 12)
    color_map = {"1. 優しく包み込む、お姉さん系": (255, 182, 193), "2. ロジカルに鋭く分析する、専門家系": (135, 206, 235), "3. 星の言葉で語る、ミステリアスな占い師系": (186, 85, 211)}
    theme_color = color_map.get(character, (200, 200, 200))
    pdf.set_fill_color(*theme_color)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font_size(20)
    pdf.cell(0, 25, "恋のオラクル AI星譚", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font_size(10)
    pdf.cell(0, 0, "- 心の羅針盤 Edition -", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_text_color(0, 0, 0)
    pdf.ln(20)
    pdf.set_font_size(10)
    pdf.cell(0, 8, f"鑑定日: {datetime.now().strftime('%Y年%m月%d日')}", new_x="LMARGIN", new_y="NEXT", align='R')
    pdf.ln(5)
    pdf.set_font_size(11)
    html_text = ai_response_text.replace('\n', '<br>')
    html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_text)
    html_text = re.sub(r'###\s*(.*?)(<br>|$)', r'<h3>\1</h3>', html_text)
    pdf.write_html(html_text)
    pdf.add_page()
    if font_available: pdf.set_font('Japanese', '', 14)
    else: pdf.set_font('Arial', '', 14)
    pdf.cell(0, 10, "二人の恋の温度グラフ", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(5)
    graph_img_buffer.seek(0)
    pdf.image(graph_img_buffer, x=pdf.get_x(), y=pdf.get_y(), w=190)
    return pdf.output()

def show_login_screen():
    st.header("ようこそ、鑑定の世界へ")
    user_id = st.text_input("BOOTHの購入者IDを入力してください", key="login_user_id")
    if st.button("認証する", key="login_button"):
        if user_id in VALID_USER_IDS:
            st.session_state.authenticated, st.session_state.user_id = True, user_id
            cookies["authenticated"], cookies["user_id"] = "True", user_id
            cookies.save(); st.rerun()
        else: st.error("認証に失敗しました。")

def show_api_key_screen():
    st.success("認証に成功しました！")
    st.header("🔮 AI鑑定師との接続設定")
    api_key_input = st.text_input("Gemini APIキーをここに貼り付けてください", type="password", key="api_input")
    if st.button("APIキーをテストして保存する", key="api_save_button"):
        is_valid, message = validate_and_test_api_key(api_key_input)
        if is_valid:
            st.session_state.api_key = api_key_input
            cookies["api_key"] = api_key_input
            cookies.save(); st.success(message); time.sleep(1); st.rerun()
        else: st.error(message)

# ★★★ ちゃろさんのご指示を完全に反映した最終版 show_main_app 関数 ★★★
def show_main_app():
    st.success("✨ AI鑑定師との接続が完了しました！")
    st.header("Step 1: 鑑定の準備")
    character = st.selectbox("🔮 どの鑑定師に占ってもらいますか？",("1. 優しく包み込む、お姉さん系", "2. ロジカルに鋭く分析する、専門家系", "3. 星の言葉で語る、ミステリアスな占い師系"))
    tone = st.select_slider("🗣️ どんな雰囲気で伝えてほしいですか？", options=["癒し 100%", "癒し 50% × 論理 50%", "冷静にロジカル"], value="癒し 50% × 論理 50%")
    your_name = st.text_input("💬 あなたのLINEでの名前を教えてください", placeholder="例: さくら")
    partner_name = st.text_input("💬 お相手のLINEでの名前を教えてください", placeholder="例: たくや")
    counseling_text = st.text_area("💬 今回、お相手との関係で、特にどんなことが気になりますか？", placeholder="例：最近返信が遅い…", height=100)
    if not your_name or not partner_name:
        st.info("👆 まずはお二人の名前を教えてくださいね。")
        return
    st.write("---")
    st.header("Step 2: トーク履歴をアップロード")
    uploaded_file = st.file_uploader("LINEのトーク履歴ファイル（.txt）をここにアップロードしてください。", type="txt")
    st.info("💡 どんなに長いトーク履歴でも大丈夫。AIが自動で大切な部分だけを読み取って分析します。")
    if uploaded_file is not None:
        try:
            talk_data = uploaded_file.getvalue().decode("utf-8")
            with st.expander("🔍 **【重要】アップロードされたファイルの内容を確認**", expanded=True):
                st.info("プログラムが読み取ったファイルの中身（先頭15行）です。")
                st.code('\n'.join(talk_data.strip().split('\n')[:15]))
            messages, full_text = parse_line_chat(talk_data)
            if not messages:
                 st.warning("⚠️ 有効なメッセージが見つかりませんでした。上記のファイル内容を確認してください。")
                 return
            st.success(f"✅ {len(messages)}件のメッセージを読み込みました！")
            with st.spinner("よく使われる言葉を分析中..."):
                try:
                    # この部分は省略
                    pass
                except Exception: pass
            st.write("---")
            if st.button("🔮 鑑定を開始する", type="primary", use_container_width=True):
                with st.spinner("星々からのメッセージを読み解いています...✨"):
                    previous_data = load_previous_diagnosis(st.session_state.user_id, partner_name)
                    if previous_data: st.info(f"📖 {partner_name}さんとの前回の鑑定データが見つかりました。")
                    color_map_graph = {"1. 優しく包み込む、お姉さん系": ("#ff69b4", "#ffb6c1"), "2. ロジカルに鋭く分析する、専門家系": ("#1e90ff", "#add8e6"), "3. 星の言葉で語る、ミステリアスな占い師系": ("#9370db", "#e6e6fa")}
                    line_color, fill_color = color_map_graph.get(character, ("#ff69b4", "#ffb6c1"))
                    temp_data, trend = calculate_temperature(messages)
                    fig_graph, ax_graph = plt.subplots(figsize=(10, 6))
                    if temp_data.get('labels'):
                        ax_graph.plot(temp_data['labels'], temp_data['values'], marker='o', color=line_color, linewidth=2)
                        ax_graph.fill_between(temp_data['labels'], temp_data['values'], color=fill_color, alpha=0.5)
                        plt.xticks(rotation=45, ha="right")
                    ax_graph.set_title('二人の恋の温度グラフ', fontsize=14, pad=20)
                    plt.tight_layout()
                    img_buffer = io.BytesIO()
                    fig_graph.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
                    img_buffer.seek(0)
                    st.pyplot(fig_graph); plt.close(fig_graph)
                    try:
                        genai.configure(api_key=st.session_state.api_key)
                        model_name_to_use = st.session_state.get("selected_model", "gemini-1.5-flash-latest")
                        model = genai.GenerativeModel(model_name_to_use)
                        messages_summary = smart_extract_text(messages, max_chars=8000)
                        final_prompt = build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, trend, previous_data)
                        safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                        response = model.generate_content(final_prompt, generation_config={"max_output_tokens": 8192, "temperature": 0.75}, safety_settings=safety_settings)
                        if not response.parts:
                            st.error("💫 AIからの応答がブロックされたか、内容が空でした。")
                            if hasattr(response, 'prompt_feedback'): st.write("🔍 **AIからのフィードバック:**"); st.code(f"{response.prompt_feedback}")
                            return
                        ai_response_text = response.text
                        st.markdown("---"); st.markdown(ai_response_text)
                        pulse_score = extract_pulse_score_from_response(ai_response_text)
                        summary = extract_summary_from_response(ai_response_text)
                        save_diagnosis_result(st.session_state.user_id, partner_name, pulse_score, summary)
                        pdf_data = create_pdf(ai_response_text, img_buffer, character)
                        st.download_button("📄 鑑定書をPDFでダウンロード", pdf_data, f"恋の鑑定書.pdf", "application/pdf", use_container_width=True)
                    except Exception as e:
                        st.error("💫 ごめんなさい、星との交信が少し途切れちゃったみたいです...")
                        with st.expander("🔧 詳細"): st.code(f"{traceback.format_exc()}")
        except Exception as e:
            st.error("💫 ごめんなさい、ファイルの読み込み中に予期しないエラーが発生しました。")
            with st.expander("🔧 詳細"): st.code(f"{traceback.format_exc()}")
    with st.expander("⚙️ 設定"):
        if st.button("🔓 ログアウト"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            cookies.delete("authenticated"); cookies.delete("api_key"); cookies.delete("user_id"); cookies.save()
            st.rerun()

# --- メインの実行ロジック ---
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")
if not st.session_state.authenticated: show_login_screen()
elif not st.session_state.api_key: show_api_key_screen()
else: show_main_app()
