import sys
from database_connection import DatabaseConnection
from PyQt5.QtWidgets import (QApplication, QMainWindow, QCalendarWidget, QVBoxLayout, 
                             QHBoxLayout, QWidget, QTableWidget, QTableWidgetItem, 
                             QPushButton, QDialog, QFormLayout, QLineEdit, QComboBox, 
                             QMessageBox, QAbstractItemView, QTextEdit, QLabel, QDialogButtonBox, QRadioButton)
from PyQt5.QtCore import QDate, Qt, QTimer, QDateTime
from PyQt5.QtGui import QTextCharFormat, QColor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from datetime import datetime, timedelta
import traceback
import sys

# 日本語フォント設定
plt.rcParams['font.family'] = 'meiryo'  # IPAexゴシックフォントを使用
plt.rcParams['axes.unicode_minus'] = False   # マイナス記号の文字化け防止

class ToDoBaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

    def validate_date_selection(self, start_date):
        """
        開始日より期限日が前の場合、期限日を開始日に合わせる
        """
        # 現在選択されている期限日を取得
        due_date = self.due_date_input.selectedDate()
        
        # 開始日より期限日が前の場合、期限日を開始日に合わせる
        if due_date < start_date:
            self.due_date_input.setSelectedDate(start_date)

    def get_dropdown_data(self, column):
        """
        データベースからドロップダウンのデータを取得する
        """
        try:
            query = f'SELECT DISTINCT {column} FROM ToDo WHERE {column} IS NOT NULL AND {column} != ""'
            results = self.parent_window.db.execute_query(query)
            return [str(item[0]) for item in results if item[0]]
        except Exception as e:
            print(f"Error fetching {column} data: {e}")
            return []

class ToDoCalendarApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseConnection()
        
        # 多重起動防止のためのクラス変数を追加
        ToDoCalendarApp.instance = None

        # 多重起動チェック
        if ToDoCalendarApp.instance is not None:
            QMessageBox.warning(None, "警告", "アプリケーションは既に起動しています。")
            sys.exit(1)
        
        ToDoCalendarApp.instance = self
        
        self.setWindowTitle('ToDo カレンダー')
        self.setGeometry(0, 0, 1900, 1000)

        # メインウィジェットとレイアウト
        main_widget = QWidget()
        main_layout = QHBoxLayout()

        # カレンダーウィジェット (タスクタイトル表示)
        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar_widget.setGridVisible(True)
        self.calendar_widget.setNavigationBarVisible(True)
        self.calendar_widget.clicked[QDate].connect(self.show_todos_for_date)

        # カレンダーを大幅に縦に広げる
        self.calendar_widget.setMinimumHeight(850)  # さらに高さを増やす

        # カスタムペイントイベントを設定して日付にToDoタイトルを表示
        self.calendar_widget.paintCell = self.custom_paint_cell

        # ToDoリストテーブル
        self.todo_table = QTableWidget()
        self.todo_table.setColumnCount(7)
        self.todo_table.setHorizontalHeaderLabels(['ID', 'タイトル', 'ステータス', '承認者', '作業者', '期限', '詳細・備考'])
        self.todo_table.setColumnHidden(7, True)
        self.todo_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.todo_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.todo_table.cellChanged.connect(self.update_todo_from_table)

        # ID列を非表示
        self.todo_table.setColumnHidden(0, True) # ID列を非表示

        # 列幅の設定
        self.todo_table.setColumnWidth(0, 0) # ID列は非表示なので幅を0に設定
        self.todo_table.setColumnWidth(1, 160) # タイトル
        self.todo_table.setColumnWidth(2, 60) # ステータス
        self.todo_table.setColumnWidth(3, 50) # 承認者
        self.todo_table.setColumnWidth(4, 50) # 作業者
        self.todo_table.setColumnWidth(5, 70) # 期限
        self.todo_table.setColumnWidth(6, 160) # 詳細

        # 追加・削除・変更・複製ボタン
        button_layout = QHBoxLayout()
        add_todo_button = QPushButton('タスク 追加')
        add_todo_button.setFixedHeight(50)
        add_todo_button.clicked.connect(self.open_add_todo_dialog)

        delete_todo_button = QPushButton('タスク 削除')
        delete_todo_button.setFixedHeight(50)
        delete_todo_button.clicked.connect(self.delete_selected_todo)

        edit_todo_button = QPushButton('タスク 変更')
        edit_todo_button.setFixedHeight(50)
        edit_todo_button.clicked.connect(self.edit_selected_todo)

        duplicate_todo_button = QPushButton('タスク 複製')
        duplicate_todo_button.setFixedHeight(50)
        duplicate_todo_button.clicked.connect(self.duplicate_selected_todo)

        button_layout.addWidget(add_todo_button)
        button_layout.addWidget(edit_todo_button)
        button_layout.addWidget(duplicate_todo_button) # 複製ボタンを追加
        button_layout.addWidget(delete_todo_button)
        
        # 作業者別統計ボタンを追加
        assignee_stats_button = QPushButton('作業者別統計')
        assignee_stats_button.setFixedHeight(50)
        assignee_stats_button.clicked.connect(self.open_assignee_stats_dialog)

        # ボタンレイアウトに追加（既存のボタンの後に）
        button_layout.addWidget(assignee_stats_button)

        # 初期化部分
        self.datetime_label = QLabel() # 現在の日時を表示するラベルを作成
        self.update_datetime() # 初期化時に日時を設定

        # タイマー設定
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_datetime) # タイマーが発火するたびにupdate_datetimeを呼び出す
        self.timer.start(1000) # 1秒ごとに更新

        # レイアウト構成
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.calendar_widget)
        header_layout = QHBoxLayout() # 新しいレイアウトを追加
        header_layout.addWidget(QLabel('🌟選択した日時に登録されているタスク　　　　　　　　　　　🖱️右クリックで進捗状況更新'))
        header_layout.addWidget(self.datetime_label, alignment=Qt.AlignRight)  # ラベルを右端に配置

        right_layout = QVBoxLayout()
        right_layout.addLayout(header_layout) # 新しいヘッダーレイアウトを追加
        right_layout.addWidget(self.todo_table)
        right_layout.addLayout(button_layout)
        right_layout.addWidget(QLabel('📅本日の作業タスク　　　　　　　　　　　　　　　　　　　　　　　 🚨遅延しているタスク'))

        # 本日のタスクと遅延タスクリストを左右に配置
        todo_status_layout = QHBoxLayout()

        # 本日のタスクリスト
        self.today_todos_list = QTextEdit()
        self.today_todos_list.setReadOnly(True)
        todo_status_layout.addWidget(self.today_todos_list)

        # 遅延タスクリスト
        self.delayed_todos_list = QTextEdit()
        self.delayed_todos_list.setReadOnly(True)
        todo_status_layout.addWidget(self.delayed_todos_list)

        # 右側のレイアウトに追加
        right_layout.addLayout(todo_status_layout)

        # メインレイアウトへの追加
        main_layout.addLayout(left_layout, 7) # カレンダー表示7割
        main_layout.addLayout(right_layout, 3) # ToDoリスト部分3割

        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        self.calendar_widget.currentPageChanged.connect(self.show_delayed_todos)
        
        # アプリケーション起動時に遅延タスクを自動更新
        self.load_initial_data()

        # テーブルをダブルクリックしたときに編集ダイアログを開く
        self.todo_table.doubleClicked.connect(self.edit_selected_todo)

        # カレンダーのダブルクリックでToDoを追加できるようにする
        self.calendar_widget.clicked[QDate].connect(self.show_todos_for_date)
        self.calendar_widget.activated[QDate].connect(self.open_add_todo_for_date)
        
        # 右クリックイベントの追加
        self.todo_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.todo_table.customContextMenuRequested.connect(self.show_todo_context_menu)

    def update_datetime(self):
        """現在の日時を更新する"""
        current_datetime = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.datetime_label.setText(current_datetime)

    def _get_todo_cell_color(self, status):
        """ToDoステータスに基づく色を返すヘルパーメソッド"""
        status_colors = {
            "未着手": QColor("blue"),
            "進行中": QColor("green"),
            "完了済": QColor("orange")
        }
        return status_colors.get(status, QColor("black"))

    def custom_paint_cell(self, painter, rect, date):
        """セルのカスタム描画メソッド"""
        displayed_month = self.calendar_widget.monthShown()
        displayed_year = self.calendar_widget.yearShown()
        date_month = date.month()
        date_year = date.year()
        selected_date = self.calendar_widget.selectedDate()

        # 背景色の設定
        self._set_cell_background(painter, rect, date, selected_date)

        # 日付のテキスト色を決定
        text_color = self._determine_date_text_color(date, displayed_month, displayed_year)
        
        # 日付の描画
        self._draw_date_text(painter, rect, date, text_color, selected_date)

        # ToDoの描画
        self._draw_todo_titles(painter, rect, date)

    def _set_cell_background(self, painter, rect, date, selected_date):
        """セルの背景色を設定"""
        if date == QDate.currentDate():
            painter.fillRect(rect, QColor("#e6f7ff"))
        elif date == selected_date:
            painter.fillRect(rect, QColor("#d0f0c0"))
        else:
            painter.fillRect(rect, Qt.white)

    def _determine_date_text_color(self, date, displayed_month, displayed_year):
        """日付のテキスト色を決定"""
        try:
            # 祝日チェック
            date_str = date.toString('yyyy-MM-dd')
            query = "SELECT is_holiday FROM Calendar WHERE date = ?"
            result = self.db.execute_query(query, (date_str,))
            is_holiday = result[0][0] if result else 0

            if is_holiday:
                return QColor("red")

            weekday = date.dayOfWeek()
            if weekday == 6:  # 土曜日
                return QColor("blue")
            elif weekday == 7:  # 日曜日
                return QColor("red")
            
            # 月の範囲外の日付
            if (date.year() < displayed_year or 
                (date.year() == displayed_year and date.month() < displayed_month) or
                (date.year() > displayed_year or date.month() > displayed_month)):
                return QColor("silver")

            # 現在の日付を取得
            today = QDate.currentDate()

            # 今日より前の日付を灰色に
            if date < today:
                return QColor("gray")
                
            return QColor("black")

        except Exception as e:
            print(f"テキスト色決定中にエラー: {e}")
            return QColor("black")

    def _draw_date_text(self, painter, rect, date, text_color, selected_date):
        """日付のテキストを描画"""
        date_font = painter.font()
        date_font.setPointSize(20)
        date_font.setBold(date == selected_date)
        painter.setFont(date_font)
        painter.setPen(text_color)

        painter.drawText(
            rect.adjusted(5, 5, -5, -rect.height() // 2),
            Qt.AlignLeft | Qt.AlignTop,
            date.toString('d')
        )

    def _draw_todo_titles(self, painter, rect, date):
        """ToDoタイトルを描画"""
        try:
            todos = self.db.execute_query(
                '''
                SELECT title, status FROM ToDo 
                JOIN Calendar ON ToDo.calendar_id = Calendar.id 
                WHERE Calendar.date = ?
                ''',
                (date.toString('yyyy-MM-dd'),)
            )

            if todos:
                todo_font = painter.font()
                todo_font.setPointSize(9)
                todo_font.setBold(False)
                painter.setFont(todo_font)

                x_offset = 25
                y_offset = rect.height() // 2 - 28
                for i, (title, status) in enumerate(todos[:6]): # 最大6件まで表示
                    status_color = self._get_todo_cell_color(status)
                    painter.setPen(status_color)
                    painter.drawText(
                        rect.adjusted(x_offset, y_offset + i * 15, -5, -5),
                        Qt.AlignLeft,
                        f"・ {title} ({status})"
                    )
        except Exception as e:
            print(f"セル描画中にエラーが発生: {e}")

    def show_todos_for_date(self, date):
        selected_date = date.toString('yyyy-MM-dd')

        # 選択した日付のToDoを取得するクエリ
        query = '''
        SELECT ToDo.id, ToDo.title, ToDo.status, ToDo.registrant, 
            ToDo.assignee, ToDo.due_date, description
        FROM ToDo
        JOIN Calendar ON ToDo.calendar_id = Calendar.id
        WHERE Calendar.date = ?
        '''

        try:
            todos = self.db.execute_query(query, (selected_date,))

            self.todo_table.setRowCount(0)

            # タスクの数に応じてレイアウトを調整
            max_tasks_per_column = 3 # 3つのタスクごとに新しい列を追加
            row = 0
            col = 0

            for todo in todos:
                row_position = self.todo_table.rowCount()
                self.todo_table.insertRow(row_position)

                # ID (非表示)を最後の列に保存
                for col, value in enumerate(todo):
                    item = QTableWidgetItem(str(value) if value is not None else '')
                    self.todo_table.setItem(row_position, col, item)

                # 列の配置調整
                col += 1
                if col >= max_tasks_per_column:
                    col = 0
                    row += 1

        except Exception as e:
            QMessageBox.critical(self, "エラー", f"データ取得中にエラーが発生しました:\n{str(e)}")

    def load_initial_data(self):
        # 今日の日付のToDoを表示
        today = QDate.currentDate()
        self.show_todos_for_date(today)
        
        # カレンダーの再描画を強制
        self.calendar_widget.updateCells()
        
        # 遅延タスクを表示
        self.show_delayed_todos()

    def annotate_calendar_with_todos(self):
        try:
            # 全ToDoデータを取得
            query = '''
            SELECT Calendar.date, GROUP_CONCAT(ToDo.title, ', ') as todo_titles
            FROM ToDo
            JOIN Calendar ON ToDo.calendar_id = Calendar.id
            GROUP BY Calendar.date
            '''
            todo_dates = self.db.execute_query(query)

            # カレンダーの既存のフォーマットをリセット
            for date in self.calendar_widget.dateTextFormat():
                format = QTextCharFormat()
                self.calendar_widget.setDateTextFormat(date, format)

            # 各日付にToDoタイトルを設定
            for date_str, titles in todo_dates:
                date = QDate.fromString(date_str, 'yyyy-MM-dd')
                
                # 日付の背景色とツールチップを設定
                date_format = QTextCharFormat()
                date_format.setToolTip(titles) # ツールチップにタイトルを設定
                date_format.setBackground(QColor(200, 230, 255))  # 薄いブルー
                
                self.calendar_widget.setDateTextFormat(date, date_format)

        except Exception as e:
            print(f"カレンダー注釈中にエラーが発生しました: {e}")

    def show_delayed_todos(self):
        # 今日の日付を取得
        today = QDate.currentDate()
        today_str = today.toString('yyyy-MM-dd')
        
        # 遅延タスクのクエリ（期限が昨日以前で未完了のタスク）
        delayed_query = '''
        SELECT title, status, start_date, due_date, assignee, description
        FROM ToDo 
        JOIN Calendar ON ToDo.calendar_id = Calendar.id 
        WHERE Calendar.date < ? AND (status = '未着手' OR status = '進行中')
        ORDER BY due_date ,start_date
        '''
        
        # 本日のタスクのクエリ（今日までの未完了タスク）
        today_query = '''
        SELECT title, status, start_date, due_date, assignee, description
        FROM ToDo 
        JOIN Calendar ON ToDo.calendar_id = Calendar.id 
        WHERE Calendar.date <= ? AND (status = '未着手' OR status = '進行中')
        ORDER BY due_date, start_date
        '''
        
        try:
            # リストをクリア
            self.delayed_todos_list.clear()
            self.today_todos_list.clear()
            
            # 遅延タスクの取得と表示
            delayed_todos = self.db.execute_query(delayed_query, (today_str,))
            
            if delayed_todos:
                for todo in delayed_todos:
                    start_date = QDate.fromString(todo[2].split()[0], "yyyy-MM-dd")
                    due_date = QDate.fromString(todo[3], "yyyy-MM-dd")
                    
                    # 遅延日数の計算（期限からの日数）
                    delay_days = due_date.daysTo(today)
                    
                    # 遅延タスクは本日のリストに表示しない（期限が昨日以前のタスク）
                    if due_date > today:
                        continue
                    
                    delayed_text = (
                        f"⚠️タイトル　 {todo[0]}\n"
                        f"ステータス　 {todo[1]}\n"
                        f"開始日　 {start_date.toString('yyyy-MM-dd')}\n"
                        f"期限　 {due_date.toString('yyyy-MM-dd')}\n"
                        f"遅延日数　 {delay_days}日\n"
                        f"作業者　 {todo[4]}\n"
                        f"詳細・備考　 {todo[5]}\n"
                        "------------------\n"
                    )
                    self.delayed_todos_list.append(delayed_text)
                    
            else:
                self.delayed_todos_list.append("遅延しているタスクはありません。\n")
            
            # 本日のタスクの取得と表示
            today_todos = self.db.execute_query(today_query, (today_str,))
            
            if today_todos:
                for todo in today_todos:
                    start_date = QDate.fromString(todo[2].split()[0], "yyyy-MM-dd")
                    due_date = QDate.fromString(todo[3], "yyyy-MM-dd")
                    
                    # 遅延タスクは本日のリストに表示しない（期限が昨日以前のタスク）
                    if due_date < today:
                        continue
                    
                    today_text = (
                        f"📌タイトル　 {todo[0]}\n"
                        f"ステータス　 {todo[1]}\n"
                        f"開始日　 {start_date.toString('yyyy-MM-dd')}\n"
                        f"期限　 {due_date.toString('yyyy-MM-dd')}\n"
                        f"作業者　 {todo[4]}\n"
                        f"詳細・備考　 {todo[5]}\n"
                        "------------------\n"
                    )
                    self.today_todos_list.append(today_text)
            else:
                self.today_todos_list.append("本日のタスクはありません。\n")
            
            # 何もタスクがない場合のデフォルトメッセージ
            if not delayed_todos and not today_todos:
                self.delayed_todos_list.setPlainText('現在、遅延しているタスクはありません')
                self.today_todos_list.setPlainText('現在、本日のタスクはありません')
        
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"タスクの取得中にエラーが発生しました:\n{str(e)}")
    
        # タスク表示後にスクロールバーを一番上に移動
        if self.delayed_todos_list:
            scrollbar = self.delayed_todos_list.verticalScrollBar()
            scrollbar.setValue(scrollbar.minimum())

        if self.today_todos_list:
            scrollbar = self.today_todos_list.verticalScrollBar()
            scrollbar.setValue(scrollbar.minimum())

    def edit_selected_todo(self):
        # 選択された行を取得
        selected_rows = self.todo_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "エラー", "変更するToDoを選択してください。")
            return
        
        # 最初の選択された行の情報を取得
        row = selected_rows[0].row()
        todo_id = self.todo_table.item(row, 0).text()
        
        # 編集用のダイアログを開く
        dialog = EditToDoDialog(self, todo_id)
        dialog.exec_()

    def update_todo_from_table(self, row, column):
        try:
            # ID 項目が存在し、None でないことを確認
            id_item = self.todo_table.item(row, 5)
            if id_item is None:
                print("ID item is None. Skipping update.")
                return
            
            todo_id = id_item.text()
            
            # 更新されたセル項目が存在し、None ではないかどうかを確認
            updated_item = self.todo_table.item(row, column)
            if updated_item is None:
                print(f"Updated item at row {row}, column {column} is None. Skipping update.")
                return
            
            # 更新するカラム名を決定
            columns = ['title', 'status', 'registrant', 'assignee', 'due_date']
            
            if column < len(columns):
                column_name = columns[column]
                new_value = updated_item.text()
                
                # 更新クエリ
                query = f'UPDATE ToDo SET {column_name} = ? WHERE id = ?'
                self.db.execute_query(query, (new_value, todo_id))
                
                # カレンダーの注釈を更新
                self.annotate_calendar_with_todos()
        
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ToDo更新中にエラーが発生しました:\n{str(e)}")
            import traceback
            traceback.print_exc()

        self.show_delayed_todos()

    def delete_selected_todo(self):
        # 選択された行を取得
        selected_rows = self.todo_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "エラー", "削除するToDoを選択してください。")
            return
        
        # 現在選択されている日付を取得
        current_date = self.calendar_widget.selectedDate()
        
        # 最初の選択された行の情報を取得
        row = selected_rows[0].row()
        todo_id = self.todo_table.item(row, 0).text()
        
        # 確認ダイアログ
        reply = QMessageBox.question(self, '確認', 'このToDoを削除しますか？', 
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                
                # ToDo削除
                query = 'DELETE FROM ToDo WHERE id = ?'
                result = self.db.execute_query(query, (todo_id,))
                
                # デバッグ用：削除結果の確認
                print(f"DELETE query result: {result}")
                
                # テーブルから行を削除
                self.todo_table.removeRow(row)
                
                # カレンダーの注釈を更新
                self.annotate_calendar_with_todos()
                
                # 選択されている日付のToDoを再表示
                self.show_todos_for_date(current_date)
                
                # 遅延タスクも更新
                self.show_delayed_todos()
            
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ToDo削除中にエラーが発生しました:\n{str(e)}")
                # エラーの詳細をコンソールに出力
                import traceback
                traceback.print_exc()

        self.show_delayed_todos()

    def duplicate_selected_todo(self):
        # 選択された行を取得
        selected_rows = self.todo_table.selectedIndexes()
        if not selected_rows:
            QMessageBox.warning(self, "エラー", "複製するタスクを選択してください。")
            return
        
        # 最初の選択された行の情報を取得
        row = selected_rows[0].row()
        todo_id = self.todo_table.item(row, 0).text()
        
        # 複製用のダイアログを開く（EditToDoDialogを拡張）
        dialog = DuplicateToDoDialog(self, todo_id)
        dialog.exec_()
        
        # 遅延タスクを更新
        self.show_delayed_todos()

    def open_add_todo_dialog(self):
        dialog = AddToDoDialog(self)
        dialog.exec_()
        self.show_delayed_todos()

    def open_add_todo_for_date(self, date):
        """
        Opens the Add Todo dialog for the selected date when the calendar is double-clicked
        """
        dialog = AddToDoDialog(self)
        # 選択された日付を開始日と期限日にデフォルト設定
        dialog.start_date_input.setSelectedDate(date)
        dialog.due_date_input.setSelectedDate(date)
        dialog.exec_()
        
        # ダイアログ後にToDoリストと遅延タスクを更新
        self.show_todos_for_date(date)
        self.show_delayed_todos()

    def open_assignee_stats_dialog(self):
        dialog = AssigneeStatsDialog(self)
        dialog.exec_()

    def show_todo_context_menu(self, pos):
        """右クリック時のコンテキストメニューを表示"""
        # クリックされた行のインデックスを取得
        index = self.todo_table.indexAt(pos)
        
        # 有効な行がクリックされていない場合は何もしない
        if not index.isValid():
            return
        
        # 選択された行の情報を取得
        row = index.row()
        status_item = self.todo_table.item(row, 2)  # ステータス列
        todo_id_item = self.todo_table.item(row, 0)  # ID列
        
        if status_item is None or todo_id_item is None:
            return
        
        current_status = status_item.text()
        todo_id = todo_id_item.text()
        
        # ステータス更新の確認ダイアログ
        if current_status == '完了済':
            return  # 完了済の場合は何もしない
        
        reply = QMessageBox.question(
            self, 
            '進捗状況の進行', 
            '進捗状況を進行させますか？', 
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # ステータスを更新
                new_status = '進行中' if current_status == '未着手' else '完了済'
                
                # データベース更新クエリ
                query = 'UPDATE ToDo SET status = ? WHERE id = ?'
                self.db.execute_query(query, (new_status, todo_id))
                
                # テーブル内のステータスを更新
                status_item.setText(new_status)
                
                # カレンダーの注釈を更新
                self.annotate_calendar_with_todos()
                
                # 遅延タスクリストを更新
                self.show_delayed_todos()
                
            except Exception as e:
                QMessageBox.critical(self, "エラー", f"ステータス更新中にエラーが発生しました:\n{str(e)}")


    def closeEvent(self, event):
        """アプリケーション終了時に多重起動防止用インスタンスをリセット"""
        ToDoCalendarApp.instance = None
        event.accept()

class EditToDoDialog(ToDoBaseDialog):
    def __init__(self, parent=None, todo_id=None):
        super().__init__(parent)
        self.todo_id = todo_id
        
        self.setWindowTitle('ToDo変更')
        self.setGeometry(200, 200, 400, 500)

        layout = QFormLayout()

        # 初期データの取得
        self.load_initial_todo_data()

        # タイトルコンボボックス
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        title_list = self.get_dropdown_data('title')
        self.title_combo.addItems(title_list)
        self.title_combo.setCurrentText(self.initial_data['title'])

        # 詳細入力
        self.description_input = QTextEdit(self.initial_data.get('description', ''))
        
        # ステータスのコンボボックス
        self.status_combo = QComboBox()
        status_options = ['未着手', '進行中', '完了済']
        self.status_combo.addItems(status_options)
        self.status_combo.setCurrentText(self.initial_data['status'])
        
        # 開始日のカレンダー
        self.start_date_input = QCalendarWidget()
        start_date = QDate.fromString(self.initial_data['start_date'], 'yyyy-MM-dd')
        self.start_date_input.setSelectedDate(start_date)
        
        # 期限日のカレンダー
        self.due_date_input = QCalendarWidget()
        due_date = QDate.fromString(self.initial_data['due_date'], 'yyyy-MM-dd')
        self.due_date_input.setSelectedDate(due_date)

        # 開始日と期限日の変更を監視
        self.start_date_input.clicked[QDate].connect(self.validate_date_selection)
        
        # 承認者のコンボボックス
        self.registrant_combo = QComboBox()
        self.registrant_combo.setEditable(True)
        registrant_list = self.get_dropdown_data('registrant')
        self.registrant_combo.addItems(registrant_list)
        self.registrant_combo.setCurrentText(self.initial_data['registrant'])
        
        # 作業者のコンボボックス
        self.assignee_combo = QComboBox()
        self.assignee_combo.setEditable(True)
        assignee_list = self.get_dropdown_data('assignee')
        self.assignee_combo.addItems(assignee_list)
        self.assignee_combo.setCurrentText(self.initial_data['assignee'])
        
        layout.addRow('タイトル　', self.title_combo)
        layout.addRow('詳細・備考　', self.description_input)
        layout.addRow('ステータス　', self.status_combo)
        layout.addRow('開始日　', self.start_date_input)
        layout.addRow('期限日　', self.due_date_input)
        layout.addRow('承認者　', self.registrant_combo)
        layout.addRow('作業者　', self.assignee_combo)

        save_button = QPushButton('更新')
        save_button.clicked.connect(self.update_todo)
        layout.addRow(save_button)

        self.setLayout(layout)

    def load_initial_todo_data(self):
        # ToDoの初期データを取得
        query = '''
        SELECT ToDo.*, Calendar.date as calendar_date
        FROM ToDo
        JOIN Calendar ON ToDo.calendar_id = Calendar.id
        WHERE ToDo.id = ?
        '''
        try:
            results = self.parent_window.db.execute_query(query, (self.todo_id,))
            if results:
                self.initial_data = {
                    'title': str(results[0][2]),
                    'description': str(results[0][3]) if results[0][3] else '',
                    'status': str(results[0][4]),
                    'registrant': str(results[0][5]),
                    'assignee': str(results[0][6]),
                    'start_date': str(results[0][10]),
                    'due_date': str(results[0][9])
                }
            else:
                raise Exception("ToDoが見つかりませんでした")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ToDo情報の取得中にエラーが発生しました:\n{str(e)}")
            self.reject()

    def update_todo(self):
        try:
            # 開始日のカレンダーIDを取得
            start_date = self.start_date_input.selectedDate().toString('yyyy-MM-dd')
            start_calendar_id_query = 'SELECT id FROM Calendar WHERE date = ?'
            start_calendar_results = self.parent_window.db.execute_query(start_calendar_id_query, (start_date,))
            
            if not start_calendar_results:
                QMessageBox.warning(self, "エラー", "開始日のカレンダーデータが見つかりません。")
                return
            
            start_calendar_id = start_calendar_results[0][0]

            # 期限日
            due_date = self.due_date_input.selectedDate().toString('yyyy-MM-dd')

            # 更新クエリ
            query = '''
            UPDATE ToDo 
            SET calendar_id = ?, title = ?, description = ?, status = ?, 
                registrant = ?, assignee = ?, due_date = ?, start_date = ?
            WHERE id = ?
            '''
            params = (
                start_calendar_id,
                self.title_combo.currentText(),  # タイトルコンボボックスから取得
                self.description_input.toPlainText(),  # QTextEditから取得
                self.status_combo.currentText(),
                self.registrant_combo.currentText(),
                self.assignee_combo.currentText(),
                due_date,
                start_date,
                self.todo_id
            )
            
            # クエリの実行
            self.parent_window.db.execute_query(query, params)
            
            # 保存後にToDoリストを更新
            self.parent_window.show_todos_for_date(
                self.start_date_input.selectedDate()
            )
            
            # カレンダーの注釈を更新
            self.parent_window.annotate_calendar_with_todos()
            
            # ダイアログを閉じる
            self.accept()
        
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ToDo更新中にエラーが発生しました:\n{str(e)}")

class AddToDoDialog(ToDoBaseDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        
        self.setWindowTitle('ToDo追加')
        self.setGeometry(200, 200, 400, 400)

        layout = QFormLayout()

        # タイトルコンボボックス
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        title_list = self.get_dropdown_data('title')
        self.title_combo.addItems(title_list)
        
        # 詳細入力
        self.description_input = QLineEdit()
        
        # ステータスのコンボボックス
        self.status_combo = QComboBox()
        self.status_combo.addItems(['未着手', '進行中', '完了済'])
        
        # 開始日のカレンダー
        self.start_date_input = QCalendarWidget()
        initial_date = self.parent_window.calendar_widget.selectedDate()
        self.start_date_input.setSelectedDate(initial_date)
        
        # 期限日のカレンダー
        self.due_date_input = QCalendarWidget()
        self.due_date_input.setSelectedDate(initial_date)

        # 開始日と期限日の変更を監視
        self.start_date_input.clicked[QDate].connect(self.validate_date_selection)
        
        # 承認者のコンボボックス
        self.registrant_combo = QComboBox()
        self.registrant_combo.setEditable(True)
        registrant_list = self.get_dropdown_data('registrant')
        self.registrant_combo.addItems(registrant_list)
        
        # 作業者のコンボボックス
        self.assignee_combo = QComboBox()
        self.assignee_combo.setEditable(True)
        assignee_list = self.get_dropdown_data('assignee')
        self.assignee_combo.addItems(assignee_list)

        layout.addRow('タイトル　', self.title_combo)
        layout.addRow('詳細・備考　', self.description_input)
        layout.addRow('ステータス　', self.status_combo)
        layout.addRow('開始日　', self.start_date_input)
        layout.addRow('期限日　', self.due_date_input)
        layout.addRow('承認者　', self.registrant_combo)
        layout.addRow('作業者　', self.assignee_combo)

        save_button = QPushButton('保存')
        save_button.clicked.connect(self.save_todo)
        layout.addRow(save_button)

        self.setLayout(layout)

    def save_todo(self):
        try:
            # 開始日のカレンダーIDを取得
            start_date = self.start_date_input.selectedDate().toString('yyyy-MM-dd')
            start_calendar_id_query = 'SELECT id FROM Calendar WHERE date = ?'
            start_calendar_results = self.parent_window.db.execute_query(start_calendar_id_query, (start_date,))
            
            if not start_calendar_results:
                QMessageBox.warning(self, "エラー", "開始日のカレンダーデータが見つかりません。")
                return
            
            start_calendar_id = start_calendar_results[0][0]

            # 期限日のカレンダーIDを取得
            due_date = self.due_date_input.selectedDate().toString('yyyy-MM-dd')
            
            # 挿入クエリ
            query = '''
            INSERT INTO ToDo 
            (calendar_id, title, description, status, registrant, assignee, due_date, start_date) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''

            params = (
                start_calendar_id,
                self.title_combo.currentText(),
                self.description_input.text(),
                self.status_combo.currentText(),
                self.registrant_combo.currentText(),
                self.assignee_combo.currentText(),
                due_date,
                start_date
            )
            
            # クエリの実行
            self.parent_window.db.execute_query(query, params)
            
            # カレンダーの注釈を更新
            self.parent_window.annotate_calendar_with_todos()
            
            # 選択されている日付のToDoを再表示
            self.parent_window.show_todos_for_date(
                self.parent_window.calendar_widget.selectedDate()
            )
            
            # ダイアログを閉じる
            self.accept()
        
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ToDo保存中にエラーが発生しました:\n{str(e)}")

class DuplicateToDoDialog(EditToDoDialog):
    def __init__(self, parent=None, todo_id=None):
        # 親クラスのコンストラクタを呼び出す
        super().__init__(parent, todo_id)
        
        # ウィンドウタイトルを変更
        self.setWindowTitle('ToDo複製')
        
        # 保存/更新ボタンを削除
        layout = self.layout()
        
        # レイアウトの最後の行（保存ボタンがあった場所）を削除
        if layout.rowCount() > 0:
            layout.removeRow(layout.rowCount() - 1)
        
        # ボタンボックスを追加
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.duplicate_todo)
        button_box.rejected.connect(self.reject)
        
        # レイアウトの最後に新しいボタンボックスを追加
        layout.addRow(button_box)
    
    def duplicate_todo(self):
        try:
            # 開始日のカレンダーIDを取得
            start_date = self.start_date_input.selectedDate().toString('yyyy-MM-dd')
            start_calendar_id_query = 'SELECT id FROM Calendar WHERE date = ?'
            start_calendar_results = self.parent_window.db.execute_query(start_calendar_id_query, (start_date,))
            
            if not start_calendar_results:
                QMessageBox.warning(self, "エラー", "開始日のカレンダーデータが見つかりません。")
                return
            
            start_calendar_id = start_calendar_results[0][0]

            # 期限日
            due_date = self.due_date_input.selectedDate().toString('yyyy-MM-dd')

            # 複製クエリ（新しいIDで挿入）
            query = '''
            INSERT INTO ToDo 
            (calendar_id, title, description, status, registrant, assignee, due_date, start_date) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''

            duplicate_title = self.title_combo.currentText()
            duplicate_description = self.description_input.toPlainText()
            
            params = (
                start_calendar_id,
                duplicate_title,
                duplicate_description,
                '未着手',  # ステータスを「未着手」にリセット
                self.registrant_combo.currentText(),
                self.assignee_combo.currentText(),
                due_date,
                start_date
            )
            
            # クエリの実行
            self.parent_window.db.execute_query(query, params)
            
            # 保存後にToDoリストを更新
            self.parent_window.show_todos_for_date(
                self.start_date_input.selectedDate()
            )
            
            # カレンダーの注釈を更新
            self.parent_window.annotate_calendar_with_todos()
            
            # ダイアログを閉じる
            self.accept()
            
            # 複製成功メッセージ
            QMessageBox.information(self.parent_window, "成功", "タスクが正常に複製されました。")
        
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ToDo複製中にエラーが発生しました:\n{str(e)}")

class AssigneeStatsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle('作業者別タスク統計')
        self.setGeometry(200, 200, 800, 600)

        # メインレイアウト
        main_layout = QVBoxLayout()

        # 期間選択コンボボックス
        period_layout = QHBoxLayout()
        self.period_combo = QComboBox()
        self.period_combo.addItems(['今月', '前1ヶ月', '年間'])
        period_layout.addWidget(QLabel('期間:'))
        period_layout.addWidget(self.period_combo)
        period_layout.addStretch()

        # 統計タイプのラジオボタン
        self.completed_radio = QRadioButton('完了タスク')
        self.uncompleted_radio = QRadioButton('未完了タスク')
        self.delayed_radio = QRadioButton('遅延タスク')
        
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.completed_radio)
        radio_layout.addWidget(self.uncompleted_radio)
        radio_layout.addWidget(self.delayed_radio)
        
        # デフォルトで完了タスクを選択
        self.completed_radio.setChecked(True)

        # グラフエリア
        self.figure, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        self.canvas = FigureCanvas(self.figure)

        # 更新ボタン
        update_button = QPushButton('統計更新')
        update_button.clicked.connect(self.update_statistics)

        # レイアウトに追加
        main_layout.addLayout(period_layout)
        main_layout.addLayout(radio_layout)
        main_layout.addWidget(self.canvas)
        main_layout.addWidget(update_button)

        self.setLayout(main_layout)

        # 初期更新
        self.update_statistics()

        # ラジオボタンと期間コンボボックスの変更イベント
        self.completed_radio.toggled.connect(self.update_statistics)
        self.uncompleted_radio.toggled.connect(self.update_statistics)
        self.delayed_radio.toggled.connect(self.update_statistics)
        self.period_combo.currentTextChanged.connect(self.update_statistics)

    def get_date_range(self):
        """選択された期間の開始日と終了日を取得"""
        today = datetime.now()  # 本日の日付
        end_date = today.date()  # 終了日は本日

        if self.period_combo.currentText() == '今月':
            start_date = today.replace(day=1).date()  # 今月の1日
        elif self.period_combo.currentText() == '前1ヶ月':
            start_date = (today - timedelta(days=30)).date()  # 本日から30日前
        else:  # 年間
            start_date = today.replace(month=1, day=1).date()  # 年初（1月1日）

        return start_date, end_date

    def update_statistics(self):
        """作業者別のタスク統計を取得し、グラフを更新"""
        try:
            start_date, end_date = self.get_date_range()

            # 条件の定義
            if self.completed_radio.isChecked():
                where_condition = "status = '完了済'"
                title_text = '完了タスク'
            elif self.uncompleted_radio.isChecked():
                where_condition = "status != '完了済'"
                title_text = '未完了タスク'
            else:  # 遅延タスク
                where_condition = "status != '完了済' AND due_date < ?"
                title_text = '遅延タスク'

            # 作業者別タスク数を取得するクエリ
            query = f'''
            SELECT assignee, COUNT(*) as task_count 
            FROM ToDo 
            WHERE {where_condition} 
            AND start_date BETWEEN ? AND ?
            GROUP BY assignee
            ORDER BY task_count DESC
            '''

            # 全タスク数を取得するクエリ
            total_task_query = f'''
            SELECT COUNT(*) as task_count 
            FROM ToDo 
            WHERE {where_condition} 
            AND start_date BETWEEN ? AND ?
            '''

            # クエリパラメータの準備
            if self.delayed_radio.isChecked():
                query_params = (str(end_date), str(start_date), str(end_date))
                total_task_params = (str(end_date), str(start_date), str(end_date))
            else:
                query_params = (str(start_date), str(end_date))
                total_task_params = (str(start_date), str(end_date))

            # データベース接続の確認
            if not hasattr(self.parent_window, 'db'):
                raise AttributeError("データベース接続が設定されていません")

            # クエリの実行
            results = self.parent_window.db.execute_query(query, query_params)
            total_tasks = self.parent_window.db.execute_query(total_task_query, total_task_params)[0][0]

            # データが空の場合の処理
            if not results:
                QMessageBox.information(self, "情報", "該当するタスクがありません")
                return

            # データ準備
            assignees = [result[0] for result in results]
            task_counts = [result[1] for result in results]

            # パーセンテージ計算（ゼロ除算回避）
            task_percentages = [count / total_tasks * 100 if total_tasks > 0 else 0 for count in task_counts]

            # グラフをクリア
            self.ax.clear()

            # 棒グラフ描画
            bars = self.ax.bar(assignees, task_counts)
            self.ax.set_title(f'作業者別{title_text}統計 ({self.period_combo.currentText()})')
            self.ax.set_xlabel('作業者')
            self.ax.set_ylabel(f'{title_text}数')

            # 棒の上に数値とパーセンテージを表示
            for i, bar in enumerate(bars):
                height = bar.get_height()
                percentage = task_percentages[i]
                self.ax.text(
                    bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f} ({percentage:.1f}%)', 
                    ha='center', va='bottom'
                )

            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            # キャンバスを再描画
            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(
                self, 
                "エラー", 
                f"統計取得中に予期せぬエラーが発生しました:\n{str(e)}"
            )

def main():
    app = QApplication(sys.argv)
    todo_calendar_app = ToDoCalendarApp()
    todo_calendar_app.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()