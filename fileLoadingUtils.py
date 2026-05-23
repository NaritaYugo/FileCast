from pathlib import Path
from PySide6.QtWidgets import QMessageBox
import sys
import yaml

import validations
import texts

def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def load_categories(parent) -> dict:
    categories_path = get_base_dir() / "categories.yaml"

    # ファイルが無ければ黙って新規作成
    if not categories_path:
        with open(categories_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(texts.DEFAULT_YAMLS["categories"], f, default_flow_style=False, allow_unicode=True)
        return texts.DEFAULT_YAMLS["categories"]
    
    try:
        with open(categories_path, "r", encoding="utf-8") as f:
            categories = yaml.safe_load(f)
        validations.check_categories(categories)
        return categories
    
    # ファイルがあるが読み込めない場合・内容が正しくない場合は確認してから初期化
    except Exception as e:
        reply = QMessageBox.question(
            parent, "読み込みエラー", 
            f"命名規則構成ファイル(categories.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with open(categories_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["categories"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["categories"]
        
    return None

def load_settings(parent) -> dict:
    settings_path = get_base_dir() / "settings.yaml"

    if not settings_path:
        with open(settings_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(texts.DEFAULT_YAMLS["settings"], f, default_flow_style=False, allow_unicode=True)
        return texts.DEFAULT_YAMLS["settings"]

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        validations.check_settings(settings)
        return settings
    
    except Exception as e:
        reply = QMessageBox.question(
            parent, "読み込みエラー", 
            f"命名規則構成ファイル(settings.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with open(settings_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["settings"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["settings"]
    return None

def load_rules(parent) -> dict:
    """rules のバリデーションに categories を使うので、load_categoriesを先に呼んでおく"""

    categories_path = get_base_dir() / "categories.yaml"
    rules_path = get_base_dir() / "rules.yaml"

    if not rules_path or not categories_path:
        if not rules_path:
            with open(rules_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["rules"], f, default_flow_style=False, allow_unicode=True)

        if not categories_path:
            with open(categories_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["categories"], f, default_flow_style=False, allow_unicode=True)

        return texts.DEFAULT_YAMLS["rules"]

    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            rules = yaml.safe_load(f)
        with open(categories_path, "r", encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        validations.check_rules(rules, categories)
        return rules
    
    except Exception as e:
        reply = QMessageBox.question(
            parent, "読み込みエラー", 
            f"命名規則構成ファイル(settings.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with open(rules_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["rules"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["rules"]
        
    return None

def load_caches(parent) -> dict:
    caches_path = get_base_dir() / "caches.yaml"

    if not caches_path:
        with open(caches_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(texts.DEFAULT_YAMLS["caches"], f, default_flow_style=False, allow_unicode=True)
        return texts.DEFAULT_YAMLS["caches"]

    try:
        with open(caches_path, "r", encoding="utf-8") as f:
            caches = yaml.safe_load(f)
        validations.check_caches(caches)
        return caches
    
    except Exception as e:
        reply = QMessageBox.question(
            parent, "読み込みエラー", 
            f"命名規則構成ファイル(caches.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with open(caches_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["caches"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["caches"]
        
    return None