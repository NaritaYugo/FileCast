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

def load_categories(parent, display_alert=True) -> dict:
    categories_path = get_base_dir() / "categories.yaml"
    try:
        with open(categories_path, "r", encoding="utf-8") as f:
            categories = yaml.safe_load(f)
        validations.check_categories(categories)
        return categories
    
    except Exception as e:
        if display_alert:
            reply = QMessageBox.question(
                parent, "読み込みエラー", 
                f"命名規則構成ファイル(categories.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        if not display_alert or reply == QMessageBox.StandardButton.Yes:
            with open(categories_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["categories"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["categories"]
        
    return None

def load_settings(parent, display_alert=True) -> dict:
    settings_path = get_base_dir() / "settings.yaml"
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)
        validations.check_settings(settings)
        return settings
    
    except Exception as e:
        if display_alert:
            reply = QMessageBox.question(
                parent, "読み込みエラー", 
                f"命名規則構成ファイル(settings.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        if not display_alert or reply == QMessageBox.StandardButton.Yes:
            with open(settings_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["settings"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["settings"]
    return None

def load_rule(parent, display_alert=True) -> dict:
    """rule のバリデーションに categories を使うので、load_categoriesを先に呼んでおく"""
    rule_path = get_base_dir() / "rule.yaml"
    categories_path = get_base_dir() / "categories.yaml"
    try:
        with open(rule_path, "r", encoding="utf-8") as f:
            rule = yaml.safe_load(f)
        with open(categories_path, "r", encoding="utf-8") as f:
            categories = yaml.safe_load(f)

        validations.check_rule(rule, categories)
        return rule
    
    except Exception as e:
        if display_alert:
            reply = QMessageBox.question(
                parent, "読み込みエラー", 
                f"命名規則構成ファイル(settings.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        if not display_alert or reply == QMessageBox.StandardButton.Yes:
            with open(rule_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["rule"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["rule"]
    return None

def load_cache(parent, display_alert=True) -> dict:
    cache_path = get_base_dir() / "cache.yaml"
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = yaml.safe_load(f)
        validations.check_cache(cache)
        return cache
    
    except Exception as e:
        if display_alert:
            reply = QMessageBox.question(
                parent, "読み込みエラー", 
                f"命名規則構成ファイル(cache.yaml)が破損しています。\nエラー内容: {e}\n初期設定に戻しますか？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

        if not display_alert or reply == QMessageBox.StandardButton.Yes:
            with open(cache_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(texts.DEFAULT_YAMLS["cache"], f, default_flow_style=False, allow_unicode=True)
            return texts.DEFAULT_YAMLS["cache"]
    return None