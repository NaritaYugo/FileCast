kind_separator = "KINDSEPARATOR"

DEFAULT_YAMLS={
    "rule": 
    [
        {"kind": "NAME", "remove_internal_delimiter": True},
        {"kind": "DATE", "format": "YY-MM-DD"}
    ],

    "categories": 
    {
        "Fruits":
            {"REQ": ["fruits"],
            "sweet": ["apple", "grape"],
            "sour": ["lemon"]},

        "Game":
            {"REQ": "_",
            "VFX": ["effect", "vfx", "fx", "efx"]}
    },
    
    "settings": 
    {
        "original_date_format": "YMD",
        "delimiter": "_",
        "sequence": {"style": "all_overlaps", "format": "(n)"}
    },

    "cache":
    {
        "target_dir": "",
        "filename": {}
    },
}

CATEGORY_REFERENCE = """【記述方法】
グループ名:
    REQ: このグループを使用する要件(requirement)
    カテゴリ名1: 要素1, 要素2,...
    カテゴリ名2: 要素1, 要素2,...
    ...

※コロンの後に半角スペース1つが必要です
※インデントは半角スペース2つ(または4つ)で行います
※このエディタでは、Tabキーを押すとスペース2つが挿入されます

【REQの書き方】
1. 要件なし(常に適用する場合)
    REQの行を書かない
    ※"REQ: _"と書いてもOK

2. 特定の文字列が含まれるファイルのみ適用
    "REQ: picture, image"のように書く
    ※複数書いた場合いずれか1つでも存在すれば適用

3. 特定の拡張子のファイルのみ適用
    "REQ: .png, .jpeg"のようにドットから始める
    ※文字列と拡張子をまぜてもOK
"""