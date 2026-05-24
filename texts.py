DEFAULT_YAMLS={
    "rules": 
    [
        {"kind": "NAME", "remove_internal_delimiter": True},
        {"kind": "DATE", "format": "YY-MM-DD"}
    ],

    "categories": 
    {
        'Game': 
        {
            'REQ': ['_ASTERISK'], 
            'bg': ['background', 'bg'], 
            'chr': ['character', 'chr', 'char'], 
            'rig': ['rig'], 
            'ui': ['ui'], 
            'shader': ['shader'], 
            'music': ['music', 'audio', 'bgm', 'voice'], 
            'movie': ['movie', 'anim', 'animation'], 
            'enemy': ['boss', 'slime', 'enemy'], 
            'material': ['mat', 'material']
        }, 
        'Enemy': {
            'REQ': ['_EXCLAMATION'], 
            'Boss': ['Boss'], 
            'others': ['slime']
        }, 
        'Status': {
            'REQ': ['_EXCLAMATION'], 
            'tmp': ['temp', 'tmp'], 
            'draft': ['draft'], 
            'cache': ['cache']
        }
    },
    
    "settings": 
    {
        "original_date_format": "YMD",
        "delimiter": "_",
        "sequence": {"style": "all_overlaps", "format": "(n)"}
    },

    "caches":
    {
        "target_dir": "",
        "filename": {}
    },
}

CATEGORY_REFERENCE = """【yaml記述方法】
1. コロンの後に半角スペース1つが必要です
    が、こっちで入れとくので無くても動きます

2. インデントは半角スペース2つ(または4つ)で行い、Tabは使用できません
    が、このエディタではTabキーを押すとスペース2個が入力されるので、Tabでよいです

3. リストを1行に書く場合、角括弧[]で囲う必要があります
    が、こっちで入れとくので書かなくてよいです

【記述方法】
カテゴリ名:
    REQ: 要件パターン, 要件パターン, ...
    アイテム名: 検索パターン, 検索パターン, ...
    アイテム名: 検索パターン, 検索パターン, ...
    ...

と書くことで、
・要件パターンのいずれかがファイル内に含まれる場合に限って、
・検索パターンのいずれかに合致するものを、
・アイテム名として配置します

検索パターンとアイテム名が同じ場合、
「アイテム名: アイテム名」を、
「アイテム名」に省略できます。

検索パターンにアイテム名を含む場合、
「アイテム名: アイテム名, 検索パターン, ...」を、
「アイテム名:: 検索パターン, ...」に省略できます。

【REQの書き方】
1. 特定の文字列が含まれるファイルのみ適用
    "REQ: picture, image"のように書く

2. 特定の拡張子のファイルのみ適用
    "REQ: .png, .jpeg"のようにドットから始める

3. 要件なし(常に適用する場合)
    REQの行を書かない、または、"REQ: *" 

4. アイテムが存在する場合のみ(存在しなくてもエラーを出さない)
    "REQ: !"と書く 
"""