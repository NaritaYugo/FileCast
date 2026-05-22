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

        self.combo_date_format = QComboBox()
        self.combo_date_format.addItem("年月日", "YMD")
        self.combo_date_format.addItem("日月年", "DMY")
        self.combo_date_format.addItem("月日年", "MDY")
        main_layout.addRow("元の日付順:", self.combo_date_format)

        self.input_delimiter = QLineEdit("_")
        self.input_delimiter.setFixedWidth(40)
        main_layout.addRow("区切り文字:", self.input_delimiter)

        self.use_sequence = QComboBox()
        self.use_sequence.addItem("常につける", "always")
        self.use_sequence.addItem("被りのみ", "all_overlaps")
        self.use_sequence.addItem("なし(非推奨)", "false")
        self.use_sequence.setCurrentIndex(1)
        self.use_sequence.setToolTip("変換後に同名のファイルが生まれる場合に連番を振るかどうかを設定できます。")
        main_layout.addRow("連番:", self.use_sequence)

        self.sequence_format = QLineEdit("(n)")
        self.sequence_format.setToolTip("「n」が連番の数字で置き換えられます。\n「nnn」のように2つ以上重ねるとその桁までゼロ埋めされます。")
        self.sequence_format.setPlaceholderText("(n)")
        main_layout.addRow("連番の形式:", self.sequence_format)

        explanation = QLabel("\n一部の設定はマウスオーバーで説明が表示されます。\n")
        explanation.setWordWrap(True)
        main_layout.addRow(explanation)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("キャンセル")
        button_box.accepted.connect(self._save_file)
        button_box.rejected.connect(self.reject)
        main_layout.addRow(button_box)

        # レイアウトをダイアログに適用
        self.setLayout(main_layout)

    def _spread_settings(self):
        settings = fileLoadingUtils.load_settings(self)

        # UIの各フォームに値をセット
        idx = self.combo_date_format.findData(settings.get("original_date_format", "YMD"))
        if idx >= 0: self.combo_date_format.setCurrentIndex(idx)

        self.input_delimiter.setText(settings.get("delimiter", "_"))

        seq_data = settings.get("sequence", {})
        idx_seq = self.use_sequence.findData(seq_data.get("style", "allOverlaps"))
        if idx_seq >= 0: self.use_sequence.setCurrentIndex(idx_seq)

        self.sequence_format.setText(seq_data.get("format", "(n)"))

    def _write_default_settings(self):
        """デフォルトの設定ファイルを書き出す"""
        try:
            with open(self.yaml_settings_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["settings"], f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Failed to write default settings: {e}")

    def _save_file(self):
        """UIの入力内容を辞書にまとめ、YAMLファイルへ保存する"""
        # UIからデータを回収して辞書を作成
        settings = {
            "original_date_format": self.combo_date_format.currentData(),
            "delimiter": self.input_delimiter.text(),
            "sequence": {
                "style": self.use_sequence.currentData(),
                "format": self.sequence_format.text()
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