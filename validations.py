import datetime
import re

import texts


def check_categories(categories: dict) -> bool:
    if categories == None:
        return True
    if not isinstance(categories, dict):
        raise TypeError

    for group_name, group_dict in categories.items():
        if not any(key != "REQ" for key in group_dict):
            raise KeyError(f"グループ「{group_name}」内にカテゴリがありません")
    return True

# ルール内にあるカテゴリがユーザー定義のカテゴリにあるか確認するため、categoryも渡す
def check_rule(rule: list, categories: dict) -> bool:
    for element in rule:
        if element.get("kind") == "NAME":
            if not isinstance(element.get("remove_internal_delimiter"), bool):
                raise KeyError("NAME")
            
        elif element.get("kind") == "DATE":
            num_Y = element.get("format").count("Y")
            num_M = element.get("format").count("M")
            num_D = element.get("format").count("D")
            if num_Y not in (2, 4) or not any(x == 2 for x in (num_M, num_D)):
                raise KeyError("DATE: 文字「Y」「M」「D」の個数が正しくありません")
            
        elif element.get("kind") == "VERSION":
            if element.get("format").replace("n", "").replace(".", ""):
                raise KeyError("VERSION: バージョン形式に使える文字は「n」「.」のみです")
            
        else:
            group, category = element.get("kind").split(texts.kind_separator)

            if category not in categories.get(group):
                raise KeyError(f"キー「{element.get("kind")}」がカテゴリに存在しません")

    return True

def check_settings(settings: dict) -> bool:
    if not isinstance(settings, dict):
        raise TypeError
    
    if settings.get("original_date_format") not in ["DMY", "YMD", "MDY"]:
        raise KeyError("original_date_format")
    
    if "delimiter" not in settings:
        raise KeyError("delimiter")
    
    sequence = settings.get("sequence", {})
    if sequence.get("style") not in ["all_overlaps", "always", "false"] or "format" not in sequence:
        raise KeyError("sequence")
    
    return True

def check_cache(cache: dict) -> bool:
    if "target_dir" not in cache:
        raise KeyError()
    
    if "filename" not in cache:
        raise KeyError()
    
    return True

def make_sample(rule: list, settings: dict, selectedIndex: int) -> str:
    """ルールから形式のサンプルを作成；ルールが完成してなくても何か表示する"""
    current_year  = str(datetime.datetime.now().year)
    current_month = str(datetime.datetime.now().month).zfill(2)
    current_day   = str(datetime.datetime.now().day).zfill(2)

    elements = []
    for element in rule:
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

def verify_comply_rule(filename: str, rule: list, settings: dict, categories: dict) -> bool:
    pattern_list = []
    for element in rule:
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

            cat_pattern = categories.get(group).get(category).replace(" ", "").replace(",", "|")
            pattern_list.append(f"({cat_pattern})")
    
    suffix_pattern = r"\.\w+"
    pattern = settings.get("delimiter").join(pattern_list) + suffix_pattern

    return bool(re.fullmatch(pattern, filename))