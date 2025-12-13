# pages/create_new_story.py (修正版)

import streamlit as st
import google.generativeai as genai
import qrcode
from io import BytesIO
import database  # 作成した database.py をインポート
import json
import re

# -----------------------------------------------------------------
#  APIキー設定 (Gemini)
# -----------------------------------------------------------------
try:
    # 通信方式は rest のままでOK
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"], transport='rest')

    model = genai.GenerativeModel('gemini-2.5-flash')
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

    # 1. チャット履歴の表示
    for msg in st.session_state.messages:
        st.chat_message(msg["role"]).write(msg["content"])

    # 2. ユーザーの入力処理
    if prompt := st.chat_input("あなたの想いをどうぞ..."):
        # A. ユーザーの入力をまずは履歴に追加
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # B. 画面上でユーザーの入力を一時的に表示
        st.chat_message("user").write(prompt)

        # C. プロンプト作成とAI生成
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
            
            【重要な禁止事項】
            回答には見出し記号（# や ## など）を使用しないでください。
            常に通常のテキストサイズで応答してください。

            # Workflow (Chain of Thought)
            ステップバイステップで、以下の手順に従って対話を進めてください。

            1.  **アイスブレイク & 商品確認**:
                - まずは明るく挨拶し、緊張を解く。
                - 「今回、皆さんに知ってほしい自慢の生産物は何ですか？」と聞く。

            2.  **ターゲットの明確化 (重要)**:
                - その生産物を「どんな人に」「どんなシチュエーションで」楽しんでほしいかを聞き出す。
                - 例：「お子さんがいる家庭に安心して食べてほしいですか？それとも、自分へのご褒美として楽しんでほしいですか？」

            3.  **「想い」の深掘り**:
                - こだわっている点、他との違い、生産する上での苦労や喜びについて聞く。
                - ユーザーの回答に対し、「それは大変でしたね！」「すごいこだわりですね！」と感情豊かに反応し、さらに「具体的にはどんなことがありましたか？」とエピソードを引き出す。

            4.  **内容の確認と終了**:
                - ストーリー作成に必要な要素が揃ったら、ヒアリング内容を「〇〇という想いで作られた、△△向けの商品ですね」と優しく要約する。
                - 「この内容で素敵な紹介文を作りますね」と伝え、会話を締める。

            # Output Example (Tone)
            - 悪い例: 「ターゲット層を教えてください。また、差別化要因は何ですか？」
            - 良い例: 「うんうん、なるほど！ すごく手間暇がかかっているんですね。ちなみに、このトマトはどんな方に一番食べてほしいですか？ 例えば、野菜嫌いのお子さんとか、料理好きな方とか…。」

            # Self-Correction
            回答を出力する前に、以下の点を自己評価してください。
            - 相手を急かしていないか？
            - 質問が一度に2つ以上になっていないか？
            - 相手の回答に対して、十分な共感（リアクション）を示しているか？
            不備があれば修正し、生産者が話しやすい回答を出力してください。

            # Conversation History
            [履歴]
            {chat_history}
        """
        
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
        full_prompt = interviewer_prompt.format(chat_history=history_text)

        with st.spinner("AIが応答を考えています..."):
            # 【修正3】チャットにもエラーハンドリング(try-except)を追加
            try:
                response = model.generate_content(full_prompt)
                ai_response = response.text
                
                # D. AIの回答を履歴に追加
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
                
                # E. 画面を再読み込み
                st.rerun()
                
            except Exception as e:
                st.error(f"AIとの通信でエラーが発生しました。しばらく待ってから再試行してください。\n詳細: {e}")

# --- タブ2: ストーリー生成 (F-002) ---
with tab2:
    st.header("ブランドストーリー生成 ✍️")
    
    if not st.session_state.messages:
        st.warning("まず「ステップ1: AIヒアリング」でAIと対話してください。")
    else:
        if st.button("このヒアリング内容からストーリーを生成する"):
            # プロンプト (変更なし)
            storyteller_prompt = """
                # Role
                あなたは、心を揺さぶる文章を書く「トップブランド・ストーリーテラー」です。
                提供されたチャット履歴（ヒアリング内容）を元に、消費者がその生産物を手に取りたくなるような、情緒的で魅力的なブランドストーリーを作成してください。

                # Goal
                生産者の「人柄」や「熱量」が伝わる文章を作成し、QRコードからアクセスした消費者の購買意欲やファン化を促進すること。

                # Information Source
                以下のチャット履歴から情報を抽出して使用してください。
                Chat History: {chat_history}

                # Constraints
                - **ターゲット設定**: チャット履歴内で語られた「ターゲット層」に響くトーン＆マナーで執筆すること。
                - **構成**: 「キャッチーなタイトル」＋「本文」の構成とする。
                - **文字数**: スマートフォンで読むことを想定し、本文は400文字〜600文字程度に収める。
                - **表現**: 説明的な文章ではなく、情景が浮かぶような「物語（ナラティブ）」にする。生産者の話し言葉や口癖を効果的に引用する。

                # Workflow (Chain of Thought)
                いきなり文章を書き始めず、以下のステップで論理的に構成してください。

                1.  **情報の分析と抽出**:
                    - `{chat_history}` を読み込み、以下の要素を抽出する。
                        - **Who**: 誰が（生産者の人柄）
                        - **What**: 何を（商品の特徴）
                        - **Target**: 誰に向けて（ターゲット層）
                        - **Why/Story**: どんな想い・苦労・喜びがあるか（核となるエピソード）

                2.  **トーン＆マナーの決定**:
                    - 抽出したターゲット層に合わせて文体を調整する。
                        - （例：高級志向 → 洗練された丁寧な文章 / 家庭向け → 温かみのある親しみやすい文章）

                3.  **プロット作成**:
                    - **導入**: 読者の興味を惹きつける問いかけや情景描写。
                    - **展開**: 生産者の直面した課題や、こだわり抜いたプロセスの描写。
                    - **結び**: 生産者のメッセージと、商品を手に取る消費者への呼びかけ。

                4.  **ドラフト作成**:
                    - プロットに基づき執筆する。タイトルは最後に、本文の内容を凝縮した最も魅力的なものをつける。

                # Output Format
                ## [ここに思わずクリックしたくなるタイトル]

                [ここに本文を記述。適度に改行を入れ、スマホでの可読性を高めること。]

                ---

                # Metacognition & Evaluation
                出力する前に、作成したストーリーを以下の基準で自己採点してください。
                1.  チャット履歴にある「生産者の想い」が反映されているか？（事実の羅列になっていないか）
                2.  ターゲット層に刺さる言葉選びができているか？
                3.  生産者の顔が浮かぶような温かみがあるか？

                上記の基準を満たしていない場合は、よりエモーショナルな表現に修正してから最終出力を行ってください。
            """
            
            history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            full_prompt = storyteller_prompt.format(chat_history=history_text)

            with st.spinner("プロのストーリーテラーが執筆中です（構成検討〜執筆まで行います）..."):
                try:
                    response = model.generate_content(full_prompt)
                    raw_story_text = response.text
                    
                    # 【修正2】正規表現の引数 raw_text= を削除し、変数名のみにする
                    match = re.search(r'##\s*(.*?)\n(.*?)(?:\n---|# Metacognition|$)', raw_story_text, flags=re.DOTALL)

                    # 万が一単純な検索で失敗した場合のバックアップロジック
                    if not match:
                         match = re.search(r'##\s*(.*?)\n(.*)', raw_story_text, re.DOTALL)

                    if match:
                        title = match.group(1).strip()
                        body = match.group(2).strip()
                        
                        # Markdownの太字などを除去（念のため）
                        title = title.replace("**", "")
                        
                        st.session_state.final_story_title = title
                        st.session_state.final_story_body = body
                        st.session_state.chat_history_json = json.dumps(st.session_state.messages)
                        
                        st.success("ストーリーが生成されました！")
                        
                        # 思考プロセス（分析結果など）もデバッグ用に見れるようにする（任意）
                        with st.expander("AIの思考プロセス・分析結果を見る"):
                            st.text(raw_story_text)

                        if "messages_loaded" not in st.session_state:
                            st.session_state.saved_story_id = None 
                    else:
                        raise IndexError("フォーマット不一致")

                except (IndexError, AttributeError):
                    st.error("AIの出力形式を解析できませんでした。")
                    st.warning("▼ 生成された生データ:")
                    st.code(raw_story_text) 
                    
                    # エラー時は生データをそのまま保存できるようにする
                    st.session_state.final_story_title = "タイトル自動取得失敗"
                    st.session_state.final_story_body = raw_story_text

                except Exception as e:
                    st.error(f"ストーリー生成中にエラーが発生しました。\n詳細: {e}")

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