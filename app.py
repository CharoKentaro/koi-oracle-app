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
from fpdf import FPDF

# ★★★ 追加：Googleスプレッドシート連携ライブラリ ★★★
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------------------
# --- ページの基本設定 ---
st.set_page_config(page_title="恋のオラクル AI恋星譚", page_icon="🌙", layout="centered")

# ---------------------------------------------------------------------
# --- 補助関数 (Googleスプレッドシート連携) ---
# ---------------------------------------------------------------------
# ★★★ 新設：Googleスプレッドシートから認証ユーザーを取得する関数 ★★★
@st.cache_data(ttl=300)  # 5分間キャッシュ（頻繁に更新する場合は短くする）
def load_valid_users_from_sheet():
    """Googleスプレッドシートから有効なユーザーIDのリストを取得します。"""
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet_id = st.secrets["spreadsheet"]["id"]
        sheet = client.open_by_key(spreadsheet_id).sheet1
        user_ids = sheet.col_values(1)[1:]  # A列の2行目以降を取得
        valid_user_ids = [uid.strip() for uid in user_ids if uid.strip()]
        return valid_user_ids
    except Exception as e:
        st.error(f"スプレッドシートからユーザー情報の取得に失敗しました。管理者に連絡してください。")
        st.code(f"エラー詳細: {e}")
        return []


# --- 初期設定と準備 ---
try:
    COOKIE_PASSWORD = st.secrets["auth"]["cookie_password"]
    VALID_USER_IDS = load_valid_users_from_sheet()
except (KeyError, FileNotFoundError):
    st.error("認証設定ファイル（secrets.toml）が見つからないか、内容が正しくありません。")
    st.stop()

cookies = EncryptedCookieManager(password=COOKIE_PASSWORD)

# ★★★【最重要修正】Cookieの準備中にメッセージを表示し、真っ白画面を防ぐ ★★★
if not cookies.ready():
    st.title("🌙 恋のオラクル AI恋星譚")
    st.caption("- 心の羅針盤 Edition -")
    st.write("---")
    st.info("🔄 アプリを準備しています。少々お待ちください...")
    st.stop()

# セッション情報の初期化（一度だけ実行）
if "session_initialized" not in st.session_state:
    st.session_state.authenticated = cookies.get("authenticated", "False") == "True"
    st.session_state.api_key = cookies.get("api_key", None)
    st.session_state.user_id = cookies.get("user_id", None)
    st.session_state.session_initialized = True

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------
# 補助関数 (ここから下は既存の関数、変更なし)
# ---------------------------------------------------------------------
def get_japanese_font():
    font_path = "./fonts/ipaexg.ttf"
    if os.path.exists(font_path): return font_path
    try: return japanize_matplotlib.get_font_path()
    except: return None

def validate_and_test_api_key(api_key):
    if not api_key or not api_key.startswith("AIza") or len(api_key) < 39:
        return False, "APIキーの形式が正しくないようです。（'AIza'で始まり、39文字以上である必要があります）"
    # ★★★ 修正：正しいモデルリストに戻す ★★★
    model_candidates = [
        "models/gemini-2.5-flash",
        "models/gemini-flash-latest",
        "models/gemini-2.5-pro",
        "models/gemini-pro-latest",
        "models/gemini-2.0-flash-001"
    ]
    last_error = None
    for model_name in model_candidates:
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            model.generate_content("こんにちは", generation_config={"max_output_tokens": 10})
            st.session_state.selected_model = model_name
            cookies["selected_model"] = model_name
            return True, f"APIキーは有効です！AI鑑定師との接続に成功しました！（モデル: {model_name}）"
        except Exception as e:
            last_error = e
            continue
    error_message = str(last_error).lower()
    if "api key not valid" in error_message: return False, "APIキーが正しくありません。"
    elif "billing" in error_message: return False, "APIキーは正しいですが、Google Cloudの「請求先アカウント」が有効になっていません。"
    elif "api has not been used" in error_message: return False, "APIキーは正しいですが、Google Cloudで「Generative Language API」が有効になっていません。"
    else: return False, "APIキーが無効、または一時的な接続エラーが発生しました。"

# validate_and_test_api_key 関数の下に追加
def test_model_name(api_key, model_name):
    """指定されたモデル名が有効かテストする"""
    if not model_name or "models/" not in model_name:
        return False, "モデル名の形式が正しくないようです。（例: models/gemini-2.5-flash）"
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        model.generate_content("test", generation_config={"max_output_tokens": 10})
        return True, f"モデル「{model_name}」は有効です！"
    except Exception as e:
        error_message = str(e).lower()
        if "not found" in error_message or "invalid" in error_message:
            return False, "モデル名が正しくないようです。コピペミスかも？もう一度入力してみてね。"
        else:
            return False, f"モデルのテスト中にエラーが発生しました。"


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



