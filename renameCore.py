from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Dict

from rapidfuzz.distance import Levenshtein

import texts


RE_DELIM = r"[_\.\-\s]"

@dataclass
class RenameContext:
    rules: list
    settings: dict
    org_file: str
    remains: str
    extracts: list
    has_error: bool = False
    has_warn: bool = False


def _build_word_search_pattern(word: str) -> str:
    """パターンの左右に区切り(デリミタや、文字種の境目)をいれたパターンを生成"""
    word_pattern = rf"(?i:{word})" # word 部分だけ ignorecase

    re_boundary = "|".join([
        rf"(?<={RE_DELIM})",            # デリミタ

        r"(?<=[a-z])(?=[A-Z])",         # camelCase
        r"(?<=[A-Z])(?=[A-Z][a-z])",    # PascalCase

        r"(?<=[^0-9])(?=[0-9])",        # 数字以外から数字
        r"(?<=[0-9])(?=[^0-9])",        # 数字から数字以外

        r"(?<=[^a-zA-Z])(?=[a-zA-Z])",  # 英字以外から英字
        r"(?<=[a-zA-Z])(?=[^a-zA-Z])",  # 英字から英字以外
    ])

    re_left = rf"(?:^|{re_boundary})"
    re_right = rf"(?:$|{re_boundary})"

    return f"{re_left}{word_pattern}{re_right}"

def _extract_dates(ctx: RenameContext):
    date_pos = []
    for i, element in enumerate(ctx.rules):
        if element["kind"] == "DATE":
            date_pos.append(i)
    
    year_pattern  = r"(?P<year>(20|19)?([0-9][0-9]))"
    month_pattern = r"(?P<month>0[1-9]|1[0-2])"
    day_pattern   = r"(?P<day>0[1-9]|[1-2][0-9]|3[0-1])"

    # "YMD", "DMY", "MDY"のいずれか
    original_date_format = ctx.settings.get("original_date_format")

    re_date = ""
    for i in range(3):
        if   original_date_format[i] == "Y": re_date += year_pattern
        elif original_date_format[i] == "M": re_date += month_pattern
        elif original_date_format[i] == "D": re_date += day_pattern
        if i != 2:
            re_date += RE_DELIM + "?"

    # 日付の前のデリミタを必須とする
    re_right = rf"(^|{RE_DELIM})"
    # 日付の後は時分秒などが続いている場合があるため、そこも含めて検索
    re_left = rf"(\d*($|{RE_DELIM}))"
    
    org_date = {}
    match = re.search(re_right + re_date + re_left, ctx.remains)
    if match:
        if len(match.group("year")) == 2:
            org_date["year2"] = match.group("year")
            org_date["year4"] = "20" + match.group("year")
        elif len(match.group("year")) == 4:
            org_date["year2"] = match.group("year")[2:]
            org_date["year4"] = match.group("year")
        org_date["month"] = match.group("month")
        org_date["day"] = match.group("day")
        ctx.remains = ctx.remains[:match.start()] + ctx.remains[match.end():]

    if not date_pos: return
    
    for i in date_pos:
        new_format = ctx.rules[i].get("format")

        try:
            new_format = re.sub(r"YYYY", org_date["year4"], new_format)
            new_format = re.sub(r"YY",   org_date["year2"], new_format)
            new_format = re.sub(r"MM",   org_date["month"], new_format)
            new_format = re.sub(r"DD",   org_date["day"],   new_format)

            ctx.extracts[i] = new_format
        except KeyError:
            ctx.extracts[i] = "No[Date]"
            ctx.has_error = True

def _extract_categories(ctx: RenameContext):
    cat_pos = []
    for i, element in enumerate(ctx.rules):
        if element["kind"] not in ["DATE", "VERSION", "NAME"]:
            cat_pos.append(i)
    
    if not cat_pos: 
        return

    # requirementに関わらずすべて抜き出す
    org_cat = {}
    for i in cat_pos:
        category = ctx.rules[i].get("kind")
        org_cat[category] = []
        for item, patterns in ctx.rules[i].get("items").items():
            patterns_cat_escaped = [re.escape(t) for t in patterns]
            re_cat = "|".join(patterns_cat_escaped)
            re_cat_unit = _build_word_search_pattern(re_cat)

            match = re.search(re_cat_unit, ctx.remains)
            if match:
                org_cat[category].append(item)
                ctx.remains = ctx.remains[:match.start()] + ctx.remains[match.end():]

    # requirementを満たすものだけ置き換え
    for i in cat_pos:
        requiremnts = ctx.rules[i].get("requirement")
        # requirementsが空ならTrue
        is_valid_cat = not bool(requiremnts)
        if requiremnts:
            for req in requiremnts:
                if (req.startswith(".") and req == Path(ctx.org_file).suffix):
                    is_valid_cat = True
                elif req in ctx.org_file:
                    is_valid_cat = True
            
        category = ctx.rules[i].get("kind")
        if is_valid_cat:
            if len(org_cat[category]) == 1:
                ctx.extracts[i] = org_cat[category][0]
            elif len(org_cat[category]) > 1:
                ctx.extracts[i] = f"Ambig[{"_".join(org_cat[category])}]"
                ctx.has_warn = True
            else:
                ctx.extracts[i] = f"No[{category}]"
                ctx.has_error = True
        else:
            ctx.extracts[i] = f"No[{category}]"
            ctx.has_error = True
         
def _pick_similar_version(org_vers: list, ver_rules: dict) -> str:
    if not org_vers:
        return ""
    
    target_prefix = ver_rules.get("prefix", "")
    target_format = ver_rules.get("format", "")
    # 理想とする形を一度作ってみる
    ideal_template = target_prefix + target_format.replace("n", "1")

    best_ver = org_vers[0]
    min_distance = float("inf")

    for org_ver in org_vers:
        # 編集距離が最も短いものを探す
        dist = Levenshtein.distance(org_ver, ideal_template)
        if dist < min_distance:
            min_distance = dist
            best_ver = org_ver
            
    return best_ver

