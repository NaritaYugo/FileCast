import re
import yaml

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QMessageBox, QPlainTextEdit, QPushButton,QVBoxLayout
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("カテゴリの編集 (YAML)")
        self.resize(600, 500)
        self.setModal(True)

        self._categories_path = fileLoadingUtils.get_base_dir() / "categories.yaml"

        self._setup_ui()
    
    def showEvent(self, arg__1):
        super().showEvent(arg__1)
        _, _category_plane_text = fileLoadingUtils.load_categories(self)
        # [] の削除と、グループごとに空行を挟む
        cleaned_text = _category_plane_text.replace("[", "").replace("]", "")
        display_text = re.sub(r"\n(?=\S+:)", r"\n\n", cleaned_text)
        self._edit_categories.setPlainText(display_text)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        header_label = QLabel("YAML形式でカテゴリを定義してください。保存時に構文チェックが行われます。")
        main_layout.addWidget(header_label)

        open_reference_button = QPushButton("記述方法リファレンス")
        open_reference_button.clicked.connect(
            lambda: QMessageBox.information(self, "リファレンス", texts.CATEGORY_REFERENCE)
            )
        main_layout.addWidget(open_reference_button)

        self._edit_categories = YamlEditor()
        
        # 等幅フォント
        font = QFont("Consolas")
        if font.insertSubstitution("Consolas", "Meiryo UI"):
            font = QFont("Meiryo UI")
        font.setPointSize(10) 
        self._edit_categories.setFont(font)

        main_layout.addWidget(self._edit_categories)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("キャンセル")
        button_box.accepted.connect(self.save_categories)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def save_categories(self):
        """エディタの内容をバリデーションした上でYAMLファイルへ保存する"""
        cat_text = self._edit_categories.toPlainText()
        
        try:
            cat_dict = yaml.safe_load(cat_text)
            valid_cat_dict = validations.convert_to_valid_categories(cat_dict)
        except yaml.scanner.ScannerError:
            QMessageBox.critical(self, "エラー", "yaml形式が正しくありません。\
                \nインデントが正しいか、コロンの後にスペースが入っているかを確認してください。") 
            return
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"{e}")  
            return
        
        yaml.add_representer(fileLoadingUtils.FlowStyleList, fileLoadingUtils.flow_style_list_representer)

        try:
            with open(self._categories_path, "w", encoding="utf-8") as f:
                yaml.dump(valid_cat_dict, f, sort_keys=False, allow_unicode=True)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイルの保存に失敗しました:\n{e}")