# smart_extract_text 関数のすぐ下にでも貼り付けてください

def create_long_term_summary(messages, max_chars=4000):
    """
    トーク履歴全体から、関係性の流れがわかるようにダイジェストを作成します。
    「初期」「中期」「後期」の3つの期間から均等に会話を抽出します。
    """
    text_lines = [f"{msg['sender']}: {msg['message']}" for msg in messages]
    if not text_lines:
        return "会話データがありません。"

    full_text = "\n".join(text_lines)
    if len(full_text) <= max_chars:
        return full_text # 全文が指定文字数以下なら、そのまま返す

    summary = []
    
    # 期間を3つに分割
    total_lines = len(text_lines)
    part_size = total_lines // 3
    
    # 各期間から抽出する目標文字数
    chars_per_part = max_chars // 3

    # パート1: 初期
    part1_lines = text_lines[:part_size]
    part1_text = ""
    for line in part1_lines:
        if len(part1_text) + len(line) > chars_per_part: break
        part1_text += line + "\n"
    summary.append("--- 関係の初期 ---\n" + part1_text)

    # パート2: 中期
    part2_lines = text_lines[part_size : part_size * 2]
    part2_text = ""
    for line in part2_lines:
        if len(part2_text) + len(line) > chars_per_part: break
        part2_text += line + "\n"
    summary.append("--- 関係の中期 ---\n" + part2_text)
    
    # パート3: 後期
    part3_lines = text_lines[part_size * 2 :]
    part3_text = ""
    for line in part3_lines:
        if len(part3_text) + len(line) > chars_per_part: break
        part3_text += line + "\n"
    summary.append("--- 関係の後期 ---\n" + part3_text)

    return "\n\n".join(summary)



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

