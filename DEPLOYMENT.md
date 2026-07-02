# Steel Industry AI Assistant - 部署文档

## 一、环境要求

### 1.1 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4核 | 8核以上 |
| 内存 | 16GB | 32GB以上 |
| 磁盘 | 100GB | 500GB以上 |
| 网络 | 100Mbps | 1Gbps |

### 1.2 软件要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Docker | 20.10+ | 容器运行时 |
| Docker Compose | 2.26+ | 容器编排 |
| Python | 3.11 | 后端开发环境（可选） |
| Node.js | 18+ | 前端开发环境（可选） |

---

## 二、快速开始

### 2.1 克隆项目

```bash
git clone <repository-url>
cd Steel-Industry-Agent
```

### 2.2 配置环境变量

复制 `.env.example` 文件并修改配置：

```bash
cp backend/.env.example backend/.env
```

编辑 `backend/.env`：

```bash
# ==================== MySQL 配置 ====================
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=@Maxwell@2024
MYSQL_DB=steel_agent

# ==================== PostgreSQL/pgvector 配置 ====================
PG_HOST=postgres
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=postgres
PG_DB=steel_agent_vector

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ========== 大模型配置 ==========
# Xinference 模型服务
XINFERENCE_BASE_URL=http://172.1.2.198:9997
XINFERENCE_EMBED_MODEL=bge-m3
XINFERENCE_RERANK_MODEL=bge-reranker-large
RERANK_TOP_K=5

# NewAPI LLM 服务
NEWAPI_BASE_URL=http://172.1.8.152:3000/v1
NEWAPI_API_KEY=sk-o1rZGfMqwI5Vbcu3OkeeFb7UOlxHEdp1GC1FxZ4aM2B8sOj1
NEWAPI_MODEL=glm-5.1-fp8
LLM_MAX_TOKENS=20480
LLM_TEMPERATURE=0.7

# ========== JWT配置 ==========
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ========== 应用配置 ==========
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=104857600
```

### 2.3 使用Docker Compose启动

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

### 2.4 访问系统

- **前端地址**：http://localhost:8080
- **后端API**：http://localhost:8000
- **健康检查**：http://localhost:8000/api/v1/health

### 2.5 默认账号

- **用户名**：admin
- **密码**：admin
- **首次登录**：强制修改密码

---

## 三、本地开发环境启动

### 3.1 环境准备

#### 3.1.1 安装后端依赖

```bash
cd backend

# 使用pip安装
python -m pip install -r requirements.txt

# 或使用Poetry（推荐）
poetry install
```

#### 3.1.2 安装前端依赖

```bash
cd frontend
pnpm install
```

#### 3.1.3 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，修改数据库连接配置为本地数据库：

```bash
# ==================== MySQL 配置 ====================
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=@Maxwell@2024
MYSQL_DB=steel_agent

# ==================== PostgreSQL/pgvector 配置 ====================
PG_HOST=postgres
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=postgres
PG_DB=steel_agent_vector

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

> **注意**：`PG_HOST=postgres` 适用于 Docker Compose 网络环境，本地开发时如果 PostgreSQL 运行在本机，请改为 `PG_HOST=localhost`。

### 3.2 数据库初始化

#### 3.2.1 MySQL数据库初始化

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS steel_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（可选）
CREATE USER 'steel_agent'@'%' IDENTIFIED BY 'steelagent@2024';
GRANT ALL PRIVILEGES ON steel_agent.* TO 'steel_agent'@'%';
FLUSH PRIVILEGES;
```

#### 3.2.2 PostgreSQL数据库初始化

```sql
-- 创建数据库
CREATE DATABASE steel_agent_vector;

-- 进入数据库
\c steel_agent_vector;

-- 安装pgvector扩展（向量索引必需）
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建用户（可选）
CREATE USER steel_agent WITH PASSWORD 'steelagent@2024';
GRANT ALL PRIVILEGES ON DATABASE steel_agent_vector TO steel_agent;
```

#### 3.2.3 使用Docker Compose启动数据库（推荐）

```bash
# 仅启动数据库服务（后台运行）
docker-compose up -d mysql postgres redis

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f mysql postgres
```

### 3.3 启动服务

#### 3.3.1 启动后端服务

```bash
cd backend

# 方式一：使用uvicorn（推荐）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 方式二：使用python直接运行
python main.py

# 方式三：使用Poetry
poetry run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 3.3.2 启动前端服务

```bash
cd frontend

# 开发模式（热更新）
pnpm dev

# 生产模式构建
pnpm build

