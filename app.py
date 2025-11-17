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
from fpdf import FPDF, HTMLMixin # ★改善点：FPDF2のHTMLMixinをインポート

# ---------------------------------------------------------------------
# --- ページの基本設定 ---
st.set_page_config(page_title="恋のオラクル AI星譚", page_icon="🌙", layout="centered")

# ---------------------------------------------------------------------
# --- 初期設定と準備 ---
# Streamlit Secretsから安全に設定を読み込む
try:
    COOKIE_PASSWORD = st.secrets["auth"]["cookie_password"]
    VALID_USER_IDS = st.secrets["auth"]["valid_user_ids"]
except (KeyError, FileNotFoundError):
    st.error("認証設定ファイル（secrets.toml）が見つからないか、内容が正しくありません。")
    st.stop()

# クッキーマネージャーの準備
cookies = EncryptedCookieManager(password=COOKIE_PASSWORD)
if not cookies.ready():
    st.stop()

# 状態管理
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

def validate_and_test_api_key(api_key):
    if not api_key or not api_key.startswith("AIza") or len(api_key) < 39:
        return False, "APIキーの形式が正しくありません。"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        model.generate_content("こんにちは", generation_config={"max_output_tokens": 10})
        return True, "APIキーは有効です！接続に成功しました！"
    except Exception as e:
        return False, f"APIキーが無効、または一時的な接続エラーが発生しました。"

def parse_line_chat(text_data):
    lines = text_data.strip().split('\n')
    messages, full_text = [], []
    date_pattern = re.compile(r'^\d{4}/\d{2}/\d{2}\(.+?\)')
    current_date = ""
    patterns = [re.compile(r'^(\d{1,2}:\d{2})\t(.+?)\t(.+)'), re.compile(r'^午[前後](\d{1,2}:\d{2})\t(.+?)\t(.+)')]
    for line in lines:
        if date_pattern.match(line):
            current_date = line.split('\t')[0]
            continue
        matched = False
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                groups = match.groups()
                sender, message = groups[-2], groups[-1]
                if message not in ["[写真]", "[動画]", "[スタンプ]", "[ファイル]"]:
                    messages.append({'timestamp': f"{current_date} {groups[0]}", 'sender': sender.strip(), 'message': message.strip()})
                    full_text.append(message.strip())
                matched = True
                break
        if not matched and messages and line.strip():
            messages[-1]['message'] += '\n' + line.strip()
            full_text[-1] += ' ' + line.strip()
    return messages, " ".join(full_text)

def smart_extract_text(messages, max_chars=5000):
    text_lines = [f"{msg['timestamp']} {msg['sender']}: {msg['message']}" for msg in messages]
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
            date_str = msg['timestamp'].split(' ')[0]
            date_obj = datetime.strptime(date_str, '%Y/%m/%d(%a)')
            score = len(msg['message']) + msg['message'].count('!') * 2 + msg['message'].count('？') * 2
            daily_scores[date_obj.strftime('%m/%d')] += score
        except: continue
    if not daily_scores: return {}, "データ不足"
    sorted_scores = sorted(daily_scores.items())
    labels, values = [item[0] for item in sorted_scores], [item[1] for item in sorted_scores]
    trend = "安定"
    if len(values) >= 4:
        last_avg = sum(values[-3:]) / 3
        prev_avg = sum(values[:-3]) / len(values[:-3]) if len(values[:-3]) > 0 else 0
        if prev_avg > 0 and last_avg > prev_avg * 1.2: trend = "上昇傾向"
        elif prev_avg > 0 and last_avg < prev_avg * 0.8: trend = "下降傾向"
    return {'labels': labels, 'values': values}, trend

