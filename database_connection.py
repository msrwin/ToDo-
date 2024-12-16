import sqlite3
from datetime import datetime, timedelta
import os
import sys
import jpholiday

class DatabaseConnection:
    def __init__(self, db_path='todo_calendar.db'):
        """
        SQLiteデータベース接続クラス
        
        :param db_path: データベースファイルのパス
        """
        # ユーザーのドキュメントフォルダにデータベースファイルを格納
        documents_folder = os.path.expanduser('~/Documents')
        
        # アプリケーション専用のサブフォルダを作成
        app_data_folder = os.path.join(documents_folder, 'TodoCalendarApp')
        
        # フォルダが存在しない場合は作成
        os.makedirs(app_data_folder, exist_ok=True)
        
        # データベースファイルのパスを設定
        self.db_path = os.path.join(app_data_folder, db_path)
        
        # データベース接続とテーブル初期化
        self.initialize_database()
    
    def get_connection(self):
        """
        データベース接続を取得
        
        :return: sqlite3接続オブジェクト
        """
        try:
            connection = sqlite3.connect(self.db_path, check_same_thread=False)
            return connection
        except sqlite3.Error as e:
            print(f"データベース接続エラー: {e}")
            raise
    
    def execute_query(self, query, params=None):
        """
        クエリを実行し、結果を返す
        
        :param query: 実行するSQL文
        :param params: クエリのパラメータ（オプション）
        :return: クエリ結果
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # パラメータがある場合
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # SELECT文の場合は結果を返す
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                
                # INSERT, UPDATE, DELETE文の場合はコミット
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error as e:
            print(f"クエリ実行エラー: {e}")
            raise
    
    def create_calendar_table(self):
        """
        Calendarテーブルを作成
        """
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS Calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            day_of_week TEXT,
            is_holiday INTEGER DEFAULT 0
        )
        '''
        self.execute_query(create_table_query)
    
    def create_todo_table(self):
        """
        ToDoテーブルを作成
        """
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS ToDo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calendar_id INTEGER,
            title TEXT,
            description TEXT,
            status TEXT CHECK(status IN ('未着手', '進行中', '完了済')) DEFAULT '未着手',
            registrant TEXT,
            assignee TEXT,
            priority INTEGER DEFAULT 3,
            due_date TEXT,
            start_date TEXT,
            FOREIGN KEY (calendar_id) REFERENCES Calendar(id)
        )
        '''
        self.execute_query(create_table_query)
    
    def get_last_existing_date(self):
        """
        データベースに保存されている最後の日付を取得
        
        :return: 最後の日付（datetime型）または現在の日付
        """
        query = 'SELECT MAX(date) FROM Calendar'
        result = self.execute_query(query)
        
        # データベースにまだ日付がない場合は現在の日付を返す
        if not result or result[0][0] is None:
            return datetime.now()
        
        # 最後の日付を取得
        last_date_str = result[0][0]
        return datetime.strptime(last_date_str, '%Y-%m-%d')
    
    def get_first_existing_date(self):
        """
        データベースに保存されている最初の日付を取得
        
        :return: 最初の日付（datetime型）または現在の日付
        """
        query = 'SELECT MIN(date) FROM Calendar'
        result = self.execute_query(query)
        
        # データベースにまだ日付がない場合は現在の日付を返す
        if not result or result[0][0] is None:
            return datetime.now()
        
        # 最初の日付を取得
        first_date_str = result[0][0]
        return datetime.strptime(first_date_str, '%Y-%m-%d')
    
    def generate_calendar_data(self):
        """
        不足している日付範囲のカレンダーデータを追加生成
        """
        # 現在の日付を取得
        current_date = datetime.now()
        
        # 既存の最後の日付を取得
        last_date = self.get_last_existing_date()
        
        # 1年後の日付を計算
        one_year_after = last_date.replace(year=last_date.year + 1)
        
        # 追加する開始日と終了日を決定
        start_date = last_date + timedelta(days=1)
        end_date = min(one_year_after, current_date.replace(year=current_date.year + 1))
        
        # データを追加する必要があるかチェック
        if start_date > end_date:
            print("カレンダーデータは最新です")
            return
        
        insert_query = '''
        INSERT OR IGNORE INTO Calendar (date, year, month, day, day_of_week)
        VALUES (?, ?, ?, ?, ?)
        '''
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            current = start_date
            while current <= end_date:
                cursor.execute(insert_query, (
                    current.strftime('%Y-%m-%d'),
                    current.year,
                    current.month,
                    current.day,
                    current.strftime('%A')
                ))
                current += timedelta(days=1)
            
            # 実際に追加されたデータの数をチェック
            rows_added = conn.total_changes
            
            conn.commit()
            
            if rows_added > 0:
                print(f"カレンダーデータを {start_date.strftime('%Y-%m-%d')} から {end_date.strftime('%Y-%m-%d')} まで追加生成しました。")
            else:
                print("カレンダーデータは最新です")
            
    def initialize_database(self):
        """
        データベースの初期化（テーブル作成とカレンダーデータ生成）
        """
        # テーブル作成
        self.create_calendar_table()
        self.create_todo_table()
        
        # カレンダーデータが空の場合のみ初期データを生成
        check_calendar_query = 'SELECT COUNT(*) FROM Calendar'
        result = self.execute_query(check_calendar_query)[0][0]
        
        # 1年以上前の古いデータを削除
        # self.delete_old_calendar_data()
        
        if result == 0:
            # 初回実行時は現在の日付から1年分を生成
            start_date = datetime.now()
            end_date = start_date + timedelta(days=364)
            
            insert_query = '''
            INSERT OR IGNORE INTO Calendar (date, year, month, day, day_of_week)
            VALUES (?, ?, ?, ?, ?)
            '''
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                current = start_date
                while current <= end_date:
                    cursor.execute(insert_query, (
                        current.strftime('%Y-%m-%d'),
                        current.year,
                        current.month,
                        current.day,
                        current.strftime('%A')
                    ))
                    current += timedelta(days=1)
                
                conn.commit()
                print(f"初期カレンダーデータを {start_date.strftime('%Y-%m-%d')} から {end_date.strftime('%Y-%m-%d')} まで生成しました。")
        
        # 不足している日付を追加
        self.generate_calendar_data()
        
        # 祝日情報を更新
        self.update_holiday_information()

    def update_holiday_information(self):
        """
        Calendarテーブルの祝日情報を更新
        """
        update_query = '''
        UPDATE Calendar
        SET is_holiday = ?
        WHERE date = ?
        '''
        
        select_query = 'SELECT date FROM Calendar'
        dates = self.execute_query(select_query)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            for date_tuple in dates:
                date_str = date_tuple[0]
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')

                # `jpholiday`を使って祝日判定
                is_holiday = 1 if jpholiday.is_holiday(date_obj) else 0

                cursor.execute(update_query, (is_holiday, date_str))
            conn.commit()
        print("祝日情報を更新しました。")

    def delete_old_calendar_data(self):
        """
        1年以上前のCalendarデータと関連するToDoデータを削除
        """
        try:
            # 現在の日付から1年以上前の日付を取得
            one_year_ago = datetime.now() - timedelta(days=365)
            one_year_ago_str = one_year_ago.strftime('%Y-%m-%d')

            # 古いToDoデータと関連するCalendarデータを削除するクエリ
            delete_todos_query = '''
            DELETE FROM ToDo 
            WHERE calendar_id IN (
                SELECT id FROM Calendar 
                WHERE date < ?
            )
            '''

            delete_calendar_query = '''
            DELETE FROM Calendar 
            WHERE date < ?
            '''

            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 古いToDoデータを削除
                cursor.execute(delete_todos_query, (one_year_ago_str,))
                todo_deleted_count = cursor.rowcount
                
                # 古いCalendarデータを削除
                cursor.execute(delete_calendar_query, (one_year_ago_str,))
                calendar_deleted_count = cursor.rowcount
                
                conn.commit()
                
                print(f"1年以上前の古いToDoデータ {todo_deleted_count} 件を削除しました。")
                print(f"1年以上前の古いCalendarデータ {calendar_deleted_count} 件を削除しました。")
                
        except sqlite3.Error as e:
            print(f"古いデータ削除中にエラーが発生しました: {e}")
            raise

def main():
    db = DatabaseConnection()

if __name__ == "__main__":
    main()