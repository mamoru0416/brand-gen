# pages/create_new_story.py (修正版)

import streamlit as st
import google.generativeai as genai
import qrcode
from io import BytesIO
import database
import json
import re

# -----------------------------------------------------------------
#  関数: ベースURLの取得 (QRコード用)
# -----------------------------------------------------------------
def get_base_url():
    """
    アプリの公開URLを取得する。
    1. st.secrets["BASE_URL"] があればそれを使う
    2. なければサイドバーでユーザーに入力させる
    """
    if "BASE_URL" in st.secrets:
        return st.secrets["BASE_URL"].rstrip("/")
    
    # ユーザー入力 (セッションステートで保持)
    if "user_base_url" not in st.session_state:
        st.session_state.user_base_url = "https://share.streamlit.io/..."
        
    with st.sidebar:
        st.divider()
        st.caption("QRコード設定")
        url_input = st.text_input(
            "アプリの公開URL", 
            value=st.session_state.user_base_url,
            help="Streamlit Community CloudのURLを入力してください（末尾の / は不要）"
        )
        if url_input:
            st.session_state.user_base_url = url_input.rstrip("/")
            
    return st.session_state.user_base_url

# -----------------------------------------------------------------
#  APIキー設定 (Gemini)
# -----------------------------------------------------------------
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"], transport='rest')
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error("Google AI APIキーが設定されていません。st.secretsを確認してください。")
    st.stop()

# -----------------------------------------------------------------
#  再開モード (履歴の読み込み)
# -----------------------------------------------------------------
params = st.query_params
if "resume_id" in params and "messages_loaded" not in st.session_state:
    resume_id = params["resume_id"]
    story_data = database.get_story(resume_id)
    
    if story_data and "chat_history" in story_data:
        try:
            loaded_messages = json.loads(story_data["chat_history"])
            st.session_state.messages = loaded_messages
            st.session_state.final_story_title = story_data.get("title", "")
            st.session_state.final_story_body = story_data.get("body", "")
            st.session_state.chat_history_json = story_data["chat_history"]
            st.session_state.saved_story_id = resume_id
            st.session_state.messages_loaded = True 
            st.info(f"過去のヒアリング履歴を読み込みました (ID: {resume_id})")
        except Exception as e:
            st.error(f"履歴の読み込み中にエラーが発生しました: {e}")
            
    st.query_params.clear()

# -----------------------------------------------------------------
#  セッションステートの初期化
# -----------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "final_story_title" not in st.session_state:
    st.session_state.final_story_title = ""
if "final_story_body" not in st.session_state:
    st.session_state.final_story_body = ""
if "chat_history_json" not in st.session_state:
    st.session_state.chat_history_json = ""
if "saved_story_id" not in st.session_state:
    st.session_state.saved_story_id = None

# -----------------------------------------------------------------
#  UI (3つのタブ)
# -----------------------------------------------------------------
st.title("新しいブランドストーリーを作成します")

tab1, tab2, tab3 = st.tabs(["ステップ1: AIヒアリング", "ステップ2: ストーリー生成", "ステップ3: 保存とQRコード発行"])

