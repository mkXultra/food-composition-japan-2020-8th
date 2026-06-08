#!/bin/bash

# Reset Neo4j database while keeping other services running
echo "Resetting Neo4j database..."

# Stop Neo4j container
echo "Stopping Neo4j container..."
docker stop food-composition-japan-2020-8th-neo4j-1

# Remove Neo4j container
echo "Removing Neo4j container..."
docker rm food-composition-japan-2020-8th-neo4j-1

# Remove Neo4j volumes
echo "Removing Neo4j volumes..."
docker volume rm food-composition-japan-2020-8th_neo4j_data food-composition-japan-2020-8th_neo4j_logs

# Start Neo4j container only
echo "Starting Neo4j container..."
docker compose up neo4j -d

echo "Neo4j database has been reset successfully!"
echo "Other services (fcj-knowledge, mcp-neo4j-cypher-server) remain running."