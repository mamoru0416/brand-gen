# pages/1_新しいストーリーを作成.py (ストーリー生成ページ)

import streamlit as st
import google.generativeai as genai
import qrcode
from io import BytesIO
import database  # 作成した database.py をインポート
import json

# -----------------------------------------------------------------
#  APIキー設定 (Gemini)
# -----------------------------------------------------------------
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-pro') 
except Exception as e:
    st.error("Google AI APIキーが設定されていません。st.secretsを確認してください。")
    st.stop()
params = st.query_params
if "resume_id" in params and "messages_loaded" not in st.session_state:
    resume_id = params["resume_id"]
    
    # DBから該当ストーリーを取得
    story_data = database.get_story(resume_id)
    
    if story_data and "chat_history" in story_data:
        try:
            # DBからチャット履歴(JSON文字列)を読み込み、リスト(list)に変換
            loaded_messages = json.loads(story_data["chat_history"])
            
            # セッションステートを初期化
            st.session_state.messages = loaded_messages
            st.session_state.final_story_title = story_data.get("title", "")
            st.session_state.final_story_body = story_data.get("body", "")
            st.session_state.chat_history_json = story_data["chat_history"]
            st.session_state.saved_story_id = resume_id # 既存のIDをセット
            
            # (重要) 読み込み完了フラグを立てる (ページリロード時に再読み込みしないため)
            st.session_state.messages_loaded = True 
            
            st.info("過去のヒアリング履歴を読み込みました。")
            
        except json.JSONDecodeError:
            st.error("チャット履歴の読み込みに失敗しました。データが破損している可能性があります。")
        except Exception as e:
            st.error(f"履歴の読み込み中にエラーが発生しました: {e}")
            
    # URLからパラメータを削除 (ブラウザリロード時に再実行しないため)
    st.query_params.clear()


# -----------------------------------------------------------------
#  セッションステートの初期化 (このページ専用)
# -----------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [] # チャット履歴
if "final_story_title" not in st.session_state:
    st.session_state.final_story_title = "" # 生成されたタイトル
if "final_story_body" not in st.session_state:
    st.session_state.final_story_body = "" # 生成された本文
if "chat_history_json" not in st.session_state:
    st.session_state.chat_history_json = "" # 保存用の履歴
if "saved_story_id" not in st.session_state:
    st.session_state.saved_story_id = None # 保存後のID

# -----------------------------------------------------------------
#  UI (3つのタブ)
# -----------------------------------------------------------------

st.title("新しいブランドストーリーを作成します")

tab1, tab2, tab3 = st.tabs(["ステップ1: AIヒアリング", "ステップ2: ストーリー生成", "ステップ3: 保存とQRコード発行"])

# --- タブ1: AIヒアリング (F-001) ---
with tab1:
    st.header("AIヒアリング 🎤")
    st.markdown("生産物への「こだわり」や「情熱」をAIに話してみてください。")

    # チャット履歴の表示
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # ユーザーの入力
    if prompt := st.chat_input("あなたの想いをどうぞ..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").write(prompt)

        # AIの応答 (インタビュアー・プロンプト)
        interviewer_prompt = """
        あなたはプロのインタビュアーです。生産者の情熱（こだわり、苦労、顧客への想い）を
        引き出すように、共感的に質問を返してください。簡潔にお願いします。
        ---
        [履歴]
        {chat_history}
        """
        
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        full_prompt = interviewer_prompt.format(chat_history=history_text)

        with st.spinner("AIが応答を考えています..."):
            response = model.generate_content(full_prompt)
            ai_response = response.text
        
        st.session_state.messages.append({"role": "assistant", "content": ai_response})
        st.chat_message("assistant").write(ai_response)

