#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

# JSONファイルを読み込み
with open('case1_json_v2_output/01001_アマランサス_玄穀.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# JSON文字列として変換
json_str = json.dumps(data, ensure_ascii=False)

# fcj-knowledgeのadd_memory用のパラメータを作成
params = {
    "name": "アマランサス　玄穀",
    "episode_body": json_str,  # JSON文字列として渡す
    "source": "json",
    "source_description": "日本食品標準成分表2020年版（第八訂）"
}

# パラメータを表示
print("name:", params["name"])
print("source:", params["source"])
print("source_description:", params["source_description"])
print("episode_body (type):", type(params["episode_body"]))
print("episode_body (first 200 chars):", params["episode_body"][:200])