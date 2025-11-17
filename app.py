# app.py (メインページ: ダッシュボード & 閲覧モード)

import streamlit as st
import database  # 作成した database.py をインポート
import pandas as pd

# 1. URLのクエリパラメータを最初にチェック
params = st.query_params

# 2. "story_id" がURLに含まれているか（＝エンドユーザーの閲覧か）
if "story_id" in params:
    
    # 3. Streamlitの内部コンポーネントを非表示にするCSSを注入
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                display: none;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
# -----------------------------------------------------------------
#  メイン処理
# -----------------------------------------------------------------


# 【F-005: ストーリー閲覧機能】
if "story_id" in params:
    story_id = params["story_id"]
    
    # データベースから該当IDのストーリーを取得
    @st.cache_data(ttl=600) # 閲覧データもキャッシュ
    def fetch_story(sid):
        return database.get_story(sid)
        
    story_data = fetch_story(story_id)
    
    if story_data:
        # ストーリーが見つかった場合、閲覧モードで表示
        st.title(story_data.get("title", "ストーリー"))
        st.markdown(f"*{story_data.get('created_at', '')}*")
        st.divider()
        st.markdown(story_data.get("body", "本文がありません。"))
    else:
        # IDが見つからない場合
        st.error("指定されたストーリーが見つかりません。")
        st.page_link("app.py", label="ダッシュボードに戻る", icon="🏠")

# 【ダッシュボード機能】
else:
    # story_id がない場合 (通常のアクセス時)
    st.set_page_config(page_title="ブランドストーリーダッシュボード", layout="wide")
    
    st.title("ブランドストーリー管理ダッシュボード 🚀")
    st.markdown("左のサイドバーから「新しいストーリーを作成」を選んで、ヒアリングを開始してください。")
    
    st.divider()
    st.header("過去に作成したストーリー一覧")
    
    # データベースから全ストーリーを取得
    try:
        df = database.get_all_stories()
        
        if df.empty:
            st.info("まだ作成されたストーリーはありません。")
        else:
            # --- 修正・追加 (ここから) ---
            # リンク用のURLをDataFrameに新しい列として追加
            # (pages/1_新しいストーリーを作成.py に ?resume_id=... を渡す)
            page_path = "create_new_story" 
            
            # resume_url 列を追加 (先頭の "/" なし)
            df["resume_url"] = df["story_id"].apply(lambda id: f"{page_path}?resume_id={id}")
            # --- 修正 (ここまで) ---

            # 表示するカラムを整形
            display_columns = ["created_at", "title", "resume_url", "story_id"]
            
            available_columns = [col for col in display_columns if col in df.columns]
            
            if available_columns:
                st.dataframe(
                    df[available_columns],
                    use_container_width=True,
                    column_config={
                        "created_at": st.column_config.DatetimeColumn("作成日時", format="YYYY/MM/DD HH:mm"),
                        "title": "タイトル",
                        # --- 修正・追加 (ここから) ---
                        "resume_url": st.column_config.LinkColumn(
                            "続きから",
                            display_text="この続きから始める ↻"
                        ),
                        # --- 修正・追加 (ここまで) ---
                        "story_id": "ストーリーID (QRコード用)"
                    },
                    hide_index=True,
                )
            else:
                st.warning("データはありますが、表示できるカラム(created_at, title, story_id)がありません。")

    except Exception as e:
        st.error(f"データの読み込みに失敗しました: {e}")