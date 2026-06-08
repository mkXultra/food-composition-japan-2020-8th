# 作業状況

## 完了した作業

### 1. JSON構造の比較と検証
- **v1構造** (`test_output/`): 基本情報 + 栄養成分（アミノ酸含む全て）
- **v2構造** (`case1_json_v2_output/`): 基本情報 + 栄養成分 + アミノ酸（分離） + アミノ酸組成計
- **結果**: v2構造でfcj-knowledge MCPへのadd_episodeが成功（27エンティティ作成）

### 2. 問題の特定
- `source='json'`でのLLM自動抽出は構造に依存して不安定
- v1構造では時々1つのエンティティにまとめられてしまう
- v2構造（分離型）の方がLLMが個別エンティティとして認識しやすい

### 3. 解決策の検討
- **アプローチ1**: カスタムエンティティタイプを定義してLLM抽出を改善
- **アプローチ2**: `add_triplet`メソッドで直接エンティティとエッジを作成（採用）

### 4. インフラのセットアップ
- Docker Compose環境構築済み（Neo4j + graphiti-mcp + mcp-neo4j-cypher）
- リセットスクリプト作成済み（`reset_all.sh`）
- graphiti-core 0.20.4インストール済み（venv環境）

## 現在の作業

### v1_to_graphiti.pyスクリプトの開発
- v1 JSON構造を読み込んで`add_triplet`でグラフ構築
- 食品を中心に栄養成分をCONTAINSエッジで接続
- **現在のエラー**: 
  ```
  Neo.ClientError.Procedure.ProcedureCallFailed: 
  Failed to invoke procedure `db.create.setNodeVectorProperty`: 
  'vector' must not be null
  ```
  - 原因: `food_node.save()`を直接呼んでいるが、name_embeddingがない
  - 解決策: `add_triplet`に任せるように修正が必要

## 次の作業

1. **v1_to_graphiti.pyの修正**
   - `food_node.save()`を削除
   - 最初の栄養成分で`add_triplet`を使用
   - 2つ目以降は既存の食品ノードを再利用

2. **動作確認**
   - アマランサスのデータでテスト
   - エンティティと関係性の確認
   - 検索機能のテスト

3. **大量データ処理**
   - 全CSVデータの変換（第2章第1表.csv）
   - バッチ処理の実装

## 環境情報

- **Neo4j**: localhost:7687 (user: neo4j, password: demodemo)
- **Python環境**: .venv/bin/activate
- **MCP接続**:
  - fcj-knowledge: http://localhost:8090
  - fcj-search: http://localhost:8091

## 重要な発見

1. **JSON構造が重要**: アミノ酸と栄養成分を分離した方がLLM抽出が安定
2. **add_triplet**使用時: 自動的にテキスト埋め込みが生成される
3. **エンティティ統一**: アミノ酸も「栄養成分」として扱う方がシンプル

## ファイル構成

```
/home/miyagi/dev/personal_biz/food-composition-japan-2020-8th/
├── test_output/              # v1 JSON（フラット構造）
├── case1_json_v2_output/     # v2 JSON（分離構造）
├── csv_to_case1_json.py      # v1変換スクリプト
├── csv_to_case1_json_v2.py   # v2変換スクリプト
├── v1_to_graphiti.py         # 作業中：add_triplet実装
├── reset_all.sh              # Docker環境リセット
├── docker-compose.yml
├── .env
└── 第2章第1表.csv            # 元データ
```