# --- タブ2: ストーリー生成 (F-002) ---
with tab2:
    st.header("ブランドストーリー生成 ✍️")
    
    if not st.session_state.messages:
        st.warning("まず「ステップ1: AIヒアリング」でAIと対話してください。")
    else:
        if st.button("このヒアリング内容からストーリーを生成する"):
            # プロンプトを修正 (パースしやすい形式に)
            storyteller_prompt = """
            [指示]
            以下の「ヒアリング履歴」に基づき、消費者の心を打つような、
            感動的な「ブランドストーリー」を作成してください。
            出力は必ず以下の形式に従ってください。

            [タイトル]
            ここにタイトルを記述

            [本文]
            ここに800字程度の本文を記述
            ---
            [ヒアリング履歴]
            {chat_history}
            """
            
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            full_prompt = storyteller_prompt.format(chat_history=history_text)

            with st.spinner("AIがストーリーを執筆中です..."):
                response = model.generate_content(full_prompt)
                raw_story_text = response.text
                
                # [タイトル]と[本文]でパースする
                try:
                    title = raw_story_text.split("[タイトル]")[1].split("[本文]")[0].strip()
                    body = raw_story_text.split("[本文]")[1].strip()
                    
                    st.session_state.final_story_title = title
                    st.session_state.final_story_body = body
                    # 保存用の履歴 (JSON文字列)
                    st.session_state.chat_history_json = json.dumps(st.session_state.messages)
                    
                    st.success("ストーリーが生成されました！")
                    
                    # --- 修正 (ここから) ---
                    
                    # 以前のコード (バグの原因)
                    # st.session_state.saved_story_id = None # 生成し直したら保存IDをリセット
                    
                    # 修正後のコード
                    # 新規作成（履歴読み込みではない）の場合のみ、IDをリセットします
                    if "messages_loaded" not in st.session_state:
                        st.session_state.saved_story_id = None 
                    
                    # --- 修正 (ここまで) ---

                except IndexError:
                    st.error("AIの出力形式が予期したものではありませんでした。再試行してください。")
                    st.session_state.final_story_title = ""
                    st.session_state.final_story_body = raw_story_text # 生データ

    if st.session_state.final_story_body:
        st.subheader("生成されたストーリー（確認用）")
        st.markdown(f"**タイトル:** {st.session_state.final_story_title}")
        st.markdown(st.session_state.final_story_body)


# --- タブ3: 保存とQRコード発行 (F-003 & F-004) ---
with tab3:
    st.header("保存とQRコード発行 📱")
    
    if not st.session_state.final_story_body:
        st.warning("まず「ステップ2: ストーリー生成」を完了してください。")
    else:
        st.subheader("最終ストーリーの確認")
        st.markdown(f"**タイトル:** {st.session_state.final_story_title}")
        st.markdown(st.session_state.final_story_body)
        
        st.divider()
        
        # 履歴読み込み済 (上書き) か、新規作成か
        is_update = st.session_state.saved_story_id is not None
        button_label = "この内容で上書き保存する" if is_update else "この内容で新規保存する"

        if st.button(button_label):
            
            if is_update:
                # --- 上書き保存の場合 ---
                with st.spinner("データベースを上書き中です..."):
                    success = database.update_story(
                        story_id=st.session_state.saved_story_id,
                        title=st.session_state.final_story_title,
                        body=st.session_state.final_story_body,
                        chat_history=st.session_state.chat_history_json
                    )
                
                if success:
                    st.success(f"ストーリーが上書き保存されました！ (ID: {st.session_state.saved_story_id})")
                else:
                    st.error("上書き保存に失敗しました。")
            
            else:
                # --- 新規保存の場合 ---
                with st.spinner("データベースに新規保存中です..."):
                    new_story_id = database.save_story(
                        title=st.session_state.final_story_title,
                        body=st.session_state.final_story_body,
                        chat_history=st.session_state.chat_history_json
                    )
                
                if new_story_id:
                    st.success(f"ストーリーが新規保存されました！ (ID: {new_story_id})")
                    st.session_state.saved_story_id = new_story_id # 発行されたIDを保存
                else:
                    st.error("新規保存に失敗しました。")

        # --- 修正 (ここまで) ---

        # 保存が成功したらQRコードを表示
        if st.session_state.saved_story_id:
            story_id = st.session_state.saved_story_id
            
            # (↓ QRコード表示ロジックは変更なし)
            # 【F-004: QRコード発行機能】
            app_url = "https://brand-gen-ejztgk9pxefnatl8jyk4tr.streamlit.app/" 
            final_url = f"{app_url}/?story_id={story_id}"
            
            st.info(f"QRコードが指すURL (↓):\n{final_url}")
            
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(final_url) 
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = BytesIO()
            img.save(buf, format="PNG")
            st.image(buf)
            
            st.warning(
                f"現在は {app_url} (あなたのPC) を指しています。\n"
                "Streamlit Community Cloudにデプロイすると、このURLが公開URLに変わります。"
            )