# --- タブ1: AIヒアリング (F-001) ---
with tab1:
    st.header("AIヒアリング 🎤")
    st.markdown("生産物への「こだわり」や「情熱」をAIに話してみてください。")

    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    if prompt := st.chat_input("あなたの想いをどうぞ..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # プロンプト (変更なし)
        interviewer_prompt = """
            # Role
            あなたは、第一次産業（農業・漁業・畜産など）の生産者に寄り添う、親しみやすく聞き上手な「ライター」です。
            ITに詳しくない高齢の生産者でも、あなたとチャットをするだけで安心して自分の想いを話せるような、温かい人格（孫や親しい若者のような口調）で振る舞ってください。

            # Goal
            生産者との対話を通じて、商品に込められた「想い」「こだわり」「苦労話」、そして「誰に食べて（使って）ほしいか」を引き出し、後続のストーリー作成AIが魅力的な記事を書くための十分な情報を収集することです。

            # Constraints
            - **口調**: 敬語は崩しすぎず、かつ親しみを込めて。「〜ですね」「〜なんですか！」など、共感を示す相槌を多用する。専門用語は一切使わない。
            - **質問の仕方**: 一度に複数の質問をしない。必ず「一問一答」形式で、会話のキャッチボールを行う。
            - **進行管理**: ユーザーが答えに詰まったら、具体的な例を出して誘導する。
            - **終了条件**: 必要な情報（商品、こだわり、ターゲット、想い）が揃ったと判断したら、会話を終了し、これまでの内容を要約して確認する。
            
            # Conversation History
            [履歴]
            {chat_history}
        """
        
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        full_prompt = interviewer_prompt.format(chat_history=history_text)

        with st.spinner("AIが応答を考えています..."):
            try:
                response = model.generate_content(full_prompt)
                ai_response = response.text
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                st.rerun()
            except Exception as e:
                st.error(f"AIとの通信でエラー: {e}")

# --- タブ2: ストーリー生成 (F-002: 改良版) ---
with tab2:
    st.header("ブランドストーリー生成 ✍️")
    
    if not st.session_state.messages:
        st.warning("まず「ステップ1: AIヒアリング」でAIと対話してください。")
    else:
        if st.button("このヒアリング内容からストーリーを生成する"):
            # プロンプト (HTMLでの出力を意識させるように少し調整しても良いが、今回はMarkdownのまま整形)
            storyteller_prompt = """
                # Role
                あなたは、心を揺さぶる文章を書く「トップブランド・ストーリーテラー」です。
                
                # Format
                出力は以下のMarkdown形式のみを行ってください。余計な挨拶は不要です。
                
                ## [タイトル]
                [本文]
                
                # Constraints
                - 本文は400〜600文字。
                - 情緒的で、生産者の人柄が伝わる物語調。
                
                # Chat History
                {chat_history}
            """
            
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            full_prompt = storyteller_prompt.format(chat_history=history_text)

            with st.spinner("プロのストーリーテラーが執筆中です..."):
                try:
                    response = model.generate_content(full_prompt)
                    raw_story_text = response.text
                    
                    # タイトルと本文の抽出 (正規表現)
                    match = re.search(r'##\s*(.*?)\n(.*)', raw_story_text, re.DOTALL)
                    
                    if match:
                        title = match.group(1).strip().replace("**", "")
                        body = match.group(2).strip()
                        
                        st.session_state.final_story_title = title
                        st.session_state.final_story_body = body
                        st.session_state.chat_history_json = json.dumps(st.session_state.messages)
                        
                        st.success("ストーリーが生成されました！")
                        if "messages_loaded" not in st.session_state:
                            st.session_state.saved_story_id = None 
                    else:
                        # 抽出失敗時のフォールバック
                        st.session_state.final_story_title = "生成されたストーリー"
                        st.session_state.final_story_body = raw_story_text
                        st.warning("形式の自動解析に失敗しましたが、内容は以下の通りです。")

                except Exception as e:
                    st.error(f"生成エラー: {e}")

    # --- モバイルプレビュー画面 ---
    if st.session_state.final_story_body:
        st.divider()
        st.subheader("📱 ストーリープレビュー")
        
        col_preview, col_dummy = st.columns([1, 2])
        
        with col_preview:
            # スマホっぽい枠の中にHTMLを表示
            preview_html = f"""
            <div style="
                width: 300px; 
                height: 550px; 
                border: 12px solid #333; 
                border-radius: 30px; 
                background: white; 
                overflow-y: scroll;
                margin: 0 auto;
                box-shadow: 0 10px 20px rgba(0,0,0,0.3);
                position: relative;
            ">
                <!-- カメラ部分のダミー -->
                <div style="
                    position: sticky; top: 0; 
                    width: 100%; height: 20px; 
                    background: #f1f1f1; 
                    z-index: 10; border-bottom: 1px solid #ddd;
                    text-align: center; color: #aaa; font-size: 10px; line-height: 20px;
                ">Brand Story View</div>
                
                <div style="padding: 20px; font-family: sans-serif; color: #333;">
                    <h3 style="text-align: center; margin-bottom: 15px; font-size: 18px;">
                        {st.session_state.final_story_title}
                    </h3>
                    <div style="font-size: 12px; line-height: 1.6; text-align: justify; white-space: pre-wrap;">
                        {st.session_state.final_story_body}
                    </div>
                </div>
            </div>
            """
            st.components.v1.html(preview_html, height=600)


# --- タブ3: 保存とQRコード発行 (F-003 & F-004: 改良版) ---
with tab3:
    st.header("保存とQRコード発行 📱")
    
    if not st.session_state.final_story_body:
        st.warning("まず「ステップ2: ストーリー生成」を完了してください。")
    else:
        st.markdown(f"**タイトル:** {st.session_state.final_story_title}")
        
        is_update = st.session_state.saved_story_id is not None
        button_label = "上書き保存" if is_update else "新規保存"

        if st.button(button_label, type="primary"):
            with st.spinner("保存中..."):
                if is_update:
                    success = database.update_story(
                        story_id=st.session_state.saved_story_id,
                        title=st.session_state.final_story_title,
                        body=st.session_state.final_story_body,
                        chat_history=st.session_state.chat_history_json
                    )
                    if success: st.success("保存完了！")
                else:
                    new_id = database.save_story(
                        title=st.session_state.final_story_title,
                        body=st.session_state.final_story_body,
                        chat_history=st.session_state.chat_history_json
                    )
                    if new_id:
                        st.session_state.saved_story_id = new_id
                        st.success("保存完了！")

        # QRコード発行
        if st.session_state.saved_story_id:
            st.divider()
            story_id = st.session_state.saved_story_id
            
            # 修正: 動的にベースURLを取得
            base_url = get_base_url()
            final_url = f"{base_url}/?story_id={story_id}"
            
            col_qr, col_info = st.columns([1, 2])
            
            with col_qr:
                qr = qrcode.QRCode(version=1, box_size=10, border=2)
                qr.add_data(final_url) 
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")

                buf = BytesIO()
                img.save(buf, format="PNG")
                st.image(buf, caption="読み込んで確認", width=200)

            with col_info:
                st.success("QRコードが発行されました！")
                st.markdown(f"**リンク先URL:**\n\n`{final_url}`")
                st.warning("※ QRコードが正しく機能しない場合は、サイドバーで「アプリの公開URL」を確認・修正してください。")