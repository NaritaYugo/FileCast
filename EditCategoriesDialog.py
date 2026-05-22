import yaml

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit, QPushButton,QVBoxLayout
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal

import fileLoadingUtils
import texts
import validations


# Tabをスペース2つ分に変更して入力する
class YamlEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            cursor = self.textCursor()
            cursor.insertText("  ")
            return
            
        super().keyPressEvent(event)

class EditCategoriesDialog(QDialog):
    # カテゴリが保存されたことを親ウィンドウに通知するためのシグナル
    categories_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("カテゴリの編集 (YAML)")
        self.resize(600, 500)
        self.setModal(True)

        base_dir = fileLoadingUtils.get_base_dir()
        self.categories_path = base_dir / "categories.yaml"

        self._setup_ui()
        self.categories = fileLoadingUtils.load_categories(self)
        self.edit_categories.setPlainText(yaml.safe_dump(self.categories, default_flow_style=False, allow_unicode=True))

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        header_label = QLabel("YAML形式でカテゴリを定義してください。保存時に構文チェックが行われます。")
        main_layout.addWidget(header_label)

        open_reference_button = QPushButton("記述方法リファレンス")
        open_reference_button.clicked.connect(lambda: QMessageBox.information(self, "リファレンス", texts.CATEGORY_REFERENCE))
        main_layout.addWidget(open_reference_button)

        self.edit_categories = YamlEditor()
        
        # 等幅フォント
        font = QFont("Consolas")
        if font.insertSubstitution("Consolas", "Meiryo UI"):
            font = QFont("Meiryo UI")
        font.setPointSize(10) 
        self.edit_categories.setFont(font)

        main_layout.addWidget(self.edit_categories)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("キャンセル")
        button_box.accepted.connect(self._save_categories)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def _save_categories(self):
        """エディタの内容をバリデーションした上でYAMLファイルへ保存する"""
        content = self.edit_categories.toPlainText()
        
        try:
            parsed_data = yaml.safe_load(content)
            validations.check_categories(parsed_data)
        except Exception as e:
            QMessageBox.critical(self, "エラー", e)  
            return
        
        # 保存
        try:
            with open(self.categories_path, "w", encoding="utf-8") as f:
                f.write(content)
            
            # 親画面にカテゴリが更新されたことを通知
            self.categories_updated.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイルの保存に失敗しました:\n{e}")