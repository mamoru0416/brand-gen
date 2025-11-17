# database.py

import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import uuid
import json # st.secretsからJSON文字列を読み込むため

# -----------------------------------------------------------------
#  定数
# -----------------------------------------------------------------

# Google Sheetsで作成したスプレッドシートの名前
SHEET_NAME = "brand_gen_database" 

# -----------------------------------------------------------------
#  データベース接続
# -----------------------------------------------------------------

@st.cache_resource(ttl=3600) # 1時間に1回接続をリフレッシュ
def connect_to_db():
    """
    Google Sheetsへの接続を確立し、ワークシートオブジェクトを返す。
    接続情報は st.secrets から読み込み、st.cache_resourceでキャッシュする。
    """
    try:
        # --- 修正箇所 (ここから) ---

        # st.secrets["gcp_service_account"] が、
        # TOMLテーブルを自動的に辞書(dict)として読み込んでくれます。
        creds_dict = st.secrets["gcp_service_account"]
        
        # 以前のコード (この2行を削除します)
        # creds_json_str = st.secrets["gcp_service_account"]
        # creds_dict = json.loads(creds_json_str)

        # --- 修正箇所 (ここまで) ---

        # 3. 辞書型の認証情報を使用してgspreadに接続
        gc = gspread.service_account_from_dict(creds_dict)
        
        # 4. 指定した名前のスプレッドシートを開く
        sh = gc.open(SHEET_NAME)
        
        # 5. 最初のワークシート（シート1）を取得
        worksheet = sh.sheet1
        
        return worksheet
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"エラー: Google Sheet '{SHEET_NAME}' が見つかりません。")
        st.stop()
    except Exception as e:
        st.error(f"データベース接続エラー: {e}")
        st.stop()

# -----------------------------------------------------------------
#  データ取得 (F-005: ストーリー閲覧機能)
# -----------------------------------------------------------------

@st.cache_data(ttl=600) # 10分間、取得したデータをキャッシュする
def get_all_stories():
    """
    シートからすべてのストーリーを取得し、Pandas DataFrameとして返す。
    (ダッシュボード一覧表示用)
    """
    ws = connect_to_db()
    if ws:
        # .get_all_records() は1行目をヘッダーとして自動的に辞書のリストに変換してくれる
        data = ws.get_all_records()
        if data:
            return pd.DataFrame(data)
    return pd.DataFrame() # データがない場合は空のDataFrameを返す

def get_story(story_id):
    """
    指定された story_id に一致するストーリーを1件取得する。
    (QRコードからの閲覧用)
    """
    # 全件取得（キャッシュ利用）
    df = get_all_stories() 
    
    if not df.empty and 'story_id' in df.columns:
        # DataFrameから該当IDの行を検索
        story = df[df['story_id'] == story_id]
        
        if not story.empty:
            # DataFrameを行(dict)に変換して最初の1件を返す
            return story.to_dict('records')[0]
            
    return None # 見つからない場合はNoneを返す

# -----------------------------------------------------------------
#  データ保存 (F-003: ストーリー保存機能)
# -----------------------------------------------------------------

def save_story(title, body, chat_history):
    """
    生成されたストーリーをGoogle Sheetsに新しい行として追加保存する。
    (F-003: ストーリー保存機能)
    
    戻り値:
        str: 保存に成功した場合、新しく発行された story_id
        None: 保存に失敗した場合
    """
    ws = connect_to_db()
    if ws:
        try:
            # 1. 新しいユニークIDを生成
            story_id = str(uuid.uuid4())
            
            # 2. 現在時刻
            created_at = datetime.now().isoformat()
            
            # 3. Google Sheetに追加する行データを作成 (テーブル設計のA列〜E列の順)
            new_row = [
                story_id,
                title,
                body,
                str(chat_history), # 履歴は安全のため文字列として保存
                created_at
            ]
            
            # 4. シートの末尾に行を追加
            ws.append_row(new_row)
            
            # 5. キャッシュをクリア (重要)
            # 新しいデータを追加したので、古いキャッシュを削除する
            st.cache_data.clear()
            
            # 6. QRコード生成用に新しいIDを返す
            return story_id 
            
        except Exception as e:
            st.error(f"ストーリーの保存に失敗しました: {e}")
            return None
    return None
# (save_story 関数の下に追記)

def update_story(story_id, title, body, chat_history):
    """
    既存のストーリーを story_id をキーに上書き更新する。
    (B列: title, C列: body, D列: chat_history を更新)
    
    戻り値:
        bool: 更新が成功したかどうか
    """
    ws = connect_to_db()
    if ws:
        try:
            # 1. story_id (A列にあるはず) を検索してセルを取得
            cell = ws.find(story_id)
            
            if cell:
                # 2. 該当する行番号を取得
                row_number = cell.row
                
                # 3. B列からD列の範囲 (例: "B5:D5") を指定して更新
                update_range = f'B{row_number}:D{row_number}'
                values = [[title, body, str(chat_history)]] # 2次元配列で渡す
                
                ws.update(update_range, values)
                
                # 4. キャッシュをクリア (重要)
                st.cache_data.clear()
                
                return True
            else:
                # 該当する story_id が見つからなかった場合
                st.error(f"上書き対象のID ({story_id}) が見つかりませんでした。")
                return False
                
        except Exception as e:
            st.error(f"ストーリーの上書き保存に失敗しました: {e}")
            return False
    return False