def build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, trend, previous_data=None):
    character_map = {
        "1. 優しく包み込む、お姉さん系": "優しく包み込むお姉さんタイプの鑑定師",
        "2. ロジカルに鋭く分析する、専門家系": "ロジカルに鋭く分析する専門家タイプの鑑定師",
        "3. 星の言葉で語る、ミステリアスな占い師系": "星の言葉で語るミステリアスな占い師"
    }
    tone_instruction = {
        "癒し 100%": "とにかく優しく、温かく包み込むような言葉遣いで。否定的な表現は避け、常に希望を見出してください。",
        "癒し 50% × 論理 50%": "優しさと客観性のバランスを保ちながら、事実も伝えつつ励ましてください。",
        "冷静にロジカル": "感情に流されず、客観的なデータと論理的な分析を中心に伝えてください。"
    }
    prompt = f"""あなたは【{character_map.get(character, character)}】です。
ユーザーは【{tone}】のスタイルでの鑑定を望んでいます。{tone_instruction.get(tone, '')}
このトーンと言葉遣いを、出力の最後まで徹底して維持してください。
以下のデータを基に、単なる占いではない、心理分析に基づいた詳細な「恋の心理レポート」を作成してください。
# ユーザー情報
- ユーザー名: {your_name}
- 相手の名前: {partner_name}
- ユーザーの悩み: {counseling_text}
"""
    if previous_data:
        prompt += f"""
# 過去の鑑定データ
- 前回の鑑定日: {previous_data.get('date', '不明')}
- 前回の脈あり度: {previous_data.get('pulse_score', 0)}%
- 前回の鑑定サマリー: {previous_data.get('summary', 'なし')}
- **特別指示**: あなたはユーザーの{your_name}さんを覚えています。導入文で「{your_name}さん、こんにちは。前回の鑑定から少し時間が経ちましたね」のように、再会を喜ぶ自然な語り口で始めてください。また、今回の分析結果と過去のデータを比較し、「前回よりも〇〇な点が増えていますね」といった、関係性の変化についての言及をレポート内に含めてください。
"""
    prompt += f"""
# 基本データ分析
- 会話の温度グラフの傾向: {trend}
- 分析対象の会話抜粋:\n{messages_summary}
# AIによる深層分析依頼
1. **感情の波の分析**: トーク履歴全体を通して、「ポジティブ」「ネガティブ」な感情表現は、それぞれどのような傾向で推移していますか？
2. **脈ありシグナルのスコア化**: 以下の項目を0〜10点で評価し、総合的な「脈あり度」をパーセンテージで算出してください。
   - 質問返しの積極性, ポジティブな絵文字・表現の使用頻度, 返信間隔の安定性・速さ, 相手からの賞賛・共感の言葉, 会話を広げようとする意図
   - 【総合脈あり度】: 〇〇%
   - なぜそのスコアになったのか、根拠を優しく解説してください。
3. **相手の"隠れ心理"抽出**: 会話の中から、相手が特に「大切にしている価値観」や「本音だと感じられる発言」を3つ抜粋し、解説してください。
4. **コミュニケーション相性診断**: 二人の言葉遣いや会話のテンポから、コミュニケーションのスタイルを分析し、「〇〇で繋がりを深めるタイプ」といった形で相性を診断してください。
5. **「最高の瞬間」ハイライト**: このトーク履歴の中で、二人の心が最も通い合ったと感じられる瞬間を1つ選び出し、その時の会話の素晴らしい点を解説してください。
6. **恋の未来予測**: これまでの会話データと心理分析に基づき、二人の関係性がポジティブに進展するための、心理学的な観点からの**優しい未来予測**を記述してください。
7. **恋の処方箋・アクションチェックリスト**: 以下の4項目について、具体的かつ実践的なアドバイスを箇条書きで作成してください。
   - **今日送ると効果的なメッセージ例**: （★★1つにつき80文字以内で、最大3つ★★）
   - **相手のタイプ別・心に刺さるキーワード**: （単語や褒め言葉）
   - **今は控えるべきNG行動**: （具体的な行動を優しく指摘）
   - **次回鑑定のおすすめタイミング**: （具体的なタイミング）
# 最終出力
上記の分析結果をすべて含め、以下の構成でレポートを作成してください。
- 導入文, **恋の温度グラフの解説**, 総合脈あり度と、その理由, 恋の心理レポート, 「最高の瞬間」の振り返り, **恋の未来予測**, **恋の処方箋・アクションチェックリスト**, ユーザーへのケアメッセージ, 最後に、ユーザーを温かく励ます一言
重要: 必ず日本語で、{your_name}さんに語りかけるような親しみやすい文体で書いてください。出力は最大6000文字以内に抑えてください。
"""
    return prompt

