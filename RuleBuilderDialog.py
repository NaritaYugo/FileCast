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
import texts
import validations


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
        
        kind = element.get("kind", "")
        # kind が "group{texts.kind_separator}category" の形式なら "group" を、そうでないなら kind を表示名とする
        self.display_text = kind.split(texts.kind_separator)[0] if texts.kind_separator in kind else kind
        self.kind = self.display_text

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
        """素材パレットの表示を更新 (グループ名のみを表示)"""
        self._palette_list.clear()
        if not self._categories:
            return
        
        kinds = ["VERSION", "DATE", "NAME"]
        kinds.extend(sorted(self._categories.keys()))
            
        for kind in kinds:
            block = PaletteBlock(kind)
            block.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            block.setSizeHint(QSize(100, 32))
            if kind in ("DATE", "NAME", "VERSION"):
                block.setBackground(Qt.GlobalColor.darkBlue)
            else:
                block.setBackground(Qt.GlobalColor.darkGreen)
            self._palette_list.addItem(block)

    def _sync_tmp_rules(self):
        """最新のカテゴリ定義(self._categories)を元に、一時退避中のブロック群を精査・更新する"""

        synced_blocks = []
        for element in self._rules_tmp_blocks:
            kind = element.get("kind", "")
            
            if texts.kind_separator in kind:
                group_name, current_target = kind.split(texts.kind_separator, 1)
                
                # グループ自体が消滅していたら、このブロックは破棄
                if group_name not in self._categories:
                    continue
                
                group = self._categories[group_name]
                categories = [c for c in group.keys() if c != "REQ"]
                
                if current_target not in categories:
                    if categories:
                        # 他に利用可能なターゲットがあれば、先頭のものに切り替える
                        current_target = categories[0]
                    else:
                        continue
                
                # 中身をデータ同期
                element["kind"] = group_name + texts.kind_separator + current_target
                
                requirement_str = group.get("REQ", "_")
                if requirement_str == "_":
                    element["requirement"] = []
                else: 
                    element["requirement"] = [r.strip() for r in str(requirement_str).split(",") if r.strip()]
                
                target_elements = group.get(current_target, "")
                if isinstance(target_elements, list):
                    element["target"] = target_elements
                else:
                    element["target"] = [t.strip() for t in str(target_elements).split(",") if t.strip()]
            
            synced_blocks.append(element)
            
        self._rules_tmp_blocks = synced_blocks

    def _spread_rules(self):
        """rules.yamlから現在の配置ルールをロードして画面に並べる"""
        self._block_list.clear()

        self.rules = fileLoadingUtils.load_rules(self)
        for element in self.rules:
            kind = element.get("kind", "")
            
            # ユーザー定義カテゴリの場合、UI用の補助プロパティを復元する
            if texts.kind_separator in kind:
                group_name, target = kind.split(texts.kind_separator, 1)
                element["_group"] = group_name
                element["_selected_target"] = target
            
            # Blockを生成
            block = RuleBlock(element)
            self._block_list.addItem(block)

        self._refresh_list_widgets()

    def _spread_tmp_rules(self):
        """カテゴリファイルが変わった時に現在配置されているブロックをチェック・同期する"""
        self._block_list.clear()

        for element in self._rules_tmp_blocks:
            kind = element.get("kind", "")
            
            # ユーザー定義カテゴリの場合、UI用の補助プロパティを復元する
            if texts.kind_separator in kind:
                group_name, target = kind.split(texts.kind_separator, 1)
                element["_group"] = group_name
                element["_selected_target"] = target
            
            # Blockを生成
            block = RuleBlock(element)
            self._block_list.addItem(block)

        self._refresh_list_widgets()

    def _on_block_dropped(self, kind, row):
        default_elements = {
            "DATE": {"kind": "DATE", "format": "YYYY-MM-DD"},
            "NAME": {"kind": "NAME", "remove_internal_delimiter": True},
            "VERSION": {"kind": "VERSION", "prefix": "ver_", "format": "n.n.nnn"}
        }

        if kind in default_elements:
            element = default_elements[kind].copy()
        else:
            group = self._categories.get(kind, {})
            categories = [c for c in group.keys() if c != "REQ"]
            
            # デフォルトで一番上のカテゴリを選択状態にする
            default_target = categories[0] if categories else ""
            
            element = {
                "kind": kind + texts.kind_separator + default_target,
                "_group": kind,
                "_selected_target": default_target
            }
            
            requirement_str = group.get("REQ", "_")
            element["requirement"] = [] if requirement_str == "_" else [r.strip() for r in str(requirement_str).split(",") if r.strip()]
            
            target_elements = group.get(default_target, "")
            element["target"] = target_elements if isinstance(target_elements, list) else [t.strip() for t in str(target_elements).split(",") if t.strip()]

        block = RuleBlock(element)
        block.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._block_list.insertItem(row, block)
        self._block_list.setCurrentItem(block)
        
        self._refresh_list_widgets()
        self._call_make_sample()

    def _on_block_selected(self):
        """現在のルールリストでブロックが選択された際、詳細設定フォームを切り替える"""
        while self.detail_form_layout.count():
            widget_item = self.detail_form_layout.takeAt(0)
            if widget_item.widget(): 
                widget_item.widget().deleteLater()

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
            
        elif block.kind in self._categories:
            group_name = block.kind
            group = self._categories.get(group_name, {})
            
            categories = [c for c in group.keys() if c != "REQ"]
            
            self.cat_combo = QComboBox()
            for category in categories:
                self.cat_combo.addItem(category, category)
                
            current_target = element.get("_selected_target", "")
            
            if not current_target and categories:
                current_target = categories[0]
                self._on_target_changed(element, group, current_target)
                
            idx = self.cat_combo.findData(current_target)
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
            elif categories:
                self.cat_combo.setCurrentIndex(0)
                
            self.cat_combo.currentIndexChanged.connect(lambda idx: self._on_target_changed(element, group, self.cat_combo.itemData(idx)))
            self.detail_form_layout.addRow("抽出ターゲットのカテゴリ:", self.cat_combo)
            
            requirement_str = group.get("REQ", "_")
            if requirement_str != "_":
                display_req = f"文字列 {requirement_str} が存在する場合のみ"
            else: 
                display_req = "なし (常に適用)"

            req_label = QLabel(f"適用要件: {display_req}")
            self.detail_form_layout.addRow(req_label)

    def _on_target_changed(self, element, group, target):
        """詳細画面でターゲットが変更された時に、一時領域の選択状態を更新してサンプルを再描画する"""
        element["_selected_target"] = target
        element["kind"] = element.get('_group', '') + texts.kind_separator + target
        
        requirement_str = group.get("REQ", "_")
        if requirement_str == "_":
            element["requirement"] = []
        else:
            element["requirement"] = [r.strip() for r in str(requirement_str).split(",") if r.strip()]

        target_elements = group.get(target, "")
        if isinstance(target_elements, list):
            element["target"] = target_elements
        else:
            element["target"] = [i.strip() for i in str(target_elements).split(",") if i.strip()]
            
        self._call_make_sample()

    def _on_category_btn_clicked(self):
        # 現在の情報を保存
        self._rules_tmp_blocks = self._get_current_rules()
        selected_row = self._block_list.currentRow()

        # 戻ってきたときに同期、復元
        if self.categories_dialog.exec() == QDialog.Accepted:
            self._categories, _ = fileLoadingUtils.load_categories(self)
            self._sync_tmp_rules()
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
            self._sync_tmp_rules()
            self._call_make_sample()

            if selected_row >= 0 and selected_row < self._block_list.count():
                self._block_list.setCurrentRow(selected_row)

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
            
            if "_group" in element:
                group_name = element["_group"]
                target = element.get("_selected_target", "")
                
                # ユニークなkind名にするため、group_nameとtargetを結合する
                packed_elem = {
                    "kind": group_name + texts.kind_separator + target,
                    "requirement": element.get("requirement", []),
                    "target": element.get("target", [])
                }
                rules_blocks.append(packed_elem)
            else:
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
