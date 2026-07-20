#!/bin/bash
set -e

echo "初始化 PostgreSQL 数据库..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE steel_agent_vector;
    \c steel_agent_vector;
    CREATE EXTENSION IF NOT EXISTS vector;
    \c steel_agent;
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "PostgreSQL 数据库初始化完成"