def save_diagnosis_result(user_id, partner_name, pulse_score, summary):
    if not user_id: return
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f: data = json.load(f)
        except: data = []
    else: data = []
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
    except: return None
    for record in reversed(data):
        if record.get("partner_name") == partner_name: return record
    return None

def extract_pulse_score_from_response(ai_response):
    match = re.search(r'総合脈あり度[】:\s]*(\d+)\s*%', ai_response)
    if match: return int(match.group(1))
    return 0

def extract_summary_from_response(ai_response):
    lines = ai_response.split('\n')
    summary = ""
    for line in lines:
        if line.strip() and not line.startswith('#'): summary += line.strip() + " "
        if len(summary) > 200: break
    return summary[:200] + '...'

class MyPDF(FPDF, HTMLMixin):
    def footer(self):
        self.set_y(-20)
        font_path = get_japanese_font()
        if font_path and 'Japanese' not in self.fonts: # ★改善点③：より安全なチェック
            try: self.add_font('Japanese', '', font_path, uni=True)
            except: font_path = None # 失敗したらフォントなしとみなす
        
        if font_path: self.set_font('Japanese', '', 8)
        else: self.set_font('Arial', '', 8)
            
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, "本鑑定はAIによる心理分析です。", align='C')
        self.ln(4)
        self.cell(0, 10, "あなたの恋を心から応援しています 💖", align='C')

def create_pdf(ai_response_text, graph_img_buffer, character):
    pdf = MyPDF()
    pdf.add_page()
    font_path = get_japanese_font()
    font_available = font_path is not None
    if font_available:
        try:
            pdf.add_font('Japanese', '', font_path, uni=True)
            pdf.set_font('Japanese', '', 12)
        except:
            font_available = False
            pdf.set_font('Arial', '', 12)
    else:
        pdf.set_font('Arial', '', 12)
        
    color_map = {
        "1. 優しく包み込む、お姉さん系": (255, 182, 193),
        "2. ロジカルに鋭く分析する、専門家系": (135, 206, 235),
        "3. 星の言葉で語る、ミステリアスな占い師系": (186, 85, 211),
    }
    theme_color = color_map.get(character, (200, 200, 200))
    pdf.set_fill_color(*theme_color)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font_size(20); pdf.cell(0, 25, "恋のオラクル AI星譚", ln=True, align='C')
    pdf.set_font_size(10); pdf.cell(0, 0, "- 心の羅針盤 Edition -", ln=True, align='C')
    pdf.set_text_color(0, 0, 0); pdf.ln(20)
    pdf.set_font_size(10); pdf.cell(0, 8, f"鑑定日: {datetime.now().strftime('%Y年%m月%d日')}", ln=True, align='R'); pdf.ln(5)
    pdf.set_font_size(11)

    html_text = ai_response_text.replace('\n', '<br>')
    html_text = re.sub(r'###\s*(.*?)(<br>|$)', r'<b>\1</b><br>', html_text)
    html_text = f"<p>{html_text}</p>" # ★改善点①：pタグで囲む

    if font_available:
        pdf.write_html(html_text)
    else:
        safe_text = html_text.encode("latin-1", "replace").decode("latin-1")
        pdf.write_html(safe_text)

    pdf.add_page()
    pdf.set_font('Japanese' if font_available else 'Arial', '', 14)
    pdf.cell(0, 10, "二人の恋の温度グラフ", ln=True, align='C'); pdf.ln(5)
    graph_img_buffer.seek(0)
    pdf.image(graph_img_buffer, x=10, y=pdf.get_y(), w=190)
    
    return pdf.output(dest="S").encode("latin-1") # ★改善点②：FPDF2の公式な書き方

# ---------------------------------------------------------------------
# 画面描画関数
# ---------------------------------------------------------------------

