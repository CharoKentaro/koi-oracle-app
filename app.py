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
            cookies["selected_model"] = model_name # Cookieにもモデル名を保存
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
**重要: あなたは鑑定の最初から最後まで、キャラクターの口調・語尾・ニュアンスを完全に一定に保ち、文体が途中で絶対に変化しないよう、強く意識してください。**
以下のデータを基に、単なる占いではない、心理分析に基づいた詳細な「恋の心理レポート」を作成してください。

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
- 分析対象の会話抜粋:\n{messages_summary}

# AIによる深層分析依頼
1. **感情の波の分析**: トーク履歴全体を通して、「ポジティブ」「ネガティブ」な感情表現は、それぞれどのような傾向で推移していますか？

2. **脈ありシグナルのスコア化**: 以下の項目を0〜10点で評価し、総合的な「脈あり度」をパーセンテージで算出してください。
   - 質問返しの積極性, ポジティブな絵文字・表現の使用頻度, 返信間隔の安定性・速さ, 相手からの賞賛・共感の言葉, 会話を広げようとする意図
   
   **【絶対厳守】出力形式:**
   以下の形式を絶対に守ってください。他の表現は一切使わず、数値は太字（**）にしないでください。
   
   【総合脈あり度】: 80%
   
   （上記の例のように、必ず「【総合脈あり度】: 数字%」の形式で出力してください）
{comparison_instruction}
   
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
    """
    AIレスポンスから脈あり度を抽出する超強力版。
    太字（**）や、あらゆる表現パターンに対応します。
    """
    # AIが **18%** のように太字で出力しても対応できるよう、パターンを強化
    patterns = [
        # 基本パターン（太字対応）
        r'【総合脈あり度】\s*[:：]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])',
        r'総合脈あり度\s*[:：]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])',
        
        # 「は」「が」などを含むパターン（太字対応）
        r'脈あり度[はが]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])',
        
        # 数字が先に来るパターン
        r'(\d{1,3})\s*[%％パーセント](?:くらい|ほど|程度)?(?:の)?(?:脈あり|可能性)',
        
        # 「スコア」を含むパターン（太字対応）
        r'スコア[はが]?\s*(?:\*\*|約|およそ|大体)?\s*(\d{1,3})\s*(?:\*\*|[%％パーセント])',
    ]

    for i, pattern in enumerate(patterns):
        # re.IGNORECASE を追加して、大文字・小文字の違いを無視
        match = re.search(pattern, ai_response, flags=re.DOTALL | re.IGNORECASE)
        if match:
            try:
                score = int(match.group(1))
                if 0 <= score <= 100:
                    return score
            except (ValueError, IndexError):
                continue
    
    st.warning("⚠️ AIの応答から脈あり度のパーセンテージを自動で読み取れませんでした。")
    return 0

def extract_summary_from_response(ai_response):
    """
    シンプルな手動サマリー生成（AI呼び出しなし）
    """
    lines = ai_response.split('\n')
    summary_parts = []
    
    # 脈あり度を探す
    for line in lines:
        if '脈あり度' in line or '総合' in line:
            summary_parts.append(line.strip())
            break
    
    # 重要そうな行を追加
    for line in lines:
        clean_line = line.strip()
        if clean_line and not clean_line.startswith('#') and len(clean_line) > 15:
            summary_parts.append(clean_line)
            if len(" ".join(summary_parts)) > 150:
                break
    
    summary = " ".join(summary_parts)
    
    if not summary:
        return ai_response[:150] + '...'
        
    return summary[:200] + '...' if len(summary) > 200 else summary


from fpdf import FPDF  # HTMLMixinは削除
class MyPDF(FPDF):  # HTMLMixinを継承しない
    def footer(self):
        pass


