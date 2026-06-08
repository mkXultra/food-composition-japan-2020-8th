#!/bin/bash

# Neo4j Auraへのデータベースアップロードスクリプト
# 使用方法: ./push-to-aura.sh <aura-uri> [dump-file]
# 例: ./push-to-aura.sh xxxxxxxx.databases.neo4j.io
# 例: ./push-to-aura.sh xxxxxxxx.databases.neo4j.io ./backups/neo4j-backup-20241016.dump

set -e

# 色付き出力用の設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# パラメータチェック
if [ $# -lt 1 ]; then
    echo -e "${RED}Usage: $0 <aura-uri> [dump-file]${NC}"
    echo -e "Example: $0 xxxxxxxx.databases.neo4j.io"
    echo -e "Example: $0 xxxxxxxx.databases.neo4j.io ./backups/neo4j-backup-20241016.dump"
    exit 1
fi

AURA_URI=$1
BACKUP_DIR="./backups"

# ダンプファイルの選択
if [ $# -ge 2 ]; then
    DUMP_FILE=$2
    if [ ! -f "$DUMP_FILE" ]; then
        echo -e "${RED}Error: Specified dump file not found: $DUMP_FILE${NC}"
        exit 1
    fi
else
    # デフォルトのダンプファイルを使用
    DUMP_FILE="${BACKUP_DIR}/neo4j.dump"
    if [ ! -f "$DUMP_FILE" ]; then
        echo -e "${RED}Error: No dump file found at ${DUMP_FILE}${NC}"
        echo -e "${YELLOW}Please run ./backup-neo4j.sh first${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}===================================${NC}"
echo -e "${GREEN} Upload to Neo4j Aura${NC}"
echo -e "${GREEN}===================================${NC}"
echo ""
echo -e "${BLUE}Target:${NC} $AURA_URI"
echo -e "${BLUE}Dump file:${NC} $DUMP_FILE"
echo -e "${BLUE}File size:${NC} $(ls -lh $DUMP_FILE | awk '{print $5}')"
echo ""

# 確認プロンプト
echo -e "${YELLOW}Warning: This will OVERWRITE the target database!${NC}"
read -p "Continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Aborted.${NC}"
    exit 1
fi

# Aura認証情報の入力
echo ""
echo -e "${YELLOW}Enter Neo4j Aura credentials:${NC}"
read -p "Username (default: neo4j): " USERNAME
USERNAME=${USERNAME:-neo4j}

read -s -p "Password: " PASSWORD
echo ""

if [ -z "$PASSWORD" ]; then
    echo -e "${RED}Error: Password is required${NC}"
    exit 1
fi

# アップロード実行
echo ""
echo -e "${YELLOW}Uploading database to Aura...${NC}"
echo -e "${YELLOW}This may take several minutes depending on the database size.${NC}"

# ダンプファイルのディレクトリとファイル名を取得
DUMP_DIR=$(dirname "$DUMP_FILE")
DUMP_NAME=$(basename "$DUMP_FILE")

# デバッグ情報を表示
echo -e "${BLUE}Debug info:${NC}"
echo "  - Dump directory: $DUMP_DIR"
echo "  - Dump filename: $DUMP_NAME"
echo "  - Full mount path: $(pwd)/$DUMP_DIR:/dumps"
echo ""

# まずダンプファイルが正しくマウントされているか確認
echo -e "${YELLOW}Checking dump file in container...${NC}"
docker run --rm \
    -v "$(pwd)/$DUMP_DIR":/dumps \
    neo4j:5.25 \
    ls -la /dumps/
echo ""

# URIが完全なBolt URIであることを確認（neo4j+s://プレフィックスが必要）
if [[ ! "$AURA_URI" =~ ^neo4j(\+s)?:// ]]; then
    # プレフィックスがない場合は追加
    FULL_URI="neo4j+s://$AURA_URI"
else
    FULL_URI="$AURA_URI"
fi
echo -e "${BLUE}Using URI: ${FULL_URI}${NC}"
echo ""

docker run --rm -it \
    -v "$(pwd)/$DUMP_DIR":/dumps \
    neo4j:5.25 \
    neo4j-admin database upload neo4j \
    --from-path=/dumps \
    --to-uri="$FULL_URI" \
    --to-user="$USERNAME" \
    --to-password="$PASSWORD" \
    --overwrite-destination=true \
    --verbose

UPLOAD_RESULT=$?

# 結果表示
if [ $UPLOAD_RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}===================================${NC}"
    echo -e "${GREEN} Upload Completed Successfully!${NC}"
    echo -e "${GREEN}===================================${NC}"
    echo ""
    echo -e "Your database has been uploaded to:"
    echo -e "  ${BLUE}$AURA_URI${NC}"
    echo ""
    echo -e "You can now connect to your Aura instance using:"
    echo -e "  - Neo4j Browser: ${BLUE}https://browser.neo4j.io${NC}"
    echo -e "  - Connection URI: ${BLUE}neo4j+s://$AURA_URI${NC}"
    echo -e "  - Username: ${BLUE}$USERNAME${NC}"
else
    echo ""
    echo -e "${RED}Upload failed!${NC}"
    echo -e "Please check your credentials and network connection."
    exit 1
fi
