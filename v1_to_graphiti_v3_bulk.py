#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v1 JSONファイルをadd_nodes_and_edges_bulkで一括追加するスクリプト（高速版）
- 各食品の全ての栄養素を一括でバルク処理
- LLM呼び出しを最小限に
"""

import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# graphiti-coreをインポート
sys.path.insert(0, str(Path(__file__).parent / 'graphiti-core'))

from graphiti_core import Graphiti
from graphiti_core.nodes import EntityNode
from graphiti_core.edges import EntityEdge
from graphiti_core.utils.datetime_utils import utc_now
from graphiti_core.utils.bulk_utils import add_nodes_and_edges_bulk

# 栄養素ノードをキャッシュ（メモリ上で管理）
nutrient_node_cache: Dict[str, EntityNode] = {}

# 埋め込みをスキップするフラグ（テスト用）
SKIP_EMBEDDINGS = True


async def get_or_create_nutrient(nutrient_name: str, group_id: str) -> EntityNode:
    """栄養素ノードを取得または作成（キャッシュを使用）"""

    if nutrient_name in nutrient_node_cache:
        print(f"      Using cached nutrient: {nutrient_name}")
        return nutrient_node_cache[nutrient_name]

    # 新しい栄養素ノードを作成
    nutrient_node = EntityNode(
        name=nutrient_name,
        group_id=group_id,
        labels=['Entity', 'Nutrient'],
        summary=f"栄養素: {nutrient_name}",
        created_at=utc_now()
    )

    # ダミーの埋め込みを設定（埋め込みスキップの場合）
    if SKIP_EMBEDDINGS:
        nutrient_node.name_embedding = [0.001] * 1024

    nutrient_node_cache[nutrient_name] = nutrient_node
    print(f"      Created new nutrient: {nutrient_name}")
    return nutrient_node


async def process_food_bulk(graphiti: Graphiti, data: dict, group_id: str = 'default', skip_existing: bool = True):
    """
    食品データを一括処理で追加（高速化版）

    Args:
        graphiti: Graphitiインスタンス
        data: 食品データ（case1_json_v2形式）
        group_id: グループID
    """
    now = utc_now()

    # 基本情報から必要な情報を抽出
    basic_info = {item['項目']: item['値'] for item in data.get('基本情報', [])}
    food_number = basic_info.get('食品番号', '')
    food_group = basic_info.get('食品群', '')
    index_number = basic_info.get('索引番号', '')
    remarks = basic_info.get('備考', '')

    print(f"\nProcessing food (BULK): {data['食品名']} (番号: {food_number})")

    # 既存のFoodエンティティがあればスキップ
    if skip_existing:
        if food_number:
            query = (
                """
                MATCH (f:Food {group_id: $group_id, food_number: $food_number})
                RETURN f.uuid AS uuid
                LIMIT 1
                """
            )
            result = await graphiti.driver.execute_query(
                query,
                params={
                    'group_id': group_id,
                    'food_number': food_number,
                },
                routing_='r',
            )
        else:
            # 食品番号が無い場合は名称でフォールバックチェック
            query = (
                """
                MATCH (f:Food {group_id: $group_id, name: $name})
                RETURN f.uuid AS uuid
                LIMIT 1
                """
            )
            result = await graphiti.driver.execute_query(
                query,
                params={
                    'group_id': group_id,
                    'name': data['食品名'],
                },
                routing_='r',
            )

        if getattr(result, 'records', []) and len(result.records) > 0:
            print(f"  Skipping existing food entity: {data['食品名']} ({food_number})")
            return

    # 1. 食品ノードを作成
    food_node = EntityNode(
        name=data['食品名'],
        group_id=group_id,
        labels=['Entity', 'Food'],
        summary=f"食品番号: {food_number}",
        created_at=now,
        attributes={
            'food_number': food_number,
            'food_group': food_group,
            'index_number': index_number,
            'remarks': remarks,
            'labels': ['Food', 'Entity']
        }
    )

    # ダミーの埋め込みを設定
    if SKIP_EMBEDDINGS:
        food_node.name_embedding = [0.001] * 1024

    # 2. 全栄養素のノードとエッジを一括で準備
    entity_nodes = [food_node]
    entity_edges = []

    # test_outputのJSONは栄養成分にすべて含まれている
    for nutrient in data.get('栄養成分', []):
        # 栄養素ノードを取得または作成
        nutrient_node = await get_or_create_nutrient(
            nutrient['名前'],
            group_id
        )

        # このノードがまだリストに入っていない場合は追加
        if nutrient_node not in entity_nodes:
            entity_nodes.append(nutrient_node)

        # エッジを作成
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

        # ダミーの埋め込みを設定
        if SKIP_EMBEDDINGS:
            edge.fact_embedding = [0.001] * 1024

        entity_edges.append(edge)

    print(f"  Prepared {len(entity_nodes)} nodes and {len(entity_edges)} edges")

    # 3. 一括でデータベースに保存
    print(f"  Executing bulk insert...")
    await add_nodes_and_edges_bulk(
        driver=graphiti.driver,
        episodic_nodes=[],  # エピソードノードは今回使わない
        episodic_edges=[],  # エピソードエッジも使わない
        entity_nodes=entity_nodes,
        entity_edges=entity_edges,
        embedder=graphiti.embedder
    )

    print(f"  ✓ Completed: {data['食品名']} - {len(entity_edges)} nutrients added in bulk")


async def main(limit=None):
    """メイン処理

    Args:
        limit: 処理する食品数の上限（デバッグ用）
    """
    # Graphitiインスタンスを作成
    print("Initializing Graphiti...")
    graphiti = Graphiti(
        uri='bolt://localhost:7687',
        user=os.getenv('NEO4J_USER', 'neo4j'),
        password=os.getenv('NEO4J_PASSWORD', 'demodemo')
    )

    try:
        # データディレクトリのパス
        data_dir = Path(__file__).parent / 'test_output'

        if not data_dir.exists():
            print(f"Error: Directory {data_dir} not found!")
            return

        # JSONファイルを取得
        json_files = sorted(data_dir.glob('*.json'))

        if limit:
            json_files = json_files[:limit]

        print(f"Found {len(json_files)} JSON files to process")

        # 処理時間の測定開始
        import time
        start_time = time.time()

        # 各ファイルを処理
        for i, json_file in enumerate(json_files, 1):
            print(f"\n[{i}/{len(json_files)}] Loading: {json_file.name}")

            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 食品データをバルク処理で追加
            await process_food_bulk(graphiti, data)

        # 処理時間を表示
        elapsed = time.time() - start_time
        print(f"\n\n=== Processing Complete ===")
        print(f"Total time: {elapsed:.2f} seconds")
        print(f"Average time per food: {elapsed/len(json_files):.2f} seconds")
        print(f"Total foods: {len(json_files)}")
        print(f"Total unique nutrients: {len(nutrient_node_cache)}")

    finally:
        # クリーンアップ
        await graphiti.driver.close()


if __name__ == '__main__':
    # コマンドライン引数の処理
    import sys

    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
        print(f"Processing limited to {limit} foods")

    # 非同期処理を実行
    asyncio.run(main(limit))
