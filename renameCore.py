from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Dict

from rapidfuzz.distance import Levenshtein

import texts


RE_DELIM = r"(_|-|\.| |^|$)"

@dataclass
class RenameContext:
    rules: list
    settings: dict
    org_file: str
    remains: str
    extracts: list
    has_error: bool = False
    has_warn: bool = False

def _extract_dates(ctx: RenameContext):
    date_pos = []
    for i, element in enumerate(ctx.rules):
        if element["kind"] == "DATE":
            date_pos.append(i)
    
    year_pattern  = r"(?P<year>(20|19)?([0-9][0-9]))"
    month_pattern = r"(?P<month>0[1-9]|1[0-2])"
    day_pattern   = r"(?P<day>0[1-9]|[1-2][0-9]|3[0-1])"

    original_date_format = ctx.settings.get("original_date_format")

    re_date = ""
    for i in range(3):
        if   original_date_format[i] == "Y": re_date += year_pattern
        elif original_date_format[i] == "M": re_date += month_pattern
        elif original_date_format[i] == "D": re_date += day_pattern
        if i != 2:
            re_date += RE_DELIM
    
    org_date = {}
    match = re.search(re_date, ctx.remains)
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

    if not date_pos: 
        return
    
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
        target_cat = ctx.rules[i].get("target")
        re_cat = "|".join(target_cat)

        match = re.search(re_cat, ctx.remains)
        if match:
            category = ctx.rules[i].get("kind").split(texts.kind_separator)[1]
            org_cat[category] = match.group(0)
            ctx.remains = ctx.remains[:match.start()] + ctx.remains[match.end():]

    # requirementを満たすものだけ置き換え
    for i in cat_pos:
        requiremnts = ctx.rules[i].get("requirement")
        is_valid_cat = False
        if requiremnts:
            for req in requiremnts:
                if req.startswith(".") and req == Path(ctx.org_file).suffix:
                    is_valid_cat = True
                elif req in ctx.org_file:
                    is_valid_cat = True
            
        category = ctx.rules[i].get("kind").split(texts.kind_separator)[1]
        if is_valid_cat:
            try:
                ctx.extracts[i] = org_cat[category]
            except KeyError:
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

    delimiter = ctx.settings.get("delimiter")
    org_vers = []
    
    # 破壊的変更を防ぐため、一時的な文字列でマッチングを行う
    current_remains = ctx.remains
    while True:
        match = re.search(re_ver, current_remains, re.IGNORECASE)
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
        prefix = ver_rules.get("prefix", "")
        
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

    delimiter = ctx.settings.get("delimiter")
    for i in name_pos:
        if ctx.rules[i].get("remove_internal_delimiter"):
            name = re.sub(RE_DELIM, "", ctx.remains)
        else:
            # 内部区切りを削除しない場合でも、delimiterが複数連続しているなら1つにする
            name = re.sub(delimiter + r"{2,}", delimiter, ctx.remains)

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

    new_file_list_raw = []
    new_file_dict_sequenced = defaultdict(list)
    for org_file in org_file_list:
        suffix = Path(org_file).suffix
        new_file, has_error, has_warn = _rename_file(org_file, rules, settings)

        other_conflicts = new_file_list_raw.count(new_file + suffix)

        sequence = ""
        if seq_style == "always":
            sequence_val = str(other_conflicts + 1).zfill(seq_digit)
            sequence = seq_format.replace("n" * seq_digit, sequence_val)
            
        elif seq_style == "all_overlaps":
            if other_conflicts >= 1:
                sequence_val = str(other_conflicts).zfill(seq_digit)
                sequence = seq_format.replace("n" * seq_digit, sequence_val)
        
        new_file_list_raw.append(new_file + suffix)
        new_file_dict_sequenced[org_file] = {
            "new_file": new_file + sequence + suffix, 
            "has_error":has_error, 
            "has_warn": has_warn
            }
            
    return new_file_dict_sequenced
