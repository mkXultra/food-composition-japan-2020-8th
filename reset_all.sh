#!/bin/bash

echo "========================================="
echo "完全リセットを開始します..."
echo "========================================="

# 1. Docker Composeを停止
echo ""
echo "1. Docker Composeを停止中..."
docker compose down

# 2. Neo4jのボリュームを削除
echo ""
echo "2. Neo4jのボリュームを削除中..."
docker volume rm food-composition-japan-2020-8th_neo4j_data food-composition-japan-2020-8th_neo4j_logs 2>/dev/null || true

# 3. Docker Composeを起動
echo ""
echo "3. Docker Composeを起動中..."
docker compose up -d

# 4. Neo4jの起動を待つ（docker compose upが既に待機しているので短時間で確認）
echo ""
echo "4. Neo4jの起動を確認中..."
sleep 5
if docker exec food-composition-japan-2020-8th-neo4j-1 cypher-shell -u neo4j -p demodemo "RETURN 1" >/dev/null 2>&1; then
    echo "   Neo4jが起動しました！"
else
    echo "   Neo4jの起動確認中..."
    for i in {1..10}; do
        if docker exec food-composition-japan-2020-8th-neo4j-1 cypher-shell -u neo4j -p demodemo "RETURN 1" >/dev/null 2>&1; then
            echo "   Neo4jが起動しました！"
            break
        fi
        echo -n "."
        sleep 2
    done
fi

# 5. 全サービスの状態確認
echo ""
echo "5. サービス状態確認:"
docker ps | grep food-composition

echo ""
echo "========================================="
echo "リセット完了！"
echo "========================================="
echo ""
echo "MCPサーバーを再接続してください:"
echo "  /mcp reconnect fcj-knowledge"
echo "  /mcp reconnect fcj-search"