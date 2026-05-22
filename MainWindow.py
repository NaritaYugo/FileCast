import sys
from pathlib import Path
import yaml

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                               QLabel, QDialog, QFileDialog, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QStackedLayout)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

import validations
import renameCore
import RuleBuilderDialog
import fileLoadingUtils


COLORS = {"ready": QColor("#54CE41"), "warn": QColor("#FFF200"), "error": QColor("#FF4949")}

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

        self.rule = []
        self.settings = {}

        self.target_dir = ""
        self.file_list = []
        self.cache = {}

        base_dir = fileLoadingUtils.get_base_dir()
            
        self.cache_path = base_dir / "cache.yaml"

        self.rule_dialog = RuleBuilderDialog.RuleBuilderDialog(self)

        self.setup_ui()

        self._ensure_yamls_exsist()
        if self.cache.get("filename"):
            self.apply_cache_btn.setEnabled(True)

        self._display_sample()

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 上段: フォルダ読み込み
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        self.dir_label = QLabel("フォルダ: 未選択")
        self.dir_label.setStyleSheet("background-color: #2b2b2b; color: white; padding: 5px;")
        top_layout.addWidget(self.dir_label, stretch=1)

        load_btn = QPushButton("📂 フォルダを選択")
        load_btn.setStyleSheet("padding: 5px;")
        load_btn.clicked.connect(self._load_directory)
        top_layout.addWidget(load_btn)

        self.apply_cache_btn = QPushButton("元に戻す")
        self.apply_cache_btn.setStyleSheet("padding: 5px;")
        self.apply_cache_btn.clicked.connect(self._apply_cache)
        self.apply_cache_btn.setEnabled(False)
        top_layout.addWidget(self.apply_cache_btn)

        # 中段: ファイルリスト
        self.stack = QStackedLayout()
        main_layout.addLayout(self.stack)

        self.label = DropLabel("フォルダを選択またはドラッグアンドドロップしてください")
        self.label.setStyleSheet("color:gray; font-size: 16px")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.folder_dropped.connect(self._process_directory)
        self.stack.addWidget(self.label)

        self.table = DropTableWidget()
        self.table.folder_dropped.connect(self._process_directory)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["元のファイル名", "変換後のプレビュー(ダブルクリックで編集)", "ステータス"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.cellChanged.connect(self._on_table_cell_changed)
        self.stack.addWidget(self.table)

        # 下段: 設定、リネーム実行
        bottom_layout = QHBoxLayout()
        main_layout.addLayout(bottom_layout)

        setting_btn = QPushButton("⚙️ 命名規則の設定")
        setting_btn.setStyleSheet("background-color: #007ACC; color: white; padding: 10px 30px;")
        setting_btn.clicked.connect(self._open_rule_dialog)
        bottom_layout.addWidget(setting_btn, 1)

        self.rule_sample = QLabel("命名規則を設定してください")
        self.rule_sample.setStyleSheet("background-color: white; padding: 10px 30px;")
        bottom_layout.addWidget(self.rule_sample, 3)

        self.execute_btn = QPushButton("リネーム実行")
        self.execute_btn.setStyleSheet("background-color: #d9534f; color: white; padding: 10px 30px;")
        self.execute_btn.clicked.connect(self._execute_rename)
        self.execute_btn.setEnabled(False)
        bottom_layout.addWidget(self.execute_btn, 1)

    def _ensure_yamls_exsist(self):
        """yamlファイルが無ければ新規作成する"""
        self.categories = fileLoadingUtils.load_categories(self, display_alert=False)
        self.rule =fileLoadingUtils.load_rule(self, display_alert=False)
        self.settings = fileLoadingUtils.load_settings(self, display_alert=False)
        self.cache = fileLoadingUtils.load_cache(self, display_alert=False)

    def _display_sample(self):
        if self.rule and self.settings:
            # -1を指定することで文字のどこにも色を付けない
            sample_text = validations.make_sample(self.rule, self.settings, -1)
            self.rule_sample.setText(sample_text)

    def _open_rule_dialog(self):
        if self.rule_dialog.exec() == QDialog.Accepted:
            self.rule = fileLoadingUtils.load_rule(self)
            self._update_preview()
            self._display_sample()

    def _apply_cache(self):
        """キャッシュを使ってファイル名を前の状態に戻してプレビュー"""
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            self.target_dir = self.cache["target_dir"]
            self.dir_label.setText(f"フォルダ: {self.target_dir}")
            self.execute_btn.setEnabled(True)
            
            for original_name, new_name in self.cache["filename"].items():
                row = self.table.rowCount()
                self.table.insertRow(row)

                # 左: 今回の変更前(前回の変更後)
                item_original = QTableWidgetItem(original_name)
                item_original.setFlags(item_original.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 0, item_original)

                # 中央: 新しいファイル名(前回の変更前)
                item_new_name = QTableWidgetItem(new_name)
                item_new_name.setFlags(item_new_name.flags() | Qt.ItemIsEditable)
                item_new_name.setForeground(Qt.black)
                self.table.setItem(row, 1, item_new_name)

                # 右: ステータス
                item_status = QTableWidgetItem("Ready")
                item_status.setBackground(COLORS["ready"]) 
                item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 2, item_status)

            self.stack.setCurrentIndex(1 if self.table.rowCount() > 0 else 0)
        
        finally:
            self.table.blockSignals(False)

    def _load_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "対象のフォルダを選択")
        if dir_path:
            self._process_directory(dir_path)

    def _process_directory(self, dir_path: str):
        self.target_dir = dir_path
        self.dir_label.setText(f"フォルダ: {self.target_dir}")
        self.execute_btn.setEnabled(True)

        self.file_list = []
        target_path = Path(self.target_dir)
        for p in target_path.iterdir():
            if p.is_file() and not p.name.startswith("."):
                self.file_list.append(p.name)

        self._update_preview()

    def _update_preview(self):
        if not self.file_list:
            return
        
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            results = renameCore.rename_all_files(self.file_list, self.rule, self.settings)
            
            for original_name in self.file_list:
                row = self.table.rowCount()
                self.table.insertRow(row)

                item_original = QTableWidgetItem(original_name)
                item_original.setFlags(item_original.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 0, item_original)

                new_file  = results.get(original_name).get("new_file")
                has_error = results.get(original_name).get("has_error")
                has_warn  = results.get(original_name).get("has_warn")

                item_new_name = QTableWidgetItem(new_file)
                item_new_name.setFlags(item_new_name.flags() | Qt.ItemIsEditable)
                item_new_name.setForeground(Qt.black)

                self.table.setItem(row, 1, item_new_name)

                item_status = QTableWidgetItem("Ready")
                item_status.setBackground(COLORS["ready"])

                if has_error:
                    item_status.setText("Error")
                    item_status.setBackground(COLORS["error"])
                elif has_warn:
                    item_status.setText("Warning")
                    item_status.setBackground(COLORS["warn"])

                item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, 2, item_status)

            self.stack.setCurrentIndex(1 if self.table.rowCount() > 0 else 0)
        
        finally:
            self.table.blockSignals(False)

    def _on_table_cell_changed(self, row, column):
        if column == 1:
            # プログラム側からステータスを書き換えた際に、無限ループになるのを防ぐ
            self.table.blockSignals(True)
            try:
                item_new_name = self.table.item(row, 1)
                item_status = self.table.item(row, 2)
                
                if not item_new_name or not item_status:
                    return

                new_file_name = item_new_name.text()

                is_comply = validations.verify_comply_rule(
                    new_file_name, self.rule, self.settings, self.categories
                )

                if is_comply:
                    item_status.setText("Ready")
                    item_status.setBackground(COLORS["ready"]) 
                else:
                    item_status.setText("Edited")
                    item_status.setBackground(COLORS["warn"])
                    
            finally:
                self.table.blockSignals(False)

    def _save_cache(self):
        cache_dict = {
            "target_dir": self.target_dir,
            "filename": {}
        }

        for row in range(self.table.rowCount()):
            original_name = self.table.item(row, 0).text()
            new_name = self.table.item(row, 1).text()
            cache_dict["filename"][new_name] = original_name

        with open(self.cache_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cache_dict, f,  default_flow_style=False, allow_unicode=True)

    def _execute_rename(self):
        is_not_Ready = False
        for row in range(self.table.rowCount()):
            if self.table.item(row, 2).text() != "Ready":
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
            
        self._save_cache()

        success_count = 0
        error_count = 0
        error_messages = []

        target_path = Path(self.target_dir)

        for row in range(self.table.rowCount()):
            original_name = self.table.item(row, 0).text()
            new_name = self.table.item(row, 1).text()

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
        
        self._process_directory(self.target_dir)
        
        self.cache = fileLoadingUtils.load_cache(self)
        if self.cache.get("filename"):
            self.apply_cache_btn.setEnabled(True)