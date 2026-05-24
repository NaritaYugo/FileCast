import datetime
import re
import yaml

import fileLoadingUtils


FORBIDDEN_CHARS = r'[\\/:*?"<>|]'

def check_categories(categories: dict) -> bool:
    if categories is None:
        return True
    if not isinstance(categories, dict):
        raise TypeError("辞書形式ではありません")

    for category, items in categories.items():
        if not isinstance(items, dict):
            raise TypeError(f"カテゴリ「{category}」が辞書形式ではありません")
        
        if not any(key != "REQ" for key in category):
            raise KeyError(f"カテゴリ「{category}」内にカテゴリがありません")
        
        for item, patterns in items.items():
            if not isinstance(patterns, list):
                raise TypeError(f"カテゴリ「{category}」内のアイテム「{item}」がリスト形式ではありません")
                
            if re.search(FORBIDDEN_CHARS, "".join(item)):
                raise ValueError(f"カテゴリ「{category}」内のアイテム「{item}」にファイル名として使用できない文字が含まれています")
    return True


def to_flowStyleList(categories: dict) -> dict:
    if categories is None:
        return True
    
    if not isinstance(categories, dict):
        raise TypeError(f"辞書形式ではありません。")

    for i, (category, items) in enumerate(categories.items()):
        if not isinstance(items, dict):
            raise TypeError(f"カテゴリ「{category}」が辞書形式ではありません。")
        
        # 改行位置を調節して書き込むため、listを継承したFlowStyleList型にする
        for item, patterns in items.items():
            if isinstance(patterns, list):
                categories[category][item] = fileLoadingUtils.FlowStyleList(patterns)
            else:
                raise TypeError(f"カテゴリ「{category}」内のアイテム「{item}」の形式が正しくありません")

    return categories

def read_as_yaml_relaxed(categories_text: str) -> dict:
    """ユーザーの入力に少々ミスがあっても修正し、yamlとして読み込んで返す"""

    """categoriesの形式メモ
    category:
        item: [pattern, pattern]
        item: [pattern, pattern, pattern]
    category:
        item: [pattern]
    """
    lines = categories_text.split("\n")
    cleand_lines = []

    for i, line in enumerate(lines):
        # 全角を半角に変更
        line = line.replace("：", ":").replace("，",",").replace("、",",").replace("　"," ").replace("！", "!")

        line = line.replace("!", "_EXCLAMATION")
        line = line.replace("*", "_ASTERISK")

        if re.search(FORBIDDEN_CHARS, "".join(line).replace(":", "")):
            raise ValueError(f"{i}行目: ファイル名として使用できない文字が含まれています")

        # item:: patternsの場合、item: item, patterns にする
        if line.startswith(" ") and "::" in line:
            line = re.sub(r"(\w+)::", r"\1: \1, ", line)
    
        # item または item: または item:: だけの場合、item: item にする
        if line.startswith(" ") and (":" not in line or line.replace(" ", "").endswith(":")):
            line = re.sub(r"(\w+):{1,2}", r"\1: \1", line)

        # スペースを入れ忘れている場合のためにコロンの後のスペースの数を増やしておく
        line = line.replace(":", ": ")
        
        # patterns が[]で囲われてない場合は囲う
        if line.startswith(" "):
            line = re.sub(r"(?<=:) +(?P<patterns>[^\[\]]+)", r" [\g<patterns>]", line)
        
        cleand_lines.append(line)

    cleand_categories_text = "\n".join(cleand_lines)

    try:
        categories = yaml.safe_load(cleand_categories_text)
    except Exception as e:
        raise Exception(f"yamlとしてパースできません: {e}")

    return to_flowStyleList(categories)


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
            category = element.get("kind")

            if category not in categories:
                raise KeyError(f"カテゴリ「{category}」はカテゴリ設定ファイル内に存在しません")
            
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
            items = element.get("items", "")
            elements.append(next(iter(items)))

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
            pattern_list.append(r".*")
            
        elif element.get("kind") == "DATE":
            date_pattern = element.get("format")\
                .replace("YYYY", r"\d{4}").replace("YY", r"\d{2}")\
                .replace("MM", r"\d{2}").replace("DD", r"\d{2}")
            pattern_list.append(date_pattern)

        elif element.get("kind") == "VERSION":
            ver_pattern = element.get("format").replace("n", r"\d")
            pattern_list.append(element.get("prefix") + ver_pattern)
            
        else:
            if "_EXCLAMATION" in element.get("requirement"):
                pattern_list.append(r".*")
            else:
                items = list(element.get("items").keys())
                cat_pattern = "|".join(items)
                pattern_list.append(f"({cat_pattern})")
        
    suffix_pattern = r"\.\w+"
    re_delimiter = settings.get("delimiter")+"?"
    pattern = re_delimiter.join(pattern_list) + suffix_pattern


    return bool(re.fullmatch(pattern, filename))
