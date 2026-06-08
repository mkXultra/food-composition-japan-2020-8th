#!/bin/bash

# Neo4j データベースバックアップスクリプト
# 使用方法: ./backup-neo4j.sh

set -e  # エラーが発生したら停止

# 色付き出力用の設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# バックアップディレクトリ
BACKUP_DIR="./backups"
BACKUP_FILE="neo4j.dump"

echo -e "${GREEN}===================================${NC}"
echo -e "${GREEN} Neo4j Database Backup Script${NC}"
echo -e "${GREEN}===================================${NC}"
echo ""

# バックアップディレクトリの作成
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${YELLOW}Creating backup directory...${NC}"
    mkdir -p "$BACKUP_DIR"
fi

# 1. Neo4jサービスの停止
echo -e "${YELLOW}Step 1: Stopping Neo4j service...${NC}"
docker-compose stop neo4j
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Neo4j service stopped successfully${NC}"
else
    echo -e "${RED}✗ Failed to stop Neo4j service${NC}"
    exit 1
fi
echo ""

# 2. バックアップの実行
echo -e "${YELLOW}Step 2: Creating backup...${NC}"
echo "Backup file: ${BACKUP_FILE}"

# docker-compose-bk.ymlを使用してバックアップ
# タイムスタンプを環境変数として渡す
docker run --rm \
    -v food-composition-japan-2020-8th_neo4j_data:/data \
    -v food-composition-japan-2020-8th_neo4j_logs:/logs \
    -v "$(pwd)/backups":/backups \
    --user "1000:1000" \
    neo4j:5.24 \
    neo4j-admin database dump neo4j --to-path=/backups/

# ダンプファイルの作成を確認
if [ -f "${BACKUP_DIR}/neo4j.dump" ]; then
    echo -e "${GREEN}✓ Backup created successfully${NC}"

    # バックアップファイルのサイズを表示
    BACKUP_SIZE=$(ls -lh "${BACKUP_DIR}/neo4j.dump" | awk '{print $5}')
    echo -e "  File: ${BACKUP_DIR}/neo4j.dump"
    echo -e "  Size: ${BACKUP_SIZE}"
else
    echo -e "${RED}✗ Backup failed - dump file not found${NC}"
    # Neo4jを再起動してから終了
    docker-compose start neo4j
    exit 1
fi
echo ""

# 3. Neo4jサービスの再起動
echo -e "${YELLOW}Step 3: Restarting Neo4j service...${NC}"
docker-compose start neo4j

# Neo4jの起動を確認（最大30秒待機）
echo -e "Waiting for Neo4j to be ready..."
MAX_WAIT=30
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    if docker exec food-composition-japan-2020-8th-neo4j-1 wget -O /dev/null -q http://localhost:7474 2>/dev/null; then
        echo -e "${GREEN}✓ Neo4j service is ready${NC}"
        break
    fi

    echo -n "."
    sleep 1
    COUNTER=$((COUNTER + 1))
done

if [ $COUNTER -eq $MAX_WAIT ]; then
    echo -e "${YELLOW}⚠ Neo4j may not be fully ready yet${NC}"
fi
echo ""

# 4. バックアップファイルの一覧表示
echo -e "${GREEN}===================================${NC}"
echo -e "${GREEN} Backup Complete!${NC}"
echo -e "${GREEN}===================================${NC}"
echo ""
echo "Recent backup files:"
ls -lht "$BACKUP_DIR" | head -6

echo ""
echo -e "${GREEN}Backup process completed successfully!${NC}"

# バックアップファイルのリストア方法を表示
echo ""
echo "To restore this backup, use:"
echo "  docker exec -it food-composition-japan-2020-8th-neo4j-1 neo4j-admin database load neo4j --from-stdin < ${BACKUP_DIR}/neo4j.dump"