def build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, long_term_summary, trend, previous_data=None):
    # ★★★ ここからが重要 ★★★
    # キャラクターの「役割」と「名前」をセットで定義します
    character_map = {
        "1. 優しく包み込む、お姉さん系": ("優しく包み込むお姉さんタイプの鑑定師", "碧月（みつき）"),
        "2. ロジカルに鋭く分析する、専門家系": ("ロジカルに鋭く分析する専門家タイプの鑑定師", "詩音（しおん）"),
        "3. 星の言葉で語る、ミステリアスな占い師系": ("星の言葉で語るミステリアスな占い師", "セレスティア")
    }
    # character_mapから役割と名前を取り出します
    char_info, char_name = character_map.get(character, (character, "AI鑑定師"))
    # ★★★ ここまでを追加・修正 ★★★

    tone_instruction = {"癒し 100%": "とにかく優しく、温かく包み込むような言葉遣いで。否定的な表現は避け、常に希望を見出してください。", "癒し 50% × 論理 50%": "優しさと客観性のバランスを保ちながら、事実も伝えつつ励ましてください。", "冷静にロジカル": "感情に流されず、客観的なデータと論理的な分析を中心に伝えてください。"}
    
    # ↓↓↓ これで char_info と char_name が正しく使われます
    prompt = f"""あなたは【{char_info}】の**{char_name}**です。導入部分で「こんにちは、鑑定師の{char_name}よ。」のように、必ず自分の名前をはっきりと名乗ってから会話を始めてください。ユーザーは【{tone}】のスタイルでの鑑定を望んでいます。{tone_instruction.get(tone, '')} このトーンと言葉遣いを、出力の最後まで徹底して維持してください。**重要: あなたは鑑定の最初から最後まで、キャラクターの口調・語尾・ニュアンスを完全に一定に保ち、文体が途中で絶対に変化しないよう、強く意識してください。**以下のデータを基に、単なる占いではない、心理分析に基づいた詳細な「恋の心理レポート」を作成してください。

# ユーザー情報
- ユーザー名: {your_name}
- 相手の名前: {partner_name}
- ユーザーの悩み: {counseling_text}
"""
    comparison_instruction = ""
    if previous_data:
        prev_score = previous_data.get('pulse_score', 0)
        prompt += f"""
# 過去の鑑定データ
- 前回の鑑定日: {previous_data.get('date', '不明')}
- **前回の脈あり度: {prev_score}%**
- 前回の鑑定サマリー: {previous_data.get('summary', 'なし')}

**【最重要】過去データに関する指示**:
- あなたはユーザーの{your_name}さんを覚えています。導入文で「{your_name}さん、こんにちは。前回の鑑定から少し時間が経ちましたね」のように、再会を喜ぶ自然な語り口で始めてください。
- **前回の脈あり度は「{prev_score}%」でした。この数値を絶対に創作せず、そのまま使用してください。**
"""
        comparison_instruction = f"""   **【前回との比較】**: 前回の鑑定では脈あり度が **{prev_score}%** でした。今回の結果と比較し、「前回の{prev_score}%から、今回は〇〇%へと変化しました」のように、数値を正確に使って必ず言及してください。"""
    prompt += f"""
# 基本データ分析
- 会話の温度グラフの傾向: {trend}

# ★★★ 変更点2: AIへの指示に「関係性の歴史」の項目を追加 ★★★
- 【関係性の歴史（全期間のダイジェスト）】:
{long_term_summary}

- 【直近の詳細な会話（分析対象）】:
{messages_summary}


# AIによる深層分析依頼
1. **感情の波の分析**: トーク履歴全体を通して、「ポジティブ」「ネガティブ」な感情表現は、それぞれどのような傾向で推移していますか？
2. **脈ありシグナルのスコア化**: 以下の項目を0〜10点で評価し、総合的な「脈あり度」をパーセンテージで算出してください。 (質問返しの積極性, ポジティブな絵文字・表現の使用頻度, 返信間隔の安定性・速さ, 相手からの賞賛・共感の言葉, 会話を広げようとする意図)
   **【絶対厳守】出力形式:** 以下の形式を絶対に守ってください。他の表現は一切使わず、数値は太字（**）にしないでください。
   【総合脈あり度】: 80%
   （上記の例のように、必ず「【総合脈あり度】: 数字%」の形式で出力してください）
{comparison_instruction}
   - なぜそのスコアになったのか、根拠を優しく解説してください。
3. **相手の"隠れ心理"抽出**: 会話の中から、相手が特に「大切にしている価値観」や「本音だと感じられる発言」を3つ抜粋し、解説してください。
4. **コミュニケーション相性診断**: 二人の言葉遣いや会話のテンポから、コミュニケーションのスタイルを分析し、「〇〇で繋がりを深めるタイプ」といった形で相性を診断してください。
5. **「最高の瞬間」ハイライト**: このトーク履歴の中で、二人の心が最も通い合ったと感じられる瞬間を1つ選び出し、その時の会話の素晴らしい点を解説してください。
6. **恋の未来予測**: これまでの会話データと心理分析に基づき、二人の関係性がポジティブに進展するための、心理学的な観点からの**優しい未来予測**を記述してください。
7. **恋の処方箋・アクションチェックリスト**: 以下の4項目について、具体的かつ実践的なアドバイスを箇条書きで作成してください。(今日送ると効果的なメッセージ例:（★★1つにつき80文字以内で、最大3つ★★）, 相手のタイプ別・心に刺さるキーワード, 今は控えるべきNG行動, 次回鑑定のおすすめタイミング)

# 最終出力
上記の分析結果をすべて含め、以下の構成でレポートを作成してください。
- 導入文, **恋の温度グラフの解説**, 総合脈あり度と、その理由, 恋の心理レポート, 「最高の瞬間」の振り返り, **恋の未来予測**, **恋の処方箋・アクションチェックリスト**, ユーザーへのケアメッセージ, 最後に、ユーザーを温かく励ます一言
重要: 必ず日本語で、{your_name}さんに語りかけるような親しみやすい文体で書いてください。出力は最大8000文字以内に抑えてください。
"""
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
    patterns = [r'【総合脈あり度】\s*[:：]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])', r'総合脈あり度\s*[:：]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])', r'脈あり度[はが]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])', r'(\d{1,3})\s*[%％パーセント](?:くらい|ほど|程度)?(?:の)?(?:脈あり|可能性)', r'スコア[はが]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])']
    for pattern in patterns:
        match = re.search(pattern, ai_response, flags=re.DOTALL | re.IGNORECASE)
        if match:
            try:
                score = int(match.group(1))
                if 0 <= score <= 100: return score
            except (ValueError, IndexError): continue
    st.warning("⚠️ AIの応答から脈あり度のパーセンテージを自動で読み取れませんでした。")
    return 0

