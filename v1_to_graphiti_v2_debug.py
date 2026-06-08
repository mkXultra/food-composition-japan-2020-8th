#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1 JSONファイルを読み込んでGraphitiにadd_tripletで追加するスクリプト（デバッグ版）
- デバッグログを追加してキャッシュの動作を確認
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

# デバッグ用カウンター
debug_stats = {
    'cache_hits': 0,
    'cache_misses': 0,
    'nodes_created': 0,
    'edges_created': 0
}


async def get_or_create_nutrient(graphiti: Graphiti, name: str, group_id: str = "default") -> EntityNode:
    """
    栄養素ノードを取得または作成
    同じ名前の栄養素は再利用する（メモリキャッシュ使用）
    """
    # 改行を削除してクリーンな名前にする
    clean_name = name.replace('\n', '')

    # キャッシュから取得
    cache_key = f"{group_id}:{clean_name}"

    print(f"    [DEBUG] Looking for nutrient: '{clean_name}' with cache_key: '{cache_key}'")
    print(f"    [DEBUG] Current cache keys: {list(nutrient_cache.keys())[:5]}...")  # 最初の5個のキーを表示

    if cache_key in nutrient_cache:
        debug_stats['cache_hits'] += 1
        cached_node = nutrient_cache[cache_key]
        print(f"    [CACHE HIT] Using cached nutrient: {clean_name}")
        print(f"    [DEBUG] Cached node UUID: {cached_node.uuid[:8]}...")
        print(f"    [DEBUG] Cached node name: {cached_node.name}")
        return cached_node

    # 新規作成
    debug_stats['cache_misses'] += 1
    debug_stats['nodes_created'] += 1
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
    print(f"    [CACHE MISS] Created new nutrient: {clean_name}")
    print(f"    [DEBUG] New node UUID: {nutrient_node.uuid[:8]}...")
    print(f"    [DEBUG] Storing in cache with key: '{cache_key}'")

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
            print(f"  [CACHE HIT] Using cached food: {food_name} ({food_number})")
            return food_cache[cache_key]

    # 新規作成
    debug_stats['nodes_created'] += 1
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

    print(f"  [CACHE MISS] Created new food: {food_name}")
    print(f"  [DEBUG] Food UUID: {food_node.uuid[:8]}...")

    return food_node


async def add_food_to_graph(graphiti: Graphiti, json_file_path: str, group_id: str = "default", skip_existing: bool = True, skip_fact_embedding: bool = True):
    """
    v1 JSONファイルを読み込んでGraphitiに追加（デバッグ版）
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

    print(f"\n{'='*60}")
    print(f"Processing food: {data['食品名']} ({food_number})")
    print(f"{'='*60}")

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
            print(f"  [SKIP] Existing food: {data['食品名']} ({food_number})")
            return

    now = utc_now()

    # 食品ノードを取得または作成
    food_node = await get_or_create_food(graphiti, data, group_id)

    # 栄養成分を追加
    nutrients = data.get('栄養成分', [])
    print(f"  Processing {len(nutrients)} nutrients...")

    # 全ての栄養成分を処理
    for i, nutrient in enumerate(nutrients):
        print(f"\n  [{i+1}/{len(nutrients)}] Processing nutrient: {nutrient['名前']}")
        print(f"    Amount: {nutrient['含有量']}{nutrient['単位']}")

        # 栄養素ノードを取得または作成
        nutrient_node = await get_or_create_nutrient(
            graphiti,
            nutrient['名前'],
            group_id
        )

        # エッジを作成（含有量情報をエッジに持たせる）
        amount_str = str(nutrient['含有量'])
        is_estimated = False

        if amount_str.startswith('(') and amount_str.endswith(')'):
            is_estimated = True
            amount_clean = amount_str[1:-1]
        else:
            amount_clean = amount_str

        edge_attributes = {
            'amount': amount_clean,
            'unit': nutrient['単位']
        }

        if is_estimated:
            edge_attributes['is_estimated'] = True

        edge = EntityEdge(
            name='CONTAINS',
            source_node_uuid=food_node.uuid,
            target_node_uuid=nutrient_node.uuid,
            group_id=group_id,
            fact=f"{nutrient['含有量']}{nutrient['単位']}",
            valid_at=now,
            created_at=now,
            episodes=[],
            expired_at=None,
            attributes=edge_attributes
        )

        # fact埋め込みをスキップする場合、ダミーの埋め込みを設定
        if skip_fact_embedding:
            edge.fact_embedding = [0.001] * 1024

        # トリプレットを追加
        debug_stats['edges_created'] += 1
        print(f"    [CREATE EDGE] {food_node.name[:30]}... -> {nutrient_node.name}")
        print(f"    [DEBUG] Edge: {food_node.uuid[:8]}... -> {nutrient_node.uuid[:8]}...")
        await graphiti.add_triplet(food_node, edge, nutrient_node)

        print(f"    [DONE] {nutrient['名前']} ({nutrient['含有量']}{nutrient['単位']})")

    print(f"\n[COMPLETED] {data['食品名']}")


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

    print(f"\n{'#'*60}")
    print(f"# Starting processing of {len(json_files)} files")
    print(f"{'#'*60}")

    for json_file in json_files:
        print(f"\nProcessing file: {json_file}")
        await add_food_to_graph(graphiti, str(json_file))

    print(f"\n{'#'*60}")
    print(f"# Processing completed")
    print(f"{'#'*60}")
    print(f"Files processed: {len(json_files)}")
    print(f"Cache hits: {debug_stats['cache_hits']}")
    print(f"Cache misses: {debug_stats['cache_misses']}")
    print(f"Nodes created: {debug_stats['nodes_created']}")
    print(f"Edges created: {debug_stats['edges_created']}")
    print(f"Cached nutrients: {len(nutrient_cache)}")
    print(f"Cached foods: {len(food_cache)}")
    print("\nSample cached nutrient keys:")
    for key in list(nutrient_cache.keys())[:10]:
        print(f"  - {key}")

    await graphiti.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='食品成分JSONをGraphitiに追加（デバッグ版）')
    parser.add_argument('--limit', type=int, help='処理するJSONファイル数の上限')
    args = parser.parse_args()

    asyncio.run(main(limit=args.limit))