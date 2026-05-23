import sys
from pathlib import Path
import yaml

from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout,QLabel, QLineEdit, QMessageBox
from PySide6.QtCore import Signal

import fileLoadingUtils
import texts
import validations


class EditSettingsDialog(QDialog):
    # 設定が保存されたことを親ウィンドウに通知するためのシグナル
    settings_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("全体設定")
        self.resize(400, 300)  # テキストエディタが無くなったため縦幅を調整
        self.setModal(True)
        
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        self.yaml_settings_path = base_dir / "settings.yaml"

        self._setup_ui()
        self._spread_settings()

    def _setup_ui(self):
        main_layout = QFormLayout()

        self._date_format_combo = QComboBox()
        self._date_format_combo.addItem("年月日", "YMD")
        self._date_format_combo.addItem("日月年", "DMY")
        self._date_format_combo.addItem("月日年", "MDY")
        main_layout.addRow("元の日付順:", self._date_format_combo)

        self._delimiter_edit = QLineEdit("_")
        self._delimiter_edit.setFixedWidth(40)
        main_layout.addRow("区切り文字:", self._delimiter_edit)

        self._sequence_style_combo = QComboBox()
        self._sequence_style_combo.addItem("常につける", "always")
        self._sequence_style_combo.addItem("被りのみ", "all_overlaps")
        self._sequence_style_combo.addItem("なし(非推奨)", "false")
        self._sequence_style_combo.setCurrentIndex(1)
        self._sequence_style_combo.setToolTip("変換後に同名のファイルが生まれる場合に連番を振るかどうかを設定できます。")
        main_layout.addRow("連番:", self._sequence_style_combo)

        self._sequence_format_edit = QLineEdit("(n)")
        self._sequence_format_edit.setToolTip("「n」が連番の数字で置き換えられます。\n「nnn」のように2つ以上重ねるとその桁までゼロ埋めされます。")
        self._sequence_format_edit.setPlaceholderText("(n)")
        main_layout.addRow("連番の形式:", self._sequence_format_edit)

        explanation = QLabel("\n一部の設定はマウスオーバーで説明が表示されます。\n")
        explanation.setWordWrap(True)
        main_layout.addRow(explanation)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("キャンセル")
        button_box.accepted.connect(self.save_file)
        button_box.rejected.connect(self.reject)
        main_layout.addRow(button_box)

        # レイアウトをダイアログに適用
        self.setLayout(main_layout)

    def _spread_settings(self):
        settings = fileLoadingUtils.load_settings(self)

        # UIの各フォームに値をセット
        idx = self._date_format_combo.findData(settings.get("original_date_format", "YMD"))
        if idx >= 0: self._date_format_combo.setCurrentIndex(idx)

        self._delimiter_edit.setText(settings.get("delimiter", "_"))

        seq_data = settings.get("sequence", {})
        idx_seq = self._sequence_style_combo.findData(seq_data.get("style", "allOverlaps"))
        if idx_seq >= 0: self._sequence_style_combo.setCurrentIndex(idx_seq)

        self._sequence_format_edit.setText(seq_data.get("format", "(n)"))

    def _write_default_settings(self):
        """デフォルトの設定ファイルを書き出す"""
        try:
            with open(self.yaml_settings_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["settings"], f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Failed to write default settings: {e}")

    def save_file(self):
        """UIの入力内容を辞書にまとめ、YAMLファイルへ保存する"""
        # UIからデータを回収して辞書を作成
        settings = {
            "original_date_format": self._date_format_combo.currentData(),
            "delimiter": self._delimiter_edit.text(),
            "sequence": {
                "style": self._sequence_style_combo.currentData(),
                "format": self._sequence_format_edit.text()
            }
        }

        try:
            validations.check_settings(settings)
        except Exception as e:
            QMessageBox.critical(self, "エラー", e)  
            return
        
        try:
            with open(self.yaml_settings_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(settings, f, default_flow_style=False, allow_unicode=True)
            
            # 親画面に設定が変わったことを通知
            self.settings_updated.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")