def extract_summary_from_response(ai_response):
    lines, summary_parts = ai_response.split('\n'), []
    for line in lines:
        if '脈あり度' in line or '総合' in line:
            summary_parts.append(line.strip())
            break
    for line in lines:
        clean_line = line.strip()
        if clean_line and not clean_line.startswith('#') and len(clean_line) > 15:
            summary_parts.append(clean_line)
            if len(" ".join(summary_parts)) > 150: break
    summary = " ".join(summary_parts)
    if not summary: return ai_response[:150] + '...'
    return summary[:200] + '...' if len(summary) > 200 else summary

class MyPDF(FPDF):
    def footer(self): pass

def create_pdf(ai_response_text, graph_img_buffer, character):
    ai_response_text = re.sub(r'[\U0001F300-\U0001F9FF]+', '', ai_response_text)
    ai_response_text = re.sub(r'[\u2600-\u26FF\u2700-\u27BF\uFE0F]+', '', ai_response_text)
    pdf = MyPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(left=20, top=20, right=20)
    font_path = get_japanese_font()
    font_available = font_path is not None
    if font_available:
        try:
            pdf.add_font('Japanese', '', font_path)
            pdf.add_font('Japanese', 'B', font_path)
        except Exception: font_available = False
    font_name = 'Japanese' if font_available else 'Arial'
    pdf.add_page()
    color_map = {"1. 優しく包み込む、お姉さん系": (255, 182, 193), "2. ロジカルに鋭く分析する、専門家系": (135, 206, 235), "3. 星の言葉で語る、ミステリアスな占い師系": (186, 85, 211)}
    theme_color = color_map.get(character, (200, 200, 200))
    pdf.set_fill_color(*theme_color)
    pdf.rect(0, 0, 210, 297, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(110)
    pdf.set_font(font_name, 'B', 26)
    pdf.cell(0, 15, "恋のオラクル AI恋星譚", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font(font_name, '', 14)
    pdf.cell(0, 10, "- 心の羅針盤 Edition -", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(40)
    pdf.set_font(font_name, '', 11)
    pdf.cell(0, 10, f"鑑定日: {datetime.now().strftime('%Y年%m月%d日')}", align='C')
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)
    LINE_HEIGHT_NORMAL, LINE_HEIGHT_H2 = 8, 12
    lines = ai_response_text.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            pdf.ln(LINE_HEIGHT_NORMAL / 2)
            continue
        if line.startswith('###'):
            pdf.ln(LINE_HEIGHT_NORMAL)
            pdf.set_font(font_name, 'B', 16)
            pdf.multi_cell(0, LINE_HEIGHT_H2, line[4:].strip(), align='L')
            pdf.set_font(font_name, '', 11)
        else:
            parts = re.split(r'(\*\*.*?\*\*)', line)
            for part in parts:
                if not part: continue
                if part.startswith('**') and part.endswith('**'):
                    pdf.set_font(font_name, 'B', 11)
                    pdf.write(LINE_HEIGHT_NORMAL, part[2:-2])
                    pdf.set_font(font_name, '', 11)
                else:
                    pdf.write(LINE_HEIGHT_NORMAL, part)
            pdf.ln(LINE_HEIGHT_NORMAL)
    pdf.add_page()
    pdf.set_font(font_name, 'B', 15)
    pdf.cell(0, 12, "二人の恋の温度グラフ", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(8)
    graph_img_buffer.seek(0)
    pdf.image(graph_img_buffer, x=20, y=pdf.get_y(), w=170)
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-25)
    pdf.set_font(font_name, '', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 10, "本鑑定はAIによる心理分析です。", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 5, "あなたの恋を心から応援しています♡", align='C')
    return bytes(pdf.output())

# ---------------------------------------------------------------------
# --- 画面表示と実行ロジック ---
# ---------------------------------------------------------------------
def show_login_screen():
    st.header("ようこそ、鑑定の世界へ")
    user_id = st.text_input("BOOTHの購入者IDを入力してください", key="login_user_id")
    if st.button("認証する", key="login_button"):
        if user_id in VALID_USER_IDS:
            st.session_state.authenticated, st.session_state.user_id = True, user_id
            cookies["authenticated"], cookies["user_id"] = "True", user_id
            cookies.save(); st.rerun()
        else: st.error("認証に失敗しました。IDが正しいか確認してください。")

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



    # ★★★ ここからが【最終確定版】の実装です ★★★
    st.write("---")
    st.header("Step 2: トーク履歴を読み込む")

    # セッション状態（再実行しても消えない記憶領域）を初期化
    if "talk_data" not in st.session_state:
        st.session_state.talk_data = None

    tab1, tab2 = st.tabs(["📁 ファイルをアップロード", "📝 テキストを貼り付け"])

    # --- タブ1：ファイルアップロードの処理 ---
    with tab1:
        st.info("💡 PCでご利用の方や、ファイルを選択できる方はこちらが便利です。")
        uploaded_file = st.file_uploader(
            "LINEのトーク履歴ファイル（.txt）を選択してください。", type="txt",
            help="スマホでファイル選択がうまくいかない場合は、右の「テキストを貼り付け」タブをお試しください。"
        )
        if uploaded_file is not None:
            # ファイルがアップロードされたら、すぐにセッション状態に保存
            try:
                raw_data = uploaded_file.getvalue()
                encodings = ['utf-8', 'utf-8-sig', 'shift_jis', 'cp932']
                decoded_data = None
                for encoding in encodings:
                    try:
                        decoded_data = raw_data.decode(encoding)
                        st.caption(f"（ファイルを{encoding}で読み込みました）")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if decoded_data:
                    # ★重要★ セッション状態にデータを保存
                    st.session_state.talk_data = decoded_data
                    # アップロードされたファイルをクリアするため、ここで一度リセット
                    
                else:
                    st.error("❌ ファイルの文字コードを判定できませんでした。")
            except Exception:
                st.error("❌ ファイルの読み込み中にエラーが発生しました。")

    # --- タブ2：テキスト貼り付けの処理 ---
    with tab2:
        st.info("📱 **スマホの方や、ファイルでのアップロードがうまくいかない方はこちらをご利用ください。**")
        st.markdown("1. LINEのトーク履歴をコピーし、下の欄に貼り付けてください。")
        
        text_input = st.text_area(
            "コピーしたトーク履歴をここに貼り付けます", height=250, key="text_area_content"
        )
        
        if st.button("📝 この内容で読み込む", key="text_submit_button"):
            if text_input and text_input.strip():
                # ★重要★ ボタンが押されたらセッション状態にデータを保存
                st.session_state.talk_data = text_input
                st.rerun() # データを確実に反映させるために再実行
            else:
                st.warning("⚠️ トーク履歴のデータが貼り付けられていません。")
                # もし空でボタンが押されたら、記憶していたデータも消す
                st.session_state.talk_data = None


    # --- ここからが共通の処理 ---
    # ★重要★ セッション状態にデータがあるかどうかをチェック
    if st.session_state.talk_data:
        # セッションからデータを取得（これで「鑑定」ボタンを押してもデータが消えない）
        talk_data = st.session_state.talk_data
        
        messages, _ = parse_line_chat(talk_data)

        if not messages:
            st.warning("⚠️ 有効なメッセージが見つかりませんでした。")
        else:
            st.success(f"✅ {len(messages)}件のメッセージを読み込みました！鑑定を開始してください。")
            with st.expander("🔍 読み込まれた内容の先頭部分を確認"):
                st.code('\n'.join(talk_data.strip().split('\n')[:15]))
            
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
                        user_override_model = cookies.get("user_custom_model")
                        default_model = st.session_state.get("selected_model") or cookies.get("selected_model") or "models/gemini-2.5-flash"
                        model_name_to_use = user_override_model if user_override_model else default_model
                        st.caption(f"（使用AIモデル: {model_name_to_use}）")
                        model = genai.GenerativeModel(model_name_to_use)
                        messages_summary = smart_extract_text(messages, max_chars=8000)
                        long_term_summary = create_long_term_summary(messages, max_chars=4000)
                        final_prompt = build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, long_term_summary, trend, previous_data)
                        safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                        response = model.generate_content(final_prompt, generation_config={"max_output_tokens": 8192, "temperature": 0.75}, safety_settings=safety_settings)
                        ai_response_text = ""
                        try: ai_response_text = response.text
                        except Exception:
                            if hasattr(response, "parts") and response.parts: ai_response_text = response.parts[0].text
                        if not ai_response_text:
                            st.error("💫 AIからの応答がブロックされたか、内容が空でした。")
                            if hasattr(response, 'prompt_feedback'): st.write("🔍 **AIからのフィードバック:**"); st.code(f"{response.prompt_feedback}")
                            return
                        st.markdown("---"); st.markdown(ai_response_text)
                        pulse_score = extract_pulse_score_from_response(ai_response_text)
                        st.info(f"🔍 抽出された脈あり度: {pulse_score}% (この数値が保存されます)")
                        summary = extract_summary_from_response(ai_response_text)
                        save_diagnosis_result(st.session_state.user_id, partner_name, pulse_score, summary)
                        if previous_data: st.info(f"📊 比較: 前回の脈あり度 {previous_data.get('pulse_score', 0)}% → 今回抽出された脈あり度 {pulse_score}%")
                        pdf_data = create_pdf(ai_response_text, img_buffer, character)
                        st.download_button("📄 鑑定書をPDFでダウンロード", pdf_data, f"恋の鑑定書.pdf", "application/pdf", use_container_width=True)
                    except Exception:
                        st.error("💫 ごめんなさい、星との交信が少し途切れちゃったみたいです...")
                        with st.expander("🔧 詳細"): st.code(f"{traceback.format_exc()}")
                        
    # ★★★【設定セクション】は、このブロックの外にあるので、変更の影響を受けません ★★★
    st.write("---")
    
    # ★★★【設定セクション改善】★★★
    st.write("---")
    # 1つの「設定」ブロックにすべてをまとめる
    with st.expander("⚙️ 設定", expanded=False):
        
        # 1. 予備AIモデル設定
        st.write("### 予備AIモデル設定")
        st.info("通常はこの設定は不要です。将来、新しいモデルが発表されたり、通常使用しているモデルでエラーが発生するようになった場合に新しいモデル名を設定してください。通常、放置してくださってOKです。")

        default_model = st.session_state.get("selected_model") or cookies.get("selected_model", "（自動選択）")
        user_override_model = cookies.get("user_custom_model")
        
        st.write(f"**通常使用するモデル:** **`{default_model}`**")
        
        if user_override_model:
            st.warning(f"現在、予備設定が有効です。こちらのモデルが優先されます: `{user_override_model}`")
        
        new_model_name = st.text_input("予備のモデル名を入力", placeholder="例: models/gemini-pro-latest", help="空のまま保存すると、予備設定がクリアされ自動選択モードに戻ります。")

        if st.button("予備設定を保存", key="model_test_button"):
            if new_model_name:
                is_valid, message = test_model_name(st.session_state.api_key, new_model_name)
                if is_valid:
                    cookies["user_custom_model"] = new_model_name
                    cookies.save()
                    st.success(message + " 予備設定を保存しました。")
                    time.sleep(1); st.rerun()
                else:
                    st.error(message)
            else:
                cookies["user_custom_model"] = ""
                cookies.save()
                st.success("✅ 予備設定をクリアしました。通常の自動選択モデルを使用します。")
                time.sleep(1); st.rerun()
        
        st.write("---")

        # 2. アプリ情報と管理者メニュー
        st.write("### アプリ情報")
        if st.session_state.user_id == "charo1118": 
            st.subheader("👑 管理者メニュー")
            if st.button("🔄 ユーザーリストを再読み込み"):
                st.cache_data.clear()
                st.success("✅ ユーザーリストのキャッシュをクリアしました。")
                time.sleep(1)
                st.rerun()

        st.write("---")

        # 3. ログアウト機能
        st.write("### ログアウト")
        st.caption("ログアウトすると、認証IDの入力画面に戻ります。")
        if st.button("🔓 ログアウトする", type="secondary", use_container_width=True, key="logout_button"):
            # (ログアウト処理の中身は変更なし)
            cookies["authenticated"] = "False"; cookies["api_key"] = ""; cookies["user_id"] = ""; cookies["selected_model"] = ""; cookies.save()
            st.session_state.authenticated = False; st.session_state.api_key = None; st.session_state.user_id = None
            keys_to_del = ["selected_model", "session_initialized"]; [st.session_state.pop(key, None) for key in keys_to_del]
            st.success("✅ ログアウトしました。"); st.info("🔄 ログイン画面に戻ります..."); st.balloons()
            time.sleep(2); st.rerun()


# --- メインの実行ロジック ---
st.title("🌙 恋のオラクル AI恋星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")

# ★★★【メインロジック堅牢化】★★★
# セッション情報の初期化とCookieからの復元を、画面表示の直前に集約
if "authenticated" not in st.session_state:
    st.session_state.authenticated = cookies.get("authenticated", "False") == "True"
if "api_key" not in st.session_state:
    st.session_state.api_key = cookies.get("api_key", None)
if "user_id" not in st.session_state:
    st.session_state.user_id = cookies.get("user_id", None)

# 認証状態に応じて画面を表示
if not st.session_state.authenticated:
    show_login_screen()
elif not st.session_state.api_key:
    show_api_key_screen()
else:
    show_main_app()
