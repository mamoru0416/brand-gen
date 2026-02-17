# app.py (メインページ: ダッシュボード & 閲覧モード)

import streamlit as st
import database
import pandas as pd

# -----------------------------------------------------------------
#  設定 & 定数
# -----------------------------------------------------------------
st.set_page_config(
    page_title="Brand Story Generator",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# クエリパラメータの取得
params = st.query_params

# -----------------------------------------------------------------
#  閲覧モード (End User View)
# -----------------------------------------------------------------
if "story_id" in params:
    story_id = params["story_id"]
    
    # --- CSS: 閲覧モード専用のスタイル (モバイルLP風) ---
    st.markdown("""
    <style>
        /* Streamlitのヘッダー・フッター・サイドバーを隠す */
        header {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stSidebar"] {display: none;}
        
        /* 全体の背景 */
        .stApp {
            background-color: #f9f9f9;
        }
        
        /* ストーリーカード */
        .story-card {
            background-color: white;
            max-width: 600px;
            margin: 20px auto;
            padding: 40px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Hiragino Sans", Meiryo, sans-serif;
            color: #333;
            line-height: 1.8;
        }
        
        .story-title {
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin-bottom: 20px;
            color: #2c3e50;
        }
        
        .story-body {
            font-size: 16px;
            text-align: justify;
            white-space: pre-wrap; /* 改行を維持 */
        }
        
        .story-footer {
            margin-top: 40px;
            text-align: center;
            font-size: 12px;
            color: #888;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }
    </style>
    """, unsafe_allow_html=True)

    # データの取得
    @st.cache_data(ttl=600)
    def fetch_story(sid):
        return database.get_story(sid)
        
    story_data = fetch_story(story_id)
    
    if story_data:
        # HTMLとしてレンダリング
        st.markdown(f"""
        <div class="story-card">
            <div class="story-title">{story_data.get('title', '無題のストーリー')}</div>
            <div class="story-body">{story_data.get('body', '')}</div>
            <div class="story-footer">
                Production Story<br>
                {story_data.get('created_at', '')[:10]}
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("指定されたストーリーが見つかりません。")
        st.page_link("app.py", label="トップへ戻る", icon="🏠")

# -----------------------------------------------------------------
#  ダッシュボードモード (Admin View)
# -----------------------------------------------------------------
else:
    # サイドバーは表示
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {display: block;}
    </style>
    """, unsafe_allow_html=True)
    
    st.title("ブランドストーリー管理ダッシュボード 🚀")
    
    # 新規作成への同線
    st.info("👈 左のサイドバーから「新しいストーリーを作成」を選んでください。")
    
    st.divider()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("作成済みストーリー一覧")
    with col2:
        if st.button("🔄 更新"):
            st.cache_data.clear()
            st.rerun()

    # データ取得
    try:
        df = database.get_all_stories()
        
        if df.empty:
            st.warning("まだストーリーがありません。")
        else:
            # 日付でソート (新しい順)
            if "created_at" in df.columns:
                df = df.sort_values("created_at", ascending=False)
            
            # カード形式でリスト表示
            for index, row in df.iterrows():
                # Streamlitネイティブのコンテナを使用 (border=Trueで枠線を表示)
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    
                    with c1:
                        st.markdown(f"**{row['title']}**")
                        # 本文の冒頭50文字を表示
                        summary = row['body'][:50].replace('\n', ' ') + "..." if len(row['body']) > 50 else row['body'].replace('\n', ' ')
                        st.caption(f"{row['created_at'][:16]} | ID: {row['story_id']}")
                        st.markdown(f"<span style='color: #666; font-size: 0.9em;'>{summary}</span>", unsafe_allow_html=True)
                    
                    with c2:
                        # 編集（続きから）リンク
                        # st.page_link ではクエリパラメータを渡せないので、通常のリンクボタンを使用
                        # Streamlit Community Cloud上のパスを想定して相対パスで指定
                        resume_url = f"create_new_story?resume_id={row['story_id']}"
                        st.link_button(
                            "編集/再開", 
                            url=resume_url,
                            help="チャットの続きから再開します",
                            use_container_width=True
                        )
                        
                        # QRコード確認（自分自身へのリンク）
                        st.link_button(
                            "確認", 
                            url=f"?story_id={row['story_id']}",
                            help="完成したストーリーを確認します",
                            use_container_width=True
                        )

    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")