# 预览生产构建
pnpm preview
```

### 3.4 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:5173 | 开发模式 |
| 前端 | http://localhost:8080 | 生产模式 |
| 后端API | http://localhost:8000 | FastAPI服务 |
| Swagger文档 | http://localhost:8000/docs | API文档 |
| Redoc文档 | http://localhost:8000/redoc | API文档 |
| 健康检查 | http://localhost:8000/api/v1/health | 健康检查 |

### 3.5 数据库初始化机制

系统启动时会自动执行以下初始化：

#### 3.5.1 表结构自动创建

后端服务启动时，SQLAlchemy会根据 `app/models/` 目录下的所有模型定义，自动创建对应的数据库表。

```python
# backend/app/core/database.py
async def init_db() -> None:
    async with mysql_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

#### 3.5.2 默认管理员自动创建

系统会自动创建默认管理员账号（admin/admin），首次登录强制修改密码。

```python
# backend/app/services/auth_service.py
async def init_default_admin(db: AsyncSession) -> None:
    existing = await AuthService.get_user_by_username(db, "admin")
    if existing:
        return
    admin = User(
        username="admin",
        password_hash=hash_password("admin"),
        role="admin",
        force_change_password=True,
    )
    db.add(admin)
    await db.commit()
```

#### 3.5.3 初始化触发时机

在 `main.py` 的 `lifespan` 上下文管理器中：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()  # 初始化数据库表结构
    
    from app.services.auth_service import auth_service
    from app.core.database import MySQLAsyncSession
    async with MySQLAsyncSession() as db:
        await auth_service.init_default_admin(db)  # 创建默认admin用户
    
    logger.success("系统启动成功!")
    yield
```

### 3.6 启动流程图

```
启动命令 → main.py → lifespan()
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
      init_db()              init_default_admin()
            │                         │
   ┌────────┴────────┐        创建admin用户
   ▼                 ▼        (admin/admin)
MySQL表结构     PostgreSQL
自动创建        连接测试
```

---

## 四、Docker Compose配置说明

### 3.1 服务组件

| 服务名称 | 镜像 | 端口 | 说明 |
|---------|------|------|------|
| mysql | mysql:8.0 | 3306 | 业务数据库（用户、会话、配置等） |
| postgres | pgvector/pgvector:pg16 | 5432 | 向量数据库（文档向量索引） |
| redis | redis:7-alpine | 6379 | 缓存（会话、配置缓存） |
| backend | 自定义构建 | 8000 | FastAPI后端服务 |
| frontend | 自定义构建 | 8080 | Vue.js前端应用 |

### 3.2 环境变量说明

#### 数据库相关

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| MYSQL_HOST | mysql | MySQL主机地址 |
| MYSQL_PORT | 3306 | MySQL端口 |
| MYSQL_USER | root | MySQL用户名 |
| MYSQL_PASSWORD | steelagent@2024 | MySQL密码 |
| MYSQL_DB | steel_agent | MySQL数据库名 |
| PG_HOST | postgres | PostgreSQL主机地址 |
| PG_PORT | 5432 | PostgreSQL端口 |
| PG_USER | postgres | PostgreSQL用户名 |
| PG_PASSWORD | steelagent@2024 | PostgreSQL密码 |
| PG_DB | steel_agent_vector | PostgreSQL数据库名 |
| REDIS_HOST | redis | Redis主机地址 |
| REDIS_PORT | 6379 | Redis端口 |

#### 大模型相关

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| XINFERENCE_BASE_URL | http://172.1.2.198:9997 | Xinference服务地址 |
| XINFERENCE_EMBED_MODEL | bge-m3 | 嵌入模型名称 |
| XINFERENCE_RERANK_MODEL | bge-reranker-large | 重排模型名称 |
| NEWAPI_BASE_URL | http://172.1.8.152:3000/v1 | NewAPI服务地址 |
| NEWAPI_API_KEY | - | API密钥 |
| NEWAPI_MODEL | glm-5.1-fp8 | 对话模型名称 |
| LLM_MAX_TOKENS | 20480 | 最大输出Token数 |
| LLM_TEMPERATURE | 0.7 | 温度参数 |

#### 应用相关

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| JWT_SECRET_KEY | your-secret-key | JWT密钥 |
| APP_HOST | 0.0.0.0 | 服务绑定地址 |
| APP_PORT | 8000 | 服务端口 |
| DEBUG | false | 调试模式 |
| UPLOAD_DIR | ./uploads | 文件上传目录 |

### 3.3 数据卷

| 数据卷名称 | 用途 | 说明 |
|-----------|------|------|
| mysql_data | MySQL数据持久化 | 存储业务数据 |
| pg_data | PostgreSQL数据持久化 | 存储向量数据 |
| redis_data | Redis数据持久化 | 存储缓存数据 |
| uploads_data | 文档上传持久化 | 存储上传的知识库文档 |

---

## 四、Oracle数据库支持

### 4.1 依赖安装

Oracle数据库连接需要安装 `oracledb` 库：

```bash
pip install oracledb
```

### 4.2 Oracle客户端配置

#### 方式一：使用thin模式（推荐）

无需安装Oracle Instant Client，使用纯Python实现：

```python
import oracledb