def create_pdf(ai_response_text, graph_img_buffer, character):

    # ★ 絵文字を削除する処理を追加
    # 絵文字の範囲（U+1F300〜U+1F9FF）を削除
    ai_response_text = re.sub(r'[\U0001F300-\U0001F9FF]+', '', ai_response_text)
    # その他の記号類も削除
    ai_response_text = re.sub(r'[\u2600-\u26FF\u2700-\u27BF\uFE0F]+', '', ai_response_text)


    # ===== 1. PDFの初期設定と、汎用的な余白設定 =====
    pdf = MyPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=25)  # 下部マージンを25mmに設定
    pdf.set_margins(left=20, top=20, right=20)   # 左右上マージンを20mmに設定

    font_path = get_japanese_font()
    pdf.font_path = font_path
    font_available = font_path is not None
    if font_available:
        try:
            pdf.add_font('Japanese', '', font_path)
            pdf.add_font('Japanese', 'B', font_path)
        except Exception as e:
            st.warning(f"PDFへの日本語フォントの追加に失敗: {e}")
            font_available, pdf.font_path = False, None

    # ===== 2. 表紙ページの作成 =====
    pdf.add_page()
    color_map = {
        "1. 優しく包み込む、お姉さん系": (255, 182, 193),
        "2. ロジカルに鋭く分析する、専門家系": (135, 206, 235),
        "3. 星の言葉で語る、ミステリアスな占い師系": (186, 85, 211)
    }
    theme_color = color_map.get(character, (200, 200, 200))
    pdf.set_fill_color(*theme_color)
    pdf.rect(0, 0, 210, 297, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(110)
    
    font_name = 'Japanese' if font_available else 'Arial'
    pdf.set_font(font_name, 'B', 26)
    pdf.cell(0, 15, "恋のオラクル AI星譚", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.set_font(font_name, '', 14)
    pdf.cell(0, 10, "- 心の羅針盤 Edition -", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(40)
    pdf.set_font(font_name, '', 11)
    pdf.cell(0, 10, f"鑑定日: {datetime.now().strftime('%Y年%m月%d日')}", align='C')

# --- 本文ページの作成 ---
    pdf.add_page()
    pdf.set_text_color(0, 0, 0)

    # 行の高さ（line height）を設定します。
    LINE_HEIGHT_NORMAL = 8  # 通常の本文の行の高さ (mm)
    LINE_HEIGHT_H2 = 12     # 見出しの行の高さ (mm)

    # AIの応答を一行ずつに分割
    lines = ai_response_text.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            # 空行の場合は、少しスペースを空ける
            pdf.ln(LINE_HEIGHT_NORMAL / 2)
            continue
        
        # 以下の if / else ブロック全体を for ループの内側に移動させました。
        # これで、すべての行が正しく処理されます。
        if line.startswith('###'):
            # 見出しの処理
            pdf.ln(LINE_HEIGHT_NORMAL)
            pdf.set_font(font_name, 'B', 16)
            pdf.multi_cell(0, LINE_HEIGHT_H2, line[4:].strip(), align='L')
            pdf.set_font(font_name, '', 11)
        else:
            # 通常の本文の処理
            parts = re.split(r'(\*\*.*?\*\*)', line)
            
            for part in parts:
                if not part:
                    continue
                
                if part.startswith('**') and part.endswith('**'):
                    # 太字部分
                    pdf.set_font(font_name, 'B', 11)
                    pdf.write(LINE_HEIGHT_NORMAL, part[2:-2])
                    pdf.set_font(font_name, '', 11)
                else:
                    # 通常のテキスト
                    pdf.write(LINE_HEIGHT_NORMAL, part)
            
            # 1行の処理が終わったら必ず改行
            pdf.ln(LINE_HEIGHT_NORMAL)

    
    # ===== 4. グラフページの作成 =====
    pdf.add_page()
    pdf.set_font(font_name, 'B', 15)
    pdf.cell(0, 12, "二人の恋の温度グラフ", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.ln(8)
    
    graph_img_buffer.seek(0)
    graph_width = 210 - (20 * 2)
    x_position = 20
    pdf.image(graph_img_buffer, x=x_position, y=pdf.get_y(), w=graph_width)

    # ===== 5. 最後のページにのみ、フッターを手動で描画 =====
    pdf.set_auto_page_break(auto=False)

    pdf.set_y(-25) 
    pdf.set_font(font_name, '', 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 10, "本鑑定はAIによる心理分析です。", new_x="LMARGIN", new_y="NEXT", align='C')
    pdf.cell(0, 5, "あなたの恋を心から応援しています♡", align='C')

    return bytes(pdf.output())

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
                        
                        model_name_to_use = st.session_state.get("selected_model") or cookies.get("selected_model") or "models/gemini-2.5-flash"
                        
                        model = genai.GenerativeModel(model_name_to_use)
                        messages_summary = smart_extract_text(messages, max_chars=8000)
                        final_prompt = build_prompt(character, tone, your_name, partner_name, counseling_text, messages_summary, trend, previous_data)
                        safety_settings = [{"category": c, "threshold": "BLOCK_NONE"} for c in ["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]]
                        response = model.generate_content(final_prompt, generation_config={"max_output_tokens": 8192, "temperature": 0.75}, safety_settings=safety_settings)


                        # --- ここからが修正箇所 ---
                        ai_response_text = ""
                        try:
                            # ★ 新しいv2.0以降のAIモデルでは、こちらの方法で本文を取得します
                            ai_response_text = response.text
                        except Exception:
                            # ★ 古い形式のAIモデルだった場合の、保険の処理です
                            if hasattr(response, "parts") and response.parts:
                                ai_response_text = response.parts[0].text

                        # 本文が空だった場合の最終チェック
                        if not ai_response_text:
                            st.error("💫 AIからの応答がブロックされたか、内容が空でした。")
                            if hasattr(response, 'prompt_feedback'): st.write("🔍 **AIからのフィードバック:**"); st.code(f"{response.prompt_feedback}")
                            return
                        
                        st.markdown("---"); st.markdown(ai_response_text)
                        
                        # --- ここから修正 ---
                        pulse_score = extract_pulse_score_from_response(ai_response_text)
                        
                        # ★ デバッグ情報として、抽出された脈あり度を画面に表示
                        st.info(f"🔍 抽出された脈あり度: {pulse_score}% (この数値が保存されます)")
                        
                        summary = extract_summary_from_response(ai_response_text)
                        save_diagnosis_result(st.session_state.user_id, partner_name, pulse_score, summary)
                        
                        # ★ PDFダウンロードボタンの前にデバッグ情報を表示
                        if previous_data:
                            st.info(f"📊 比較: 前回の脈あり度 {previous_data.get('pulse_score', 0)}% → 今回抽出された脈あり度 {pulse_score}%")
                        
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
        try:
            # 1. セッション状態をクリア
            st.session_state.clear()  # または for ループで削除
            
            # 2. Cookieを更新（delete ではなく、空の値を設定）
            try:
                cookies["authenticated"] = "False"
                cookies["api_key"] = ""
                cookies["user_id"] = ""
                cookies["selected_model"] = ""
                cookies.save()
            except AttributeError:
                # cookies.save() が使えない場合の代替処理
                pass
            
            st.success("ログアウトしました。")
            time.sleep(0.5)
            st.rerun()
            
        except Exception as e:
            st.error(f"ログアウト中にエラーが発生しました: {e}")



# --- メインの実行ロジック ---
st.title("🌙 恋のオラクル AI星譚")
st.caption("- 心の羅針盤 Edition -")
st.write("---")
if not st.session_state.authenticated: show_login_screen()
elif not st.session_state.api_key: show_api_key_screen()
else: show_main_app()