def _extract_versions(ctx: RenameContext):
    ver_pos = []
    for i, element in enumerate(ctx.rules):
        if element["kind"] == "VERSION":
            ver_pos.append(i)
  
    # 接頭辞(v/ver/version)は任意
    # その後ろに「区切り文字（任意）＋数字（必須）」のセットが1回以上続く
    re_ver = rf"(?P<main>(v|ver|version)?({RE_DELIM}?\d+)+)"
    re_ver_unit = _build_word_search_pattern(re_ver)

    delimiter = ctx.settings.get("delimiter")
    org_vers = []
    
    # 破壊的変更を防ぐため、一時的な文字列でマッチングを行う
    current_remains = ctx.remains
    while True:
        match = re.search(re_ver_unit, current_remains)
        if not match: 
            break
        
        org_vers.append(match.group("main").rstrip("."))
        # くっつかないようにdelimiterを挟んでおく
        current_remains = current_remains[:match.start()] + delimiter + current_remains[match.end():]

    if not ver_pos: 
        return

    for i in ver_pos:
        ver_rules = ctx.rules[i]
        suitable_org_ver = _pick_similar_version(org_vers, ver_rules)
        
        if not suitable_org_ver:
            ctx.extracts[i] = "No[Version]"
            ctx.has_error = True
            continue

        # 元のバージョンから数字だけを抽出する (例: "v1.2.3" -> ["1", "2", "3"])
        digits = re.findall(r"\d+", suitable_org_ver)
        
        # 新しいフォーマット（例: "n.n.nnn"）の 'n' を、抽出した数字で順番に置換していく
        new_format = ver_rules.get("format", "")
        prefix = re.escape(ver_rules.get("prefix", ""))
        
        new_ver = ""
        digit_idx = 0
        
        # フォーマット文字列を解析して置換
        tokens = re.split(r"(n+)", new_format)
        for token in tokens:
            if "n" in token:
                if digit_idx < len(digits):
                    new_ver += digits[digit_idx].zfill(len(token))
                    digit_idx += 1
                else:
                    # サブバージョンが足りない場合は、サブバージョンを0とする
                    new_ver += "0".zfill(len(token))
                    ctx.has_warn = True
            else:
                new_ver += token

        ctx.extracts[i] = prefix + new_ver
        
        # 使用したバージョン文字列を ctx.remains から削除（NAME処理に残さないため）
        ctx.remains = ctx.remains.replace(suitable_org_ver, "", 1)
        # リストからも削除（1つのバージョンが複数のVERSIONルールに重複して取られないようにする）
        if suitable_org_ver in org_vers:
            org_vers.remove(suitable_org_ver)

def _extract_names(ctx: RenameContext):
    name_pos = []
    for i, element in enumerate(ctx.rules):
        if element["kind"] == "NAME":
            name_pos.append(i)
    
    if not name_pos: return

    raw_delimiter = ctx.settings.get("delimiter")
    escaped_delimiter = re.escape(raw_delimiter)
    for i in name_pos:
        if ctx.rules[i].get("remove_internal_delimiter"):
            name = re.sub(RE_DELIM, "", ctx.remains)
        else:
            # 内部区切りを削除しない場合でも、delimiterが複数連続しているなら1つにする
            # 検索にはescaped_delimiterを使い、置換結果にはraw_delimiterを使う
            name = re.sub(escaped_delimiter + r"{2,}", lambda _: raw_delimiter, ctx.remains)

        if name:
            ctx.extracts[i] = name
        else:
            ctx.extracts[i] = "No[Name]"
            ctx.has_error = True

def _rename_file(org_file: str, rules: list, settings: dict) -> tuple[str, bool, bool]:
    remains = Path(org_file).stem
    extracts = [""] * len(rules)

    ctx = RenameContext(
        rules=rules,
        settings=settings,
        org_file=org_file,
        remains=remains, 
        extracts=extracts
        )

    _extract_dates(ctx)
    _extract_categories(ctx)
    _extract_versions(ctx)
    _extract_names(ctx)

    new_file = settings.get("delimiter").join(ctx.extracts)

    return new_file, ctx.has_error, ctx.has_warn


def rename_all_files(org_file_list: List[str], rules: list, settings: dict) -> Dict[str, dict]:
    seq_style  = settings.get("sequence").get("style")
    seq_format = settings.get("sequence").get("format")

    match = re.search(r"n+", seq_format)
    seq_digit = len(match.group()) if match else 1

    new_file_dict_sequenced = defaultdict(list)
    file_counts = defaultdict(int)
    for org_file in org_file_list:
        suffix = Path(org_file).suffix
        new_file, has_error, has_warn = _rename_file(org_file, rules, settings)

        base_name_with_suffix = new_file + suffix
        other_conflicts = file_counts[base_name_with_suffix]

        sequence = ""
        if seq_style == "always":
            sequence_val = str(other_conflicts + 1).zfill(seq_digit)
            sequence = seq_format.replace("n" * seq_digit, sequence_val)
            
        elif seq_style == "all_overlaps":
            if other_conflicts >= 1:
                sequence_val = str(other_conflicts).zfill(seq_digit)
                sequence = seq_format.replace("n" * seq_digit, sequence_val)
        
        file_counts[base_name_with_suffix] += 1
        new_file_dict_sequenced[org_file] = {
            "new_file": new_file + sequence + suffix, 
            "has_error":has_error, 
            "has_warn": has_warn
            }
            
    return new_file_dict_sequenced