# 直接使用thin模式连接
connection = oracledb.connect(
    user="username",
    password="password",
    dsn="host:port/service_name"
)
```

#### 方式二：使用Oracle Instant Client

1. 下载Oracle Instant Client：
   - 地址：https://www.oracle.com/database/technologies/instant-client.html
   - 选择对应平台的Basic或Basic Light版本

2. 配置环境变量：
   ```bash
   # Linux
   export LD_LIBRARY_PATH=/path/to/instantclient:$LD_LIBRARY_PATH

   # Windows
   set PATH=C:\path\to\instantclient;%PATH%
   ```

3. 初始化客户端：
   ```python
   import oracledb
   oracledb.init_oracle_client()
   ```

### 4.3 Schema同步说明

Oracle数据库的Schema同步通过以下视图获取表结构信息：

| 视图名称 | 用途 |
|---------|------|
| all_tables | 获取当前用户可访问的所有表 |
| all_tab_columns | 获取表的列信息 |
| all_tab_comments | 获取表注释 |

### 5.4 添加Oracle数据源

在前端数据管理页面添加Oracle数据源：

1. **类型**：选择 `Oracle`
2. **主机**：Oracle数据库主机地址
3. **端口**：默认 `1521`
4. **数据库**：Oracle服务名（如 `ORCL` 或 `XE`）
5. **用户名**：Oracle用户名
6. **密码**：Oracle密码

---

## 五、健康检查

### 5.1 API接口

| 接口路径 | 方法 | 说明 |
|---------|------|------|
| /api/v1/health | GET | 综合健康检查 |
| /api/v1/health/ready | GET | 就绪检查（K8s就绪探针） |
| /api/v1/health/live | GET | 存活检查（K8s存活探针） |

### 5.2 响应示例

```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "1.0.0",
    "checks": {
        "service": {"status": "healthy", "message": "Steel Industry AI Assistant"},
        "database": {"status": "healthy", "message": "MySQL连接正常"},
        "redis": {"status": "healthy", "message": "Redis连接正常"},
        "postgres": {"status": "healthy", "message": "PostgreSQL连接正常"}
    }
}
```

---

## 六、常见问题

### 6.1 Docker网络问题

**现象**：容器之间无法通信

**解决方法**：
```bash
# 检查网络配置
docker network ls
docker network inspect steel-agent-net

# 重启网络
docker-compose down
docker network rm steel-agent-net
docker-compose up -d
```

### 6.2 数据库连接失败

**现象**：后端服务启动后无法连接数据库

**解决方法**：
1. 检查环境变量配置是否正确
2. 检查数据库服务是否正常启动
3. 检查防火墙规则是否允许访问
4. 查看容器日志：`docker-compose logs -f backend`

### 6.3 Oracle连接问题

**现象**：Oracle数据源测试连接失败

**解决方法**：
1. 确认Oracle服务是否正常运行
2. 确认Oracle监听是否启动：`lsnrctl status`
3. 确认网络可访问性：`telnet host 1521`
4. 确认用户名密码正确
5. 确认服务名配置正确（使用 `tnsping` 测试）

### 6.4 大模型服务连接问题

**现象**：无法连接Xinference或NewAPI服务

**解决方法**：
1. 确认大模型服务是否正常运行
2. 确认网络可访问性
3. 确认API密钥配置正确
4. 测试API连通性：
   ```bash
   curl http://172.1.2.198:9997/v1/models
   curl http://172.1.8.152:3000/v1/models
   ```

---

## 七、安全建议

### 7.1 生产环境配置

1. **修改默认密码**：
   - 修改MySQL root密码
   - 修改PostgreSQL密码
   - 修改admin用户密码

2. **修改JWT密钥**：
   ```bash
   # 生成随机密钥
   openssl rand -hex 32
   ```

3. **启用HTTPS**：
   - 使用Nginx反向代理
   - 配置SSL证书

4. **限制网络访问**：
   - 仅允许内网访问数据库端口
   - 配置防火墙规则

### 7.2 数据安全

1. **定期备份**：
   ```bash
   # MySQL备份
   docker exec steel-agent-mysql mysqldump -u root -p steel_agent > backup.sql

   # PostgreSQL备份
   docker exec steel-agent-postgres pg_dump steel_agent_vector > backup.sql
   ```

2. **敏感数据加密**：
   - 数据库密码使用环境变量
   - API密钥使用环境变量
   - 避免硬编码敏感信息

---

## 八、技术支持

如需技术支持，请提供以下信息：

1. 系统版本
2. Docker Compose版本
3. 相关日志（`docker-compose logs`）
4. 问题描述和复现步骤
5. 网络拓扑和环境配置

---

## 九、版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2024-01-15 | 初始版本，支持RAG知识问答、ChatBI智能问数、Oracle数据源 |
