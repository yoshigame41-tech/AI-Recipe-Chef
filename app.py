import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import google.genai as genai
from google.genai.errors import APIError
from google.genai import types 

# .envファイルから環境変数をロード
load_dotenv() 

app = Flask(__name__)

# チャットの履歴を保存するためのリスト
chat_history = [] 

# --- Gemini APIクライアントの初期化 ---
client = None
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        client = genai.Client()
    else:
        print("警告: GEMINI_API_KEYが設定されていません。Gemini API関連の機能は動作しません。")
        
except Exception as e:
    print(f"Gemini APIクライアントの初期化に失敗しました: {e}")
    client = None

# --- レシピ生成のためのシステムプロンプト関数 ---
def create_initial_prompt(history):
    """
    AIに与える役割（System Prompt）を作成する関数。
    """
    
    base_instruction = """
    あなたは、栄養学の専門知識を持つ、独創的で効率的なレシピ考案AI「AIシェフ」です。
    ターゲットは主婦、学生であり、効率的かつ独創的なレシピを提供します。

    以下のルールに従ってユーザーと対話を進めてください。

    1. まず、ユーザーに「使いたい材料」「避けたい材料」「今の気分・目的（例：時短、節約、ヘルシー、こってり）」を順に尋ねてください。
    2. 上記の情報収集が完了したら、レシピを考案する直前に、「**何人分のレシピ**をご希望ですか？」と尋ねてください。
    3. すべての情報（材料、目的、人数）が揃ったら、その情報を含めてレシピを考案してください。
    4. 考案するレシピは、具体的な工程と分量を明確に示し、再現性を確保してください。
    5. レシピの最後には、**【豆知識・ポイント】**として、そのレシピに関する一言豆知識や料理のポイントを必ず添えてください。
    6. レシピ考案後、「このレシピでよろしいですか？」と確認をとり、対話を完了してください。
    """
    return base_instruction

# --- Gemini API呼び出し関数 ---
def generate_recipe_with_ai(system_prompt, history):
    """
    Google Gemini APIを呼び出し、応答を取得する関数
    """
    global client
    if client is None:
        return "サーバー設定エラー: AIクライアントが初期化されていません。APIキーを確認してください。"

    # 会話履歴をGemini SDKの Content オブジェクトに変換
    messages = []
    
    for message in history:
        role = "user" if message["role"] == "user" else "model"
        
        if message["role"] not in ["system"]: 
            
            content_object = types.Content(
                role=role,
                parts=[types.Part(text=message["content"])] 
            )
            messages.append(content_object)
            
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=messages,
            config={
                "temperature": 0.7, 
                "system_instruction": system_prompt 
            }
        )
        return response.text
    except APIError as e:
        print(f"Gemini APIエラー: {e}")
        return "Gemini APIとの通信中にエラーが発生しました。APIキーまたはネットワーク設定を確認してください。"

# --- Flaskルート設定 ---
@app.route('/')
def index():
    """初期画面の表示（ブラウザ再読み込み時にサーバー側の履歴をリセット）"""
    global chat_history
    chat_history = []
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_ai():
    """ユーザーからの入力を受け取り、AIにレシピ生成を依頼するエンドポイント"""
    user_input = request.json.get('message')
    
    chat_history.append({"role": "user", "content": user_input})

    system_prompt = create_initial_prompt(chat_history)
    
    ai_response_content = generate_recipe_with_ai(system_prompt, chat_history)

    chat_history.append({"role": "assistant", "content": ai_response_content})

    return jsonify({"message": ai_response_content})

# --- 編集機能用: 履歴を巻き戻すエンドポイント ---
@app.route('/undo_history', methods=['POST'])
def undo_history():
    """指定されたユーザーメッセージの直前まで履歴を巻き戻すエンドポイント"""
    global chat_history
    original_message_text = request.json.get('message')
    
    found_index = -1
    for i in reversed(range(len(chat_history))):
        message = chat_history[i]
        if message["role"] == "user" and message["content"] == original_message_text:
            found_index = i
            break
            
    if found_index != -1:
        # そのメッセージを含めず、それ以前の履歴のみを残す
        chat_history = chat_history[:found_index] 
        
    return jsonify({"status": "undo success", "new_history_length": len(chat_history)})


@app.route('/reset', methods=['POST'])
def reset_chat():
    """チャット履歴をリセットするエンドポイント"""
    global chat_history
    chat_history = []
    return jsonify({"status": "reset success"})

# ★新規追加: プライバシーポリシーのルート
@app.route('/privacy')
def privacy_policy():
    """プライバシーポリシーを表示するページ"""
    return render_template('privacy.html') 


# --- アプリケーションの実行 ---
if __name__ == '__main__':
    # スマホからのアクセスを許可するために host='0.0.0.0' を追加
    app.run(debug=True, host='0.0.0.0')