def show_login_screen():
    st.header("ようこそ、鑑定の世界へ")
    user_id = st.text_input("BOOTHの購入者IDを入力してください", key="login_user_id")
    if st.button("認証する", key="login_button"):
        if user_id in VALID_USER_IDS:
            st.session_state.authenticated = True
            st.session_state.user_id = user_id
            cookies["authenticated"] = "True"
            cookies["user_id"] = user_id
            cookies.save()
            st.rerun()
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
            cookies.save()
            st.success(message)
            time.sleep(1)
            st.rerun()
        else: st.error(message)

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
            messages, full_text = parse_line_chat(talk_data)
            if not messages:
                 st.warning("⚠️ 有効なメッセージが見つかりませんでした。")
                 return
            st.success(f"✅ {len(messages)}件のメッセージを読み込みました！")
            
            with st.spinner("よく使われる言葉を分析中..."):
                font_path = get_japanese_font()
                if font_path:
                    japanese_words = re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]{2,}', full_text)
                    if japanese_words:
                        word_freq = Counter(japanese_words)
                        filtered_freq = {word: count for word, count in word_freq.most_common(50) if count >= 2}
                        if filtered_freq:
                            wordcloud = WordCloud(font_path=font_path, width=800, height=400, background_color="white").generate_from_frequencies(filtered_freq)
                            fig_wc, ax_wc = plt.subplots(); ax_wc.imshow(wordcloud, interpolation='bilinear'); ax_wc.axis("off"); st.pyplot(fig_wc); plt.close(fig_wc)
                else:
                    st.info("⚠️ この環境ではワードクラウド用の日本語フォントが利用できないため、このステップをスキップします。")
            
            st.write("---")
            
            if st.button("🔮 鑑定を開始する", type="primary", use_container_width=True):
                with st.spinner("星々からのメッセージを読み解いています...✨"):
                    previous_data = load_previous_diagnosis(st.session_state.user_id, partner_name)
                    if previous_data: st.info(f"📖 {partner_name}さんとの前回の鑑定データが見つかりました。")
                    
                    color_map_graph = {
                        "1. 優しく包み込む、お姉さん系": ("#ff69b4", "#ffb6c1"),       # line_color, fill_color
                        "2. ロジカルに鋭く分析する、専門家系": ("#1e90ff", "#add8e6"),
                        "3. 星の言葉で語る、ミステリアスな占い師系": ("#9370db", "#e6e6fa")
                    }
                    # 選択されたキャラクターに対応する色を取得（見つからない場合はピンクをデフォルトに）
                    line_color, fill_color = color_map_graph.get(character, ("#ff69b4", "#ffb6c1"))

                    temp_data, trend = calculate_temperature(messages)
                    fig_graph, ax_graph = plt.subplots(figsize=(10, 6))
                    if temp_data.get('labels'):
                        ax_graph.plot(temp_data['labels'], temp_data['values'], marker='o', color=line_color, linewidth=2)
                        ax_graph.fill_between(temp_data['labels'], temp_data['values'], color=fill_color, alpha=0.5)
                        plt.xticks(rotation=45, ha="right")
                    ax_graph.set_title('💖 二人の恋の温度グラフ', fontsize=14, pad=20)
                    plt.tight_layout()
                    
                    img_buffer = io.BytesIO()
                    fig_graph.savefig(img_buffer, format='png', dpi=300, bbox_inches='tight')
                    img_buffer.seek(0)
                    st.pyplot(fig_graph)
                    plt.close(fig_graph)
                    
                    try:
                        genai.configure(api_key=st.session_state.api_key)
                        model = genai.GenerativeModel('gemini-pro')
                        messages_summary = smart_extract_text(messages, max_chars=5000)
                        final_prompt = build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, trend, previous_data)
                        
                        response = model.generate_content(final_prompt, generation_config={"max_output_tokens": 6144, "temperature": 0.75})
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
            st.error("💫 ごめんなさい、予期しないエラーが発生しました...")
            with st.expander("🔧 詳細"): st.code(f"{traceback.format_exc()}")
            
    with st.expander("⚙️ 設定"):
        if st.button("🔓 ログアウト"):
            for key in list(st.session_state.keys()): del st.session_state[key]
            cookies.delete("authenticated"); cookies.delete("api_key"); cookies.delete("user_id"); cookies.save()
            st.rerun()

# ---------------------------------------------------------------------
# --- メインの実行ロジック ---
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")

if not st.session_state.authenticated: show_login_screen()
elif not st.session_state.api_key: show_api_key_screen()
else: show_main_app()
