#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1 JSONファイルを読み込んでGraphitiにadd_tripletで追加するスクリプト
"""

import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
import os
from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge
from graphiti_core.utils.datetime_utils import utc_now

load_dotenv()

# Neo4j接続設定（ホストから接続するためlocalhostを使用）
NEO4J_URI = 'bolt://localhost:7687'
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'demodemo')


async def add_food_to_graph(graphiti: Graphiti, json_file_path: str, group_id: str = "default"):
    """v1 JSONファイルを読み込んでGraphitiに追加"""
    
    # JSONファイルを読み込み
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    now = utc_now()
    
    # 食品のメインノードを作成
    food_node = EntityNode(
        name=data['食品名'],
        group_id=group_id,
        labels=['Entity', 'Food'],
        summary=f"食品番号: {data['基本情報'][1]['値']}" if len(data['基本情報']) > 1 else "",
        created_at=now,
        attributes={}
    )
    
    # 基本情報を属性として追加
    for info in data.get('基本情報', []):
        if info['項目'] == '食品群':
            food_node.attributes['food_group'] = info['値']
        elif info['項目'] == '食品番号':
            food_node.attributes['food_number'] = info['値']
        elif info['項目'] == '索引番号':
            food_node.attributes['index_number'] = info['値']
        elif info['項目'] == '備考':
            food_node.attributes['remarks'] = info['値']
    
    # 栄養成分を追加
    nutrients = data.get('栄養成分', [])
    print(f"  Processing {len(nutrients)} nutrients...")
    
    for i, nutrient in enumerate(nutrients):  # 全ての栄養成分を処理
        print(f"  [{i+1}/{len(nutrients)}] Adding {nutrient['名前']}...")
        # 栄養成分ノードを作成
        nutrient_node = EntityNode(
            name=nutrient['名前'].replace('\n', ''),  # 改行を削除
            group_id=group_id,
            labels=['Entity', 'Nutrient'],
            summary=f"{nutrient['含有量']}{nutrient['単位']}",
            created_at=now,
            attributes={
                'content': nutrient['含有量'],
                'unit': nutrient['単位']
            }
        )
        
        # エッジを作成
        edge = EntityEdge(
            name='CONTAINS',
            source_node_uuid=food_node.uuid,
            target_node_uuid=nutrient_node.uuid,
            group_id=group_id,
            fact=f"{data['食品名']}は{nutrient['名前']}を{nutrient['含有量']}{nutrient['単位']}含有",
            valid_at=now,
            created_at=now,
            episodes=[],
            expired_at=None
        )
        
        # トリプレットを追加
        print(f"    Creating triplet...")
        await graphiti.add_triplet(food_node, edge, nutrient_node)
        
        print(f"    Done: {nutrient['名前']} ({nutrient['含有量']}{nutrient['単位']})")
    
    print(f"Completed: {data['食品名']}")


async def main():
    """メイン処理"""
    # Graphitiクライアントを初期化
    graphiti = Graphiti(
        NEO4J_URI,
        NEO4J_USER,
        NEO4J_PASSWORD
    )
    
    # インデックスと制約を構築
    await graphiti.build_indices_and_constraints()
    
    # test_outputディレクトリのv1 JSONファイルを処理
    test_output_dir = Path('test_output')
    
    # 01001_アマランサス_玄穀.jsonをテスト
    test_file = test_output_dir / '01001_アマランサス_玄穀.json'
    if test_file.exists():
        print(f"Processing: {test_file}")
        await add_food_to_graph(graphiti, str(test_file))
    
    # 必要に応じて他のファイルも処理
    # for json_file in test_output_dir.glob('*.json'):
    #     print(f"Processing: {json_file}")
    #     await add_food_to_graph(graphiti, str(json_file))
    
    await graphiti.close()


if __name__ == "__main__":
    asyncio.run(main())