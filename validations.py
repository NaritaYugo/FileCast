import datetime
import re

import fileLoadingUtils
import texts


FORBIDDEN_CHARS = r'[\\/:*?"<>|]'

def check_categories(categories: dict) -> bool:
    if categories is None:
        return True
    if not isinstance(categories, dict):
        raise TypeError

    for group_name, group_dict in categories.items():
        if not isinstance(group_dict, dict):
            raise KeyError(f"グループ「{group_name}」が辞書形式ではありません")
        if not any(key != "REQ" for key in group_dict):
            raise KeyError(f"グループ「{group_name}」内にカテゴリがありません")
        for cat_name, cat_list in group_dict.items():
            if not isinstance(cat_list, list):
                raise KeyError(f"カテゴリ「{group_name}-{cat_name}」がリスト形式ではありません")
            if re.search(FORBIDDEN_CHARS, "".join(cat_list)):
                raise ValueError(f"カテゴリ「{group_name}-{cat_name}」にファイル名として使用できない文字が含まれています")
    return True


def convert_to_valid_categories(categories: dict) -> dict:
    """ユーザーの入力に少々ミスがあっても修正し、yamlに書き込む形式に直す"""
    if categories is None:
        return True
    
    if not isinstance(categories, dict):
        raise TypeError(f"辞書形式ではありません。")

    for i, (group_name, group_dict) in enumerate(categories.items()):
        if isinstance(group_dict, dict):
            pass

        # コロンはあって、スペースが抜けているだけの場合は修正する
        elif isinstance(group_dict, str) and group_dict.count(":") == 1:
            categories_list = list(categories)
            categories_list[i] = (group_dict.split())
            categories = dict(categories_list)
        
        else:
            raise TypeError(f"グループ「{group_name}」が辞書形式ではありません。")

    # 更新されたcategoriesを再度回して、中の確認
    for group_name, group_dict in categories.items():
        if not any(key != "REQ" for key in group_dict):
            raise KeyError(f"グループ「{group_name}」内にカテゴリがありません")
        
        # 改行位置を調節して書き込むため、listを継承したFlowStyleList型にする
        for cat_name, cat_list in group_dict.items():
            if isinstance(cat_list, list):
                categories[group_name][cat_name] = fileLoadingUtils.FlowStyleList(cat_list)
                if re.search(FORBIDDEN_CHARS, "".join(cat_list)):
                    raise ValueError(f"カテゴリ「{group_name}-{cat_name}」にファイル名として使用できない文字が含まれています")
                
            elif isinstance(cat_list, str):
                categories[group_name][cat_name] = fileLoadingUtils.FlowStyleList(
                    cat_list.replace(" ","").split(","))
                if re.search(FORBIDDEN_CHARS, cat_list):
                    raise ValueError(f"カテゴリ「{group_name}-{cat_name}」にファイル名として使用できない文字が含まれています")
            else:
                raise TypeError(f"{group_name}-{cat_name}: カンマ区切り文字列またはリストとして記述してください")

    return categories


def check_rules(rules: list, categories: dict) -> bool:
    # ルール内にあるカテゴリがユーザー定義のカテゴリにあるか確認するため、categoryも渡す
    for element in rules:
        if element.get("kind") == "NAME":
            if not isinstance(element.get("remove_internal_delimiter"), bool):
                raise KeyError("NAME")
            
        elif element.get("kind") == "DATE":
            num_Y = element.get("format").count("Y")
            num_M = element.get("format").count("M")
            num_D = element.get("format").count("D")
            if num_Y not in (2, 4) or num_M != 2 or num_D != 2:
                raise KeyError("DATE: 文字「Y」「M」「D」の個数が正しくありません")
            
            elif re.search(FORBIDDEN_CHARS, element.get("format")):
                    raise ValueError(f"DATE: 形式にファイル名として使用できない文字が含まれています")
            
        elif element.get("kind") == "VERSION":
            if re.search(FORBIDDEN_CHARS, element.get("format")):
                raise ValueError("VERSION: バージョン形式にファイル名として使用できない文字が含まれています")
            elif "n" not in element.get("format"):
                raise ValueError("VERSION: バージョン形式には「n」を1字以上含めてください")
            
            elif re.search(FORBIDDEN_CHARS, element.get("prefix")):
                raise ValueError("VERSION: prefixにファイル名として使用できない文字が含まれています")
            
        else:
            group, category = element.get("kind").split(texts.kind_separator)

            if category not in categories.get(group):
                raise KeyError(f"キー「{category}」がカテゴリに存在しません")
            
            if "_" in element.get("requirement"):
                raise KeyError("内部エラー: '_' がそのまま保存されています")
            
    return True


def check_settings(settings: dict) -> bool:
    if not isinstance(settings, dict):
        raise TypeError
    
    if settings.get("original_date_format") not in ["DMY", "YMD", "MDY"]:
        raise KeyError("original_date_format")
    
    if "delimiter" not in settings:
        raise KeyError("delimiter")
    
    if re.search(FORBIDDEN_CHARS, settings.get("delimiter")):
        raise ValueError("文字区切りにファイル名として使用できない文字が含まれています")
    
    sequence = settings.get("sequence", {})
    if sequence.get("style") not in ["all_overlaps", "always", "false"] or "format" not in sequence:
        raise KeyError("sequence")
    
    return True


def check_caches(caches: dict) -> bool:
    if "target_dir" not in caches:
        raise KeyError()
    
    if "filename" not in caches:
        raise KeyError()
    
    return True


def make_sample(rules: list, settings: dict, selectedIndex: int) -> str:
    """ルールから形式のサンプルを作成；ルールが完成してなくても何か表示する"""
    current_year  = str(datetime.datetime.now().year)
    current_month = str(datetime.datetime.now().month).zfill(2)
    current_day   = str(datetime.datetime.now().day).zfill(2)

    elements = []
    for element in rules:
        kind = element.get("kind")

        if kind == "DATE":
            date_format = element.get("format", "")
            if date_format:
                # YYYY を置換してから YY を置換する
                date = date_format\
                    .replace("YYYY", current_year).replace("YY", current_year[2:])\
                    .replace("MM", current_month).replace("DD", current_day)
            else:
                date = "日付[形式未設定]"
            elements.append(date)

        elif kind == "NAME":
            if element.get("remove_internal_delimiter"):
                name = "ExampleName"
            else:
                name = "Example" + settings.get("delimiter", "_") + "Name"
            elements.append(name)
                
        elif kind == "VERSION":
            ver_format = element.get("format", "")
            if ver_format:
                # n -> 1, nn -> 01, nnn -> 001 のように置換
                ver_num = re.sub(r"n+", lambda m: "0" * (len(m.group()) - 1) + "1", ver_format)
            else:
                ver_num = "バージョン[形式未設定]"
            elements.append(element.get("prefix", "") + ver_num)
            
        else:
            if texts.kind_separator in kind:
                category = kind.split(texts.kind_separator)[1]
            else:
                category = kind
            elements.append(category)

    if selectedIndex >= 0:
        # 現在選択されているブロックに対応するテキストの色を変える
        blue = "#007ACC"
        elements[selectedIndex] = f"<span style='color: {blue}; '><b>" + elements[selectedIndex] + "</b></span>"

    sample_text = settings.get("delimiter", "_").join(elements)

    seq_style = settings.get("sequence", {}).get("style")
    seq_format = settings.get("sequence", {}).get("format", "")
    
    if seq_style == "always":
        match = re.search(r"n+", seq_format)
        if match:
            digit = len(match.group())
            sample_text += seq_format.replace("n"*digit, "1".zfill(digit))
        
    return sample_text + ".xxx"


def verify_comply_rules(filename: str, rules: list, settings: dict, categories: dict) -> bool:
    pattern_list = []
    for element in rules:
        if element.get("kind") == "NAME":
            pattern_list.append(r".+")
            
        elif element.get("kind") == "DATE":
            date_pattern = element.get("format")\
                .replace("YYYY", r"\d{4}").replace("YY", r"\d{2}")\
                .replace("MM", r"\d{2}").replace("DD", r"\d{2}")
            pattern_list.append(date_pattern)

        elif element.get("kind") == "VERSION":
            ver_pattern = element.get("format").replace("n", r"\d")
            pattern_list.append(ver_pattern)
            
        else:
            group, category = element.get("kind").split(texts.kind_separator)

            target_cat = categories.get(group).get(category)
            cat_pattern = "|".join(target_cat)
            pattern_list.append(f"({cat_pattern})")
    
    suffix_pattern = r"\.\w+"
    pattern = settings.get("delimiter").join(pattern_list) + suffix_pattern

    return bool(re.fullmatch(pattern, filename))
