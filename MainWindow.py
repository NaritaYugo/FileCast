from pathlib import Path
import yaml

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QDialog, QFileDialog, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QStackedLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

import fileLoadingUtils
import renameCore
import RuleBuilderDialog
import styles
import validations


COLORS = {
    "ready": QColor("#54CE41"), 
    "warn": QColor("#FFF200"), 
    "error": QColor("#FF4949")
    }

class DropEventMixin:
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return

        file_path = Path(urls[0].toLocalFile())
        if file_path.is_dir():
            self.folder_dropped.emit(str(file_path))

class DropTableWidget(DropEventMixin, QTableWidget):
    folder_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setColumnCount(1)
        self.setRowCount(0)
        self.setHorizontalHeaderLabels(["ファイルの内容"])

class DropLabel(DropEventMixin, QLabel):
    folder_dropped = Signal(str)

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setAcceptDrops(True)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileCast")
        self.resize(1000, 600)

        self._rules = []
        self._settings = {}

        self._target_dir = ""
        self._original_files = []
        self._file_caches = {}

        self._file_caches_path = fileLoadingUtils.get_base_dir() / "caches.yaml"

        self._ensure_yamls_exsist()
        
        self._setup_ui()
        self._display_sample()

        self._rules_dialog = RuleBuilderDialog.RuleBuilderDialog(self)

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 上段: フォルダ読み込み
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        self._dir_label = QLabel("フォルダ: 未選択")
        self._dir_label.setStyleSheet(styles.MainStyle.DIR_LABEL)
        top_layout.addWidget(self._dir_label, stretch=1)

        load_file_btn = QPushButton("📂 フォルダを選択")
        load_file_btn.setStyleSheet("padding: 5px;")
        load_file_btn.clicked.connect(self.load_directory)
        top_layout.addWidget(load_file_btn)

        self._revert_file_btn = QPushButton("元に戻す")
        self._revert_file_btn.setStyleSheet("padding: 5px;")
        self._revert_file_btn.clicked.connect(self._on_revert_btn_clicked)
        self._revert_file_btn.setEnabled(bool(self._file_caches.get("filename")))
        top_layout.addWidget(self._revert_file_btn)

        # 中段: ファイルリスト
        self.stack = QStackedLayout()
        main_layout.addLayout(self.stack)

        table_placeholder = DropLabel("フォルダを選択またはドラッグアンドドロップしてください")
        table_placeholder.setStyleSheet(styles.MainStyle.TABLE_PH)
        table_placeholder.setAlignment(Qt.AlignCenter)
        table_placeholder.folder_dropped.connect(self._process_directory)
        self.stack.addWidget(table_placeholder)

        self._file_table = DropTableWidget()
        self._file_table.folder_dropped.connect(self._process_directory)
        self._file_table.setColumnCount(3)
        self._file_table.setHorizontalHeaderLabels(["元のファイル名", "変換後のプレビュー(ダブルクリックで編集)", "ステータス"])
        self._file_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._file_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._file_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._file_table.cellChanged.connect(self._on_table_cell_changed)
        self.stack.addWidget(self._file_table)

        # 下段: 設定、リネーム実行
        bottom_layout = QHBoxLayout()
        main_layout.addLayout(bottom_layout)

        setting_btn = QPushButton("⚙️ 命名規則の編集")
        setting_btn.setStyleSheet(styles.MainStyle.SETTING_BTN)
        setting_btn.clicked.connect(self._open_rules_dialog)
        bottom_layout.addWidget(setting_btn, 1)

        self._rules_sample = QLabel("命名規則を設定してください")
        self._rules_sample.setStyleSheet(styles.MainStyle.RULES_SAMPLE)
        bottom_layout.addWidget(self._rules_sample, 3)

        self._execute_btn = QPushButton("リネーム実行")
        self._execute_btn.setStyleSheet(styles.MainStyle.EXECUTE_BTN)
        self._execute_btn.clicked.connect(self.execute_rename)
        self._execute_btn.setEnabled(False)
        bottom_layout.addWidget(self._execute_btn, 1)

    def _ensure_yamls_exsist(self):
        """yamlファイルが無ければ新規作成する"""
        self._categories = fileLoadingUtils.load_categories(self)
        self._rules = fileLoadingUtils.load_rules(self)
        self._settings = fileLoadingUtils.load_settings(self)
        self._file_caches = fileLoadingUtils.load_caches(self)

    def _display_sample(self):
        if self._rules and self._settings:
            # -1を指定することでどこにも色を付けない
            sample_text = validations.make_sample(self._rules, self._settings, -1)
            self._rules_sample.setText(sample_text)

    def _open_rules_dialog(self):
        if self._rules_dialog.exec() == QDialog.Accepted:
            self._rules = fileLoadingUtils.load_rules(self)
            self._update_preview()
            self._display_sample()

    def _on_revert_btn_clicked(self):
        """キャッシュを使ってファイル名を前の状態に戻してプレビュー"""
        self._file_table.blockSignals(True)
        try:
            self._file_table.setRowCount(0)
            self._target_dir = self._file_caches["target_dir"]
            self._dir_label.setText(f"フォルダ: {self._target_dir}")
            self._execute_btn.setEnabled(True)
            
            for original_name, new_name in self._file_caches["filename"].items():
                row = self._file_table.rowCount()
                self._file_table.insertRow(row)

                # 左: 今回の変更前(前回の変更後)
                item_original = QTableWidgetItem(original_name)
                item_original.setFlags(item_original.flags() & ~Qt.ItemIsEditable)
                self._file_table.setItem(row, 0, item_original)

                # 中央: 新しいファイル名(前回の変更前)
                item_new_name = QTableWidgetItem(new_name)
                item_new_name.setFlags(item_new_name.flags() | Qt.ItemIsEditable)
                item_new_name.setForeground(Qt.black)
                self._file_table.setItem(row, 1, item_new_name)

                # 右: ステータス
                item_status = QTableWidgetItem("Ready")
                item_status.setBackground(COLORS["ready"]) 
                item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
                self._file_table.setItem(row, 2, item_status)

            self.stack.setCurrentIndex(1 if self._file_table.rowCount() > 0 else 0)
        
        finally:
            self._file_table.blockSignals(False)

    def load_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "対象のフォルダを選択")
        if dir_path:
            self._process_directory(dir_path)

    def _process_directory(self, dir_path: str):
        self._target_dir = dir_path
        self._dir_label.setText(f"フォルダ: {self._target_dir}")
        self._execute_btn.setEnabled(True)

        self._original_files = []
        target_path = Path(self._target_dir)
        for p in target_path.iterdir():
            if p.is_file() and not p.name.startswith("."):
                self._original_files.append(p.name)

        self._update_preview()

    def _update_preview(self):
        if not self._original_files:
            return
        
        # tableの文字が編集されたときのチェック判定を切っておく
        self._file_table.blockSignals(True)
        try:
            self._file_table.setRowCount(0)
            results = renameCore.rename_all_files(self._original_files, self._rules, self._settings)
            
            for original_name in self._original_files:
                row = self._file_table.rowCount()
                self._file_table.insertRow(row)

                item_original = QTableWidgetItem(original_name)
                item_original.setFlags(item_original.flags() & ~Qt.ItemIsEditable)
                self._file_table.setItem(row, 0, item_original)

                new_file  = results.get(original_name).get("new_file")
                has_error = results.get(original_name).get("has_error")
                has_warn  = results.get(original_name).get("has_warn")

                item_new_name = QTableWidgetItem(new_file)
                item_new_name.setFlags(item_new_name.flags() | Qt.ItemIsEditable)
                item_new_name.setForeground(Qt.black)

                self._file_table.setItem(row, 1, item_new_name)

                item_status = QTableWidgetItem("Ready")
                item_status.setBackground(COLORS["ready"])

                if has_error:
                    item_status.setText("Error")
                    item_status.setBackground(COLORS["error"])
                elif has_warn:
                    item_status.setText("Warning")
                    item_status.setBackground(COLORS["warn"])

                item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
                self._file_table.setItem(row, 2, item_status)

            self.stack.setCurrentIndex(1 if self._file_table.rowCount() > 0 else 0)
        
        finally:
            self._file_table.blockSignals(False)

    def _on_table_cell_changed(self, row, column):
        if column == 1:
            self._file_table.blockSignals(True)
            try:
                item_new_name = self._file_table.item(row, 1)
                item_status = self._file_table.item(row, 2)
                
                if not item_new_name or not item_status:
                    return

                new_file_name = item_new_name.text()

                is_comply = validations.verify_comply_rules(
                    new_file_name, self._rules, self._settings, self._categories
                )

                if is_comply:
                    item_status.setText("Ready")
                    item_status.setBackground(COLORS["ready"]) 
                else:
                    item_status.setText("Edited")
                    item_status.setBackground(COLORS["warn"])
                    
            finally:
                self._file_table.blockSignals(False)

    def save_caches(self):
        caches_dict = {
            "target_dir": self._target_dir,
            "filename": {}
        }

        for row in range(self._file_table.rowCount()):
            original_name = self._file_table.item(row, 0).text()
            new_name = self._file_table.item(row, 1).text()
            caches_dict["filename"][new_name] = original_name

        with open(self._file_caches_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(caches_dict, f,  default_flow_style=False, allow_unicode=True)

    def execute_rename(self):
        is_not_Ready = False
        for row in range(self._file_table.rowCount()):
            if self._file_table.item(row, 2).text() != "Ready":
                is_not_Ready = True
                
        reply = QMessageBox.question(self, "確認", 
                                     "表示されているプレビュー通りにリネームを実行しますか？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return
        
        if is_not_Ready:
            reply = QMessageBox.question(self, "確認", 
                                        "ルール通りでないファイル名があります。このままリネームしますか？",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return
            
        self.save_caches()

        success_count = 0
        error_count = 0
        error_messages = []

        target_path = Path(self._target_dir)

        for row in range(self._file_table.rowCount()):
            original_name = self._file_table.item(row, 0).text()
            new_name = self._file_table.item(row, 1).text()

            if original_name != new_name:
                old_file = target_path / original_name
                new_file = target_path / new_name
                
                if new_file.exists() and original_name.lower() != new_name.lower():
                    error_msg = f"{new_name} は既に存在するためスキップしました。"
                    error_messages.append(error_msg)
                    error_count += 1
                    continue
                
                try:
                    old_file.rename(new_file)
                    success_count += 1
                except Exception as e:
                    error_msg = f"{original_name} の変更に失敗しました: {str(e)}"
                    error_messages.append(error_msg)
                    error_count += 1

        result_msg = f"リネームが完了しました。\n（成功: {success_count}件 / 失敗: {error_count}件）"
        if error_messages:
            QMessageBox.warning(self, "完了（一部エラー）", result_msg + "\n\n" + "\n".join(error_messages[:5]) + ("\n..." if len(error_messages) > 5 else ""))
        else:
            QMessageBox.information(self, "完了", result_msg)
        
        self._process_directory(self._target_dir)
        
        self._file_caches = fileLoadingUtils.load_caches(self)
        if self._file_caches.get("filename"):
            self._revert_file_btn.setEnabled(True)