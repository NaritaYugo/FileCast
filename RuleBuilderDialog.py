import yaml

from PySide6.QtWidgets import (QAbstractItemView, QCheckBox,  QComboBox, QDialog, QDialogButtonBox, 
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListView, 
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,QWidget)
from PySide6.QtCore import Qt, QSize, Signal

import EditCategoriesDialog
import EditSettingsDialog
import fileLoadingUtils
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
            
        self.rule_yaml_path = base_dir / "rule.yaml"
        self.settings_yaml_path = base_dir / "settings.yaml"
        self.categories_yaml_path = base_dir / "categories.yaml"

        # categories.yaml の生データをそのまま保持する辞書
        self.categories = {}

        self._setup_ui()
        
        self.settings_dialog = EditSettingsDialog.EditSettingsDialog(self)
        self.settings_dialog.settings_updated.connect(self._call_make_sample)

        self.categories_dialog = EditCategoriesDialog.EditCategoriesDialog(self)
        self.categories_dialog.categories_updated.connect(self._on_categories_file_updated)

        self.categories = fileLoadingUtils.load_categories(self)
        self._spread_rule()

        self._setup_palette()
        self._call_make_sample()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        split_layout = QHBoxLayout()
        left_layout = QVBoxLayout()

        # 左上：サンプルを表示
        sample_group = QGroupBox("サンプル")
        sample_layout = QVBoxLayout()
        self.sample = QLabel()
        self.sample.setStyleSheet("padding: 3px; font-size: 15px; font-weight: bold;")
        self.sample.setWordWrap(True)
        self.sample.setAlignment(Qt.AlignCenter)
        self.sample.setTextFormat(Qt.RichText)
        sample_layout.addWidget(self.sample)
        sample_group.setLayout(sample_layout)
        left_layout.addWidget(sample_group)

        # 左中：現在のルール
        rule_group = QGroupBox("ブロック追加・並び替え")
        rule_layout = QVBoxLayout()

        rule_layout.addWidget(QLabel("現在のルール順序（ドラッグで並び替え / ×で削除）:"))
        self.block_list = SortableListWidget()
        self.block_list.setFlow(QListView.LeftToRight)
        self.block_list.setWrapping(False)
        self.block_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.block_list.setFixedHeight(55)
        self.block_list.setStyleSheet("""
            QListWidget { background-color: #2b2b2b; outline: none; padding : 5px; border-radius: 4px;}
            QListWidget::item { background-color:#555; color:white; margin:2px; min-width:100px; border-radius: 3px;}
            QListWidget::item:selected { background-color: #007ACC;}
        """)
        self.block_list.itemSelectionChanged.connect(self._on_block_selected)
        
        self.block_list.order_changed.connect(self._refresh_list_widgets)
        self.block_list.order_changed.connect(self._call_make_sample)
        self.block_list.palette_dropped.connect(self._on_block_dropped)
        rule_layout.addWidget(self.block_list)

        # 左下：素材パレット
        rule_layout.addWidget(QLabel("利用可能なブロック（上にドラッグ＆ドロップして追加）:"))
        self.palette_list = QListWidget()
        self.palette_list.setFlow(QListView.LeftToRight)

        self.palette_list.setWrapping(True)
        self.palette_list.setGridSize(QSize(110, 40)) 
        self.palette_list.setSpacing(4)

        self.palette_list.setDragEnabled(True)
        self.palette_list.setAcceptDrops(False)
        self.palette_list.setStyleSheet("""
            QListWidget { background-color: #222; padding: 3px; border-radius: 4px; }
            QListWidget::item { background-color: #007ACC; color: white; margin: 2px; padding: 4px 10px; border-radius: 3px;}
        """)
        rule_layout.addWidget(self.palette_list)

        rule_group.setLayout(rule_layout)
        left_layout.addWidget(rule_group)

        # 右：詳細設定
        right_group = QGroupBox("詳細設定")
        right_layout = QVBoxLayout()

        self.empty_label = QLabel('ブロックを選択してください')
        self.empty_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.empty_label)

        self.detail_container = QWidget()
        self.detail_form_layout = QFormLayout(self.detail_container)
        self.detail_container.hide()
        right_layout.addWidget(self.detail_container)
        right_layout.addStretch()

        right_group.setLayout(right_layout)
        
        split_layout.addLayout(left_layout, 3)
        split_layout.addWidget(right_group, 2)
        main_layout.addLayout(split_layout)

        # 下：ボタン類
        bottom_layout = QHBoxLayout()
        
        self.settings_btn = QPushButton("全体設定")
        self.settings_btn.clicked.connect(lambda: self.settings_dialog.exec())
        bottom_layout.addWidget(self.settings_btn)

        self.category_editor_btn = QPushButton("カテゴリの編集")
        self.category_editor_btn.clicked.connect(lambda: self.categories_dialog.exec())
        bottom_layout.addWidget(self.category_editor_btn)
        
        bottom_layout.addStretch()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("保存")
        button_box.button(QDialogButtonBox.Cancel).setText("キャンセル")
        button_box.accepted.connect(self._save_rule)
        button_box.rejected.connect(self.reject)
        bottom_layout.addWidget(button_box)
        
        main_layout.addLayout(bottom_layout)

    def _setup_palette(self):
        """素材パレットの表示を更新 (グループ名のみを表示)"""
        self.palette_list.clear()
        
        kinds = ["VERSION", "DATE", "NAME"]
        kinds.extend(sorted(self.categories.keys()))
            
        for kind in kinds:
            block = PaletteBlock(kind)
            block.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            block.setSizeHint(QSize(100, 32))
            if kind in ("DATE", "NAME", "VERSION"):
                block.setBackground(Qt.GlobalColor.darkBlue)
            else:
                block.setBackground(Qt.GlobalColor.darkGreen)
            self.palette_list.addItem(block)

    def _spread_rule(self):
        """rule.yamlから現在の配置ルールをロードして画面に並べる"""
        self.block_list.clear()

        self.rule = fileLoadingUtils.load_rule(self)
        for element in self.rule:
            kind = element.get("kind", "")
            
            # ユーザー定義カテゴリの場合、UI用の補助プロパティを復元する
            if texts.kind_separator in kind:
                group_name, target = kind.split(texts.kind_separator, 1)
                element["_group"] = group_name
                element["_selected_target"] = target
            
            # Blockを生成
            block = RuleBlock(element)
            self.block_list.addItem(block)

        self._refresh_list_widgets()
    
    def _write_default_texts(self, file_target: str):
        try:
            with open(getattr(self, f"{file_target}_yaml_path"), "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS[file_target], f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            print(f"Failed to write default {file_target}: {e}")
    
    def _on_categories_file_updated(self):
        self.categories = fileLoadingUtils.load_categories(self)
        self._spread_rule
        self._setup_palette()
        self._call_make_sample()

    def _on_block_dropped(self, kind, row):
        default_elements = {
            "DATE": {"kind": "DATE", "format": "YYYY-MM-DD"},
            "NAME": {"kind": "NAME", "remove_internal_delimiter": True},
            "VERSION": {"kind": "VERSION", "prefix": "ver_", "format": "n.n.nnn"}
        }

        if kind in default_elements:
            element = default_elements[kind].copy()
        else:
            group = self.categories.get(kind, {})
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
        self.block_list.insertItem(row, block)
        self.block_list.setCurrentItem(block)
        
        self._refresh_list_widgets()
        self._call_make_sample()

    def _on_block_selected(self):
        """現在のルールリストでブロックが選択された際、詳細設定フォームを切り替える"""
        while self.detail_form_layout.count():
            widget_item = self.detail_form_layout.takeAt(0)
            if widget_item.widget(): 
                widget_item.widget().deleteLater()

        selected_blocks = self.block_list.selectedItems()
        if not selected_blocks:
            self.empty_label.show()
            self.detail_container.hide()
            return
        
        self._call_make_sample()

        self.empty_label.hide()
        self.detail_container.show()
        
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
            
        elif block.kind in self.categories:
            group_name = block.kind
            group = self.categories.get(group_name, {})
            
            categories = [c for c in group.keys() if c != "REQ"]
            
            self.cat_combo = QComboBox()
            for category in categories:
                self.cat_combo.addItem(category, category)
                
            current_target = element.get("_selected_target", "")
            
            if not current_target and categories:
                current_target = categories[0]
                self.on_target_changed(element, group, current_target)
                
            idx = self.cat_combo.findData(current_target)
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
            elif categories:
                self.cat_combo.setCurrentIndex(0)
                
            self.cat_combo.currentIndexChanged.connect(lambda idx: self.on_target_changed(element, group, self.cat_combo.itemData(idx)))
            self.detail_form_layout.addRow("抽出ターゲットのカテゴリ:", self.cat_combo)
            
            requirement_str = group.get("REQ", "_")
            if requirement_str != "_":
                display_req = f"文字列 {requirement_str} が存在する場合のみ"
            else: 
                display_req = "なし (常に適用)"

            req_label = QLabel(f"適用要件: {display_req}")
            self.detail_form_layout.addRow(req_label)

    def on_target_changed(self, element, group, target):
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

    def _call_make_sample(self):
        settings = {"original_date_format": "YMD", "delimiter": "_", "sequence": {"style": "all_overlaps", "format": "(n)"}}
        if self.settings_yaml_path.exists():
            try:
                with open(self.settings_yaml_path, "r", encoding="utf-8") as f:
                    settings_data = yaml.safe_load(f)
                    if isinstance(settings_data, dict):
                        settings.update(settings_data)
            except Exception as e:
                print(f"Preview load settings error: {e}")

        rule_blocks = self._get_current_rule()
        selected_index = self.block_list.currentRow()
        
        try:
            sample_text = validations.make_sample(rule_blocks, settings, selected_index)
            self.sample.setText(sample_text)
        except Exception as e:
            print(f"Preview error: {e}")
            self.sample.setText("<span style='color:gray;'>サンプルプレビュー (validations 未接続)</span>")

    def _refresh_list_widgets(self):
        for i in range(self.block_list.count()):
            block = self.block_list.item(i)
            display_text = getattr(block, "display_text", block.kind)
            
            widget = DragableBlockWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(8, 4, 4, 2) 
            layout.setSpacing(6)
            
            label = QLabel(display_text)
            label.setStyleSheet("color: white; font-weight: bold; background: transparent;")
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(label)
            
            close_btn = QPushButton("×")
            close_btn.setFixedSize(14, 14)
            close_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d9534f; color: white;
                    border-radius: 7px; font-size: 9px; font-weight: bold; border: none;
                    line-height: 14px;
                }
                QPushButton:hover { background-color: #c9302c; }
            """)
            close_btn.clicked.connect(lambda _, b=block: self._delete_block(b))
            layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)
            
            widget.setStyleSheet("background: transparent;")
            block.setSizeHint(widget.sizeHint())

            size = widget.sizeHint()
            # リストアイテム枠の余白分として、横幅を少しだけ拡張する
            block.setSizeHint(QSize(size.width() + 6, size.height()))

            self.block_list.setItemWidget(block, widget)

    def _delete_block(self, block):
        row = self.block_list.row(block)
        if row >= 0:
            self.block_list.takeItem(row)
            self._on_block_selected()
            self._refresh_list_widgets() 
            self._call_make_sample()

    def _get_current_rule(self):
        """画面上のブロック群をルールとしてパッキング"""
        rule_blocks = []
        for i in range(self.block_list.count()):
            element = self.block_list.item(i).element
            
            if "_group" in element:
                group_name = element["_group"]
                target = element.get("_selected_target", "")
                
                # ユニークなkind名にするため、group_nameとtargetを結合する
                packed_elem = {
                    "kind": group_name + texts.kind_separator + target,
                    "requirement": element.get("requirement", []),
                    "target": element.get("target", [])
                }
                rule_blocks.append(packed_elem)
            else:
                rule_blocks.append(element)
        return rule_blocks

    def _save_rule(self):
        rule_blocks = self._get_current_rule()
        
        try:
            validations.check_rule(rule_blocks, self.categories)
        except Exception as e:
            QMessageBox.warning(self, "命名規則エラー", str(e))
            return

        try:
            with open(self.rule_yaml_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(rule_blocks, f, default_flow_style=False, allow_unicode=True)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"保存に失敗しました:\n{e}")
