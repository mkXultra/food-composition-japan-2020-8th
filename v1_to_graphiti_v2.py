#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1 JSONファイルを読み込んでGraphitiにadd_tripletで追加するスクリプト（改善版）
- 栄養素ノードを共有（get or create方式）
- エッジに含有量情報を持たせる
- Graphiti APIを最大限活用
"""

import json
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Dict
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

# 栄養素ノードのキャッシュ（名前 -> EntityNode）
nutrient_cache: Dict[str, EntityNode] = {}
# 食品ノードのキャッシュ（食品番号 -> EntityNode）
food_cache: Dict[str, EntityNode] = {}


async def get_or_create_nutrient(graphiti: Graphiti, name: str, group_id: str = "default") -> EntityNode:
    """
    栄養素ノードを取得または作成
    同じ名前の栄養素は再利用する（メモリキャッシュ使用）
    """
    # 改行を削除してクリーンな名前にする
    clean_name = name.replace('\n', '')
    
    # キャッシュから取得
    cache_key = f"{group_id}:{clean_name}"
    if cache_key in nutrient_cache:
        print(f"    Using cached nutrient: {clean_name}")
        return nutrient_cache[cache_key]
    
    # 新規作成
    nutrient_node = EntityNode(
        name=clean_name,
        group_id=group_id,
        labels=['Entity', 'Nutrient'],
        summary=f"栄養素: {clean_name}",
        created_at=utc_now(),
        attributes={}
    )
    
    # キャッシュに保存
    nutrient_cache[cache_key] = nutrient_node
    print(f"    Created new nutrient: {clean_name}")
    
    return nutrient_node


async def get_or_create_food(graphiti: Graphiti, food_data: Dict, group_id: str = "default") -> EntityNode:
    """
    食品ノードを取得または作成
    同じ食品番号の食品は再利用する（メモリキャッシュ使用）
    """
    food_name = food_data['食品名']
    food_number = None
    
    # 基本情報から食品番号を取得
    for info in food_data.get('基本情報', []):
        if info['項目'] == '食品番号':
            food_number = info['値']
            break
    
    # キャッシュから取得
    if food_number:
        cache_key = f"{group_id}:{food_number}"
        if cache_key in food_cache:
            print(f"  Using cached food: {food_name} ({food_number})")
            return food_cache[cache_key]
    
    # 新規作成
    now = utc_now()
    food_node = EntityNode(
        name=food_name,
        group_id=group_id,
        labels=['Entity', 'Food'],
        summary=f"食品番号: {food_number}" if food_number else "",
        created_at=now,
        attributes={}
    )
    
    # 基本情報を属性として追加
    for info in food_data.get('基本情報', []):
        if info['項目'] == '食品群':
            food_node.attributes['food_group'] = info['値']
        elif info['項目'] == '食品番号':
            food_node.attributes['food_number'] = info['値']
        elif info['項目'] == '索引番号':
            food_node.attributes['index_number'] = info['値']
        elif info['項目'] == '備考':
            food_node.attributes['remarks'] = info['値']
    
    # キャッシュに保存
    if food_number:
        cache_key = f"{group_id}:{food_number}"
        food_cache[cache_key] = food_node
    
    print(f"  Created new food: {food_name}")
    
    return food_node


async def add_food_to_graph(graphiti: Graphiti, json_file_path: str, group_id: str = "default", skip_existing: bool = True, skip_fact_embedding: bool = True):
    """
    v1 JSONファイルを読み込んでGraphitiに追加（改善版）
    
    Args:
        skip_existing: 既存の食品をスキップするかどうか（デフォルト: True）
        skip_fact_embedding: fact埋め込みをスキップするかどうか（デフォルト: True）
    """
    
    # JSONファイルを読み込み
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 食品番号を取得
    food_number = None
    for info in data.get('基本情報', []):
        if info['項目'] == '食品番号':
            food_number = info['値']
            break
    
    # 既存食品をチェック（食品番号で）
    if skip_existing and food_number:
        query = """
        MATCH (f:Food {food_number: $food_number, group_id: $group_id})
        RETURN f.name as name
        LIMIT 1
        """
        result = await graphiti.driver.execute_query(
            query,
            food_number=food_number,
            group_id=group_id
        )
        
        if result.records and len(result.records) > 0:
            print(f"  Skipping existing food: {data['食品名']} ({food_number})")
            return
    
    now = utc_now()
    
    # 食品ノードを取得または作成
    food_node = await get_or_create_food(graphiti, data, group_id)
    
    # 栄養成分を追加
    nutrients = data.get('栄養成分', [])
    print(f"  Processing {len(nutrients)} nutrients...")
    
    # 全ての栄養成分を処理
    for i, nutrient in enumerate(nutrients):
        print(f"  [{i+1}/{len(nutrients)}] Processing {nutrient['名前']}...")
        
        # 栄養素ノードを取得または作成
        nutrient_node = await get_or_create_nutrient(
            graphiti,
            nutrient['名前'],
            group_id
        )
        print(f"    DEBUG: Node UUID for {nutrient['名前']}: {nutrient_node.uuid}")
        
        # エッジを作成（含有量情報をエッジに持たせる）
        amount_str = str(nutrient['含有量'])  # 文字列として扱う
        is_estimated = False

        # カッコの有無をチェックして推定値を判定
        if amount_str.startswith('(') and amount_str.endswith(')'):
            is_estimated = True
            amount_clean = amount_str[1:-1]  # カッコを除去
        else:
            amount_clean = amount_str

        edge_attributes = {
            'amount': amount_clean,  # カッコを除去した値
            'unit': nutrient['単位']
        }

        # 推定値の場合はフラグを追加
        if is_estimated:
            edge_attributes['is_estimated'] = True
        
        edge = EntityEdge(
            name='CONTAINS',
            source_node_uuid=food_node.uuid,
            target_node_uuid=nutrient_node.uuid,
            group_id=group_id,
            fact=f"{nutrient['含有量']}{nutrient['単位']}",  # シンプルな含有量表記
            valid_at=now,
            created_at=now,
            episodes=[],
            expired_at=None,
            attributes=edge_attributes
        )
        
        # fact埋め込みをスキップする場合、ダミーの埋め込みを設定
        if skip_fact_embedding:
            # 1024次元の小さな値のベクトル（完全なゼロベクトルは類似度計算でエラーになる）
            edge.fact_embedding = [0.001] * 1024
        
        # トリプレットを追加
        print(f"    Creating triplet... source={food_node.uuid[:8]}, target={nutrient_node.uuid[:8]}")
        await graphiti.add_triplet(food_node, edge, nutrient_node)
        
        print(f"    Done: {nutrient['名前']} ({nutrient['含有量']}{nutrient['単位']})")
    
    print(f"Completed: {data['食品名']}")


async def main(limit=None):
    """メイン処理

    Args:
        limit: 処理するファイル数の上限（Noneの場合は全ファイル処理）
    """
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

    # ファイル数の制限を適用
    json_files = list(test_output_dir.glob('*.json'))
    if limit:
        json_files = json_files[:limit]
    
    for json_file in json_files:
        print(f"\nProcessing: {json_file}")
        await add_food_to_graph(graphiti, str(json_file))
    
    print("\n=== 処理完了 ===")
    print(f"処理したファイル数: {len(json_files)}")
    print(f"キャッシュされた栄養素数: {len(nutrient_cache)}")
    print(f"キャッシュされた食品数: {len(food_cache)}")
    
    await graphiti.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='食品成分JSONをGraphitiに追加')
    parser.add_argument('--limit', type=int, help='処理するJSONファイル数の上限')
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit))