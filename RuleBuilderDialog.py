import re
import yaml

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox,  QComboBox, QDialog, QDialogButtonBox, 
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListView, 
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, 
                               QVBoxLayout, QWidget)
from PySide6.QtCore import Qt, QSize, Signal

import EditCategoriesDialog
import EditSettingsDialog
import fileLoadingUtils
import styles
import validations


DEFALT_BLOCKS = {
    "DATE": {"kind": "DATE", "format": "YYYY-MM-DD"},
    "NAME": {"kind": "NAME", "remove_internal_delimiter": True},
    "VERSION": {"kind": "VERSION", "prefix": "ver_", "format": "n.n.nnn"}
}

class PaletteBlock(QListWidgetItem):
    """素材パレット専用のアイテムクラス"""
    def __init__(self, kind):
        super().__init__(kind)
        self.kind = kind

class DragableBlockWidget(QWidget):
    """QListWidgetのドラッグ操作を妨げないためのカスタムウィジェット"""
    def mousePressEvent(self, event):
        # イベントを無視して親のQListWidgetに伝播させる
        event.ignore()

class SortableListWidget(QListWidget):
    order_changed = Signal()
    palette_dropped = Signal(str, int)  # (kind, 挿入する行)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

        # スクロールバーの状態変化を監視
        self.horizontalScrollBar().rangeChanged.connect(self._adjust_height_for_scrollbar)

    def showEvent(self, event):
        super().showEvent(event)
        # 画面に配置され、レイアウトやスクロールバーの実際のサイズが確定した後に計算する
        self._adjust_height_for_scrollbar()

    def _adjust_height_for_scrollbar(self):
        """スクロールバーが表示されているならウィジェットの高さを伸ばす"""
        base_height = 55  # スクロールバーがない時の高さ
        
        if self.horizontalScrollBar().maximum() > 0:
            scrollbar_height = self.horizontalScrollBar().height()
            self.setFixedHeight(base_height + scrollbar_height)
        else:
            self.setFixedHeight(base_height)

    def dropEvent(self, event):
        source = event.source()
        if not source:
            return

        position = event.position().toPoint()
        target_block = self.itemAt(position)
        drop_row = self.row(target_block) if target_block else self.count()

        if source == self:
            current_block = self.currentItem()
            if not current_block:
                return
            current_row = self.row(current_block)
            
            if current_row == -1 or current_row == drop_row:
                return
            
            # 右に動かす場合は、自分が抜ける分だけインデックスが1つズレるのを防ぐ
            if current_row < drop_row:
                drop_row -= 1
                
            block = self.takeItem(current_row)
            self.insertItem(drop_row, block)
            self.setCurrentItem(block)
            
            event.setDropAction(Qt.DropAction.IgnoreAction) 
            event.accept()
        else:
            # 素材パレットからの追加
            selected_block = source.currentItem()
            if selected_block and hasattr(selected_block, 'kind'):
                self.palette_dropped.emit(selected_block.kind, drop_row)
                event.accept()
        
        self.order_changed.emit()
        self._adjust_height_for_scrollbar()

class RuleBlock(QListWidgetItem):
    def __init__(self, element):
        super().__init__("")
        self.element = element
        self.kind = element.get("kind", "")

class RuleBuilderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("命名規則ビルダー")
        self.resize(850, 600)
        self.setModal(True) 

        base_dir = fileLoadingUtils.get_base_dir()
        self._rules_path = base_dir / "rules.yaml"

        self._categories, _ = fileLoadingUtils.load_categories(self)

        self._setup_ui()

        self.settings_dialog = EditSettingsDialog.EditSettingsDialog(self)
        self.categories_dialog = EditCategoriesDialog.EditCategoriesDialog(self)

    def showEvent(self, event):
        super().showEvent(event)
        self._spread_rules()
        self._setup_palette()
        self._call_make_sample()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        split_layout = QHBoxLayout()
        left_layout = QVBoxLayout()

        # 左上：サンプルを表示
        sample_group = QGroupBox("サンプル")
        sample_layout = QVBoxLayout()
        self._sample_label = QLabel()
        self._sample_label.setStyleSheet(styles.RuleStyle.SAMPLE_LABEL)
        self._sample_label.setWordWrap(True)
        self._sample_label.setAlignment(Qt.AlignCenter)
        self._sample_label.setTextFormat(Qt.RichText)
        sample_layout.addWidget(self._sample_label)
        sample_group.setLayout(sample_layout)
        left_layout.addWidget(sample_group)

        # 左中：現在のルール
        rules_group = QGroupBox("ブロック追加・並び替え")
        rules_layout = QVBoxLayout()

        rules_layout.addWidget(QLabel("現在のルール順序（ドラッグで並び替え / ×で削除）:"))
        self._block_list = SortableListWidget()
        self._block_list.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        self._block_list.setFlow(QListView.LeftToRight)
        self._block_list.setWrapping(False)
        self._block_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self._block_list.setStyleSheet(styles.RuleStyle.RULE_BLOCK_LIST)
        self._block_list.itemSelectionChanged.connect(self._on_block_selected)
        
        self._block_list.order_changed.connect(self._refresh_list_widgets)
        self._block_list.order_changed.connect(self._call_make_sample)
        self._block_list.palette_dropped.connect(self._on_block_dropped)
        rules_layout.addWidget(self._block_list)

        # 左下：素材パレット
        rules_layout.addWidget(QLabel("利用可能なブロック（上にドラッグ＆ドロップして追加）:"))
        self._palette_list = QListWidget()
        self._palette_list.setFlow(QListView.LeftToRight)

        self._palette_list.setWrapping(True)
        self._palette_list.setResizeMode(QListView.Adjust)
        self._palette_list.setGridSize(QSize(105, 40)) 
        self._palette_list.setSpacing(4)

        self._palette_list.setDragEnabled(True)
        self._palette_list.setAcceptDrops(False)
        self._palette_list.setStyleSheet(styles.RuleStyle.PALLETE_LIST)
        rules_layout.addWidget(self._palette_list)

        rules_group.setLayout(rules_layout)
        left_layout.addWidget(rules_group)

        # 右：詳細設定
        right_group = QGroupBox("詳細設定")
        right_layout = QVBoxLayout()

        self._property_placeholder = QLabel('ブロックを選択してください')
        self._property_placeholder.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self._property_placeholder)

        self._property_container = QWidget()
        self.detail_form_layout = QFormLayout(self._property_container)
        self._property_container.hide()
        right_layout.addWidget(self._property_container)
        right_layout.addStretch()

        right_group.setLayout(right_layout)
        
        # ブロックがたくさん追加されても横幅が伸びないように、一度コンテナに載せる
        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        split_layout.addWidget(left_container, 3)
        split_layout.addWidget(right_group, 2)
        main_layout.addLayout(split_layout)

        # 下：ボタン類
        bottom_layout = QHBoxLayout()
        
        settings_btn = QPushButton("全体設定")
        settings_btn.clicked.connect(self._on_settings_btn_clicked)
        bottom_layout.addWidget(settings_btn)

        category_btn = QPushButton("カテゴリの編集")
        category_btn.clicked.connect(self._on_category_btn_clicked)
        bottom_layout.addWidget(category_btn)
        
        bottom_layout.addStretch()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("キャンセル")
        button_box.accepted.connect(self.save_rules)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)
        
        main_layout.addLayout(bottom_layout)

    def _setup_palette(self):
        """素材パレットの表示を更新"""
        self._palette_list.clear()
        if not self._categories:
            return

        kinds = list(DEFALT_BLOCKS.keys()) + sorted(list(self._categories.keys()))

        for kind in kinds:
            block = PaletteBlock(kind)
            block.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            block.setSizeHint(QSize(100, 32))
            self._palette_list.addItem(block)

    def _spread_rules(self):
        """rules.yamlから現在の配置ルールをロードして画面に並べる"""
        self._block_list.clear()

        self.rules = fileLoadingUtils.load_rules(self)
        for element in self.rules:
            # Blockを生成
            block = RuleBlock(element)
            self._block_list.addItem(block)

        self._refresh_list_widgets()

    def _spread_tmp_rules(self):
        """カテゴリに更新があった場合にブロックを更新して置き直す"""
        self._block_list.clear()
        
        for element in self._rules_tmp_blocks:
            kind = element.get("kind", "")

            if kind not in self._categories and kind not in DEFALT_BLOCKS:
                continue

            if kind in self._categories:
                category = self._categories.get(kind, {})
                requirement = category.pop("REQ", "")
                if "_" in requirement:
                    requirement = ""

                element = {
                    "kind": kind,
                    "requirement": requirement,
                    "items": category
                }
                
            block = RuleBlock(element)
            self._block_list.addItem(block)

        self._refresh_list_widgets()

    def _on_block_dropped(self, kind, row):
        if kind in DEFALT_BLOCKS:
            element = DEFALT_BLOCKS[kind].copy()
        else:
            category = self._categories.get(kind, {})
            requirement = category.pop("REQ", "")

            element = {
                "kind": kind,
                "requirement": requirement,
                "items": category
            }

        block = RuleBlock(element)
        block.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._block_list.insertItem(row, block)
        self._block_list.setCurrentItem(block)
        
        self._refresh_list_widgets()
        self._call_make_sample()

    def _on_block_selected(self):
        """現在のルールリストでブロックが選択された際、詳細設定フォームを切り替える"""
        # 既存の行をすべてクリア
        while self.detail_form_layout.rowCount() > 0:
            self.detail_form_layout.removeRow(0)

        selected_blocks = self._block_list.selectedItems()
        if not selected_blocks:
            self._property_placeholder.show()
            self._property_container.hide()
            return
        
        self._call_make_sample()

        self._property_placeholder.hide()
        self._property_container.show()
        
        block = selected_blocks[0]
        element = block.element

        if block.kind == "DATE":
            self.date_edit = QLineEdit(element.get("format", "YYYY-MM-DD"))
            self.date_edit.textChanged.connect(lambda text: element.update({"format": text}))
            self.date_edit.textChanged.connect(self._call_make_sample)
            self.detail_form_layout.addRow("フォーマット:", self.date_edit)

        elif block.kind == "NAME":
            self.name_chk = QCheckBox()
            self.name_chk.setChecked(element.get("remove_internal_delimiter", True))
            self.name_chk.stateChanged.connect(lambda state: element.update({"remove_internal_delimiter": state == Qt.CheckState.Checked.value}))
            self.name_chk.stateChanged.connect(self._call_make_sample)
            self.detail_form_layout.addRow("内部区切り文字を削除:", self.name_chk)
            
        elif block.kind == "VERSION":
            self.ver_prefix_edit = QLineEdit(element.get("prefix", "ver_"))
            self.ver_prefix_edit.textChanged.connect(lambda text: element.update({"prefix": text}))
            self.ver_prefix_edit.textChanged.connect(self._call_make_sample)
            self.detail_form_layout.addRow("接頭辞(空欄可):", self.ver_prefix_edit)

            self.ver_format_edit = QLineEdit(element.get("format", "n.n.nnn"))
            self.ver_format_edit.textChanged.connect(lambda text: element.update({"format": text}))
            self.ver_format_edit.textChanged.connect(self._call_make_sample)
            self.detail_form_layout.addRow("数字の形式:", self.ver_format_edit)
            
        else:
            requirement = element.get("requirement")
            if not requirement or "_ASTERISK" in requirement:
                req_text = "要件: なし (常に適用)"
            elif "_EXCLAMATION" in requirement:
                req_text = "要件: 以下のいずれかのパターンが存在する場合のみ"
            else:
                req_text = f"要件: {", ".join(element.get("requirement"))} が存在する場合のみ"
            self.detail_form_layout.addRow(QLabel(req_text))

            for item, patterns in element.get("items").items():
                self.detail_form_layout.addRow(QLabel(f"・{item} <- {", ".join(patterns)}"))

    def _on_category_btn_clicked(self):
        # 現在の情報を保存
        self._rules_tmp_blocks = self._get_current_rules()
        selected_row = self._block_list.currentRow()

        # 戻ってきたときに同期、復元
        if self.categories_dialog.exec() == QDialog.Accepted:
            self._categories, _ = fileLoadingUtils.load_categories(self)
            self._spread_tmp_rules()
            self._setup_palette()

            if selected_row >= 0 and selected_row < self._block_list.count():
                self._block_list.setCurrentRow(selected_row)
                
            self._call_make_sample()
            self._rules_tmp_blocks = []

    def _on_settings_btn_clicked(self):
        self._rules_tmp_blocks = self._get_current_rules()
        selected_row = self._block_list.currentRow()
        if self.settings_dialog.exec() == QDialog.Accepted:
            self._spread_tmp_rules()

            if selected_row >= 0 and selected_row < self._block_list.count():
                self._block_list.setCurrentRow(selected_row)

            self._call_make_sample()
            self._rules_tmp_blocks = []

    def _adjust_sample_font_size(self, text):
        """テキストがラベルの横幅に1行で収まるようにフォントサイズを動的に調節する"""
        from PySide6.QtGui import QFont, QFontMetrics
        
        max_size = 12
        min_size = 3
        
        font = QFont()
        font.setBold(True)
        
        available_width = self._sample_label.width()
        if available_width <= 0:
            available_width = 300
            
        plain_text = re.sub(r'<[^>]*>', '', text)

        suitable_size = min_size
        for size in range(max_size, min_size - 1, -1):
            font.setPointSize(size)
            metrics = QFontMetrics(font)
            text_width = metrics.horizontalAdvance(plain_text)
            
            if text_width <= available_width:
                suitable_size = size
                break
                
        font.setPointSize(suitable_size)
        self._sample_label.setFont(font)
        
        self._sample_label.setText(text)

    def _call_make_sample(self):
        settings = fileLoadingUtils.load_settings(self)
        rules_blocks = self._get_current_rules()
        selected_index = self._block_list.currentRow()
        
        try:
            sample_text = validations.make_sample(rules_blocks, settings, selected_index)
            self._adjust_sample_font_size(sample_text)
        except Exception as e:
            self._adjust_sample_font_size(f"<span style='color:gray;'>サンプルを利用できません: {e}</span>")

    def _refresh_list_widgets(self):
        for i in range(self._block_list.count()):
            block = self._block_list.item(i)
            display_text = getattr(block, "display_text", block.kind)
            
            widget = DragableBlockWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(8, 4, 4, 2) 
            layout.setSpacing(6)
            
            label = QLabel(display_text)
            label.setStyleSheet(styles.RuleStyle.RULE_BLOCK_LABEL)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)
            
            close_btn = QPushButton("×")
            close_btn.setFixedSize(14, 14)
            close_btn.setStyleSheet(styles.RuleStyle.DELETE_BLOCK_BTN)
            close_btn.clicked.connect(lambda _, b=block: self._delete_block(b))
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)
            
            widget.setStyleSheet("background: transparent;")
            block.setSizeHint(widget.sizeHint())

            size = widget.sizeHint()
            # リストアイテム枠の余白分として、横幅を少しだけ拡張する
            block.setSizeHint(QSize(size.width() + 6, size.height()))

            self._block_list.setItemWidget(block, widget)

    def _delete_block(self, block):
        row = self._block_list.row(block)
        if row >= 0:
            self._block_list.takeItem(row)
            self._on_block_selected()
            self._refresh_list_widgets() 
            self._call_make_sample()

    def _get_current_rules(self):
        """画面上のブロック群をルールとしてパッキング"""
        rules_blocks = []
        for i in range(self._block_list.count()):
            element = self._block_list.item(i).element
            rules_blocks.append(element)
        return rules_blocks

    def save_rules(self):
        rules_blocks = self._get_current_rules()
        
        try:
            validations.check_rules(rules_blocks, self._categories)
        except Exception as e:
            QMessageBox.warning(self, "命名規則エラー", str(e))
            return

        try:
            with open(self._rules_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(rules_blocks, f, default_flow_style=False, allow_unicode=True)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")
