# Industrial Intelligent Assistant Platform - 部署文档

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
| pnpm | 8+ | 前端包管理器 |

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
# ==================== PostgreSQL 配置（系统数据库 + 向量数据库） ====================
PG_HOST=postgres
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=steelagent@2024
PG_DB=steel_agent

# ==================== MySQL 配置（业务数据库，钢铁生产数据） ====================
BUSINESS_DB_HOST=mysql
BUSINESS_DB_PORT=3306
BUSINESS_DB_USER=root
BUSINESS_DB_PASSWORD=steelagent@2024
BUSINESS_DB_NAME=steel_test

# ==================== Redis配置 ====================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# ========== Xinference 大模型配置 ==========
XINFERENCE_BASE_URL=http://your-xinference-host:9997
XINFERENCE_EMBED_MODEL=bge-m3
XINFERENCE_RERANK_MODEL=bge-reranker-large
XINFERENCE_LLM_MODEL=qwen3
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
UPLOAD_DIR=./storage/documents
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

---

## 三、本地开发环境启动

### 3.1 环境准备

#### 3.1.1 安装后端依赖

```bash
cd backend

# 使用pip安装
python -m pip install -r requirements.txt
```

核心依赖说明：

| 库 | 版本 | 说明 |
|----|------|------|
| fastapi | >=0.111.0 | Web框架 |
| sqlalchemy[asyncio] | >=2.0.30 | ORM框架 |
| asyncpg | >=0.29.0 | PostgreSQL异步驱动 |
| aiomysql | >=0.2.0 | MySQL异步驱动 |
| llama-index | - | RAG框架 |
| llama-index-vector-stores-postgres | - | pgvector向量存储 |
| llama-index-embeddings-huggingface | - | HuggingFace嵌入模型 |
| llama-index-readers-file | - | 文档读取器 |
| pypdf | >=4.0.0 | PDF解析 |
| python-docx | >=1.1.0 | Word文档解析 |
| redis[hiredis] | >=5.0.0 | Redis缓存 |
| loguru | >=0.7.2 | 日志管理 |

#### 3.1.2 安装前端依赖

```bash
cd frontend
pnpm install
```

核心依赖说明：

| 库 | 版本 | 说明 |
|----|------|------|
| vue | ^3.4.0 | 前端框架 |
| vue-router | ^4.3.0 | 路由管理 |
| pinia | ^2.2.0 | 状态管理 |
| element-plus | ^2.8.0 | UI组件库 |
| @element-plus/icons-vue | ^2.3.0 | Element Plus图标 |
| echarts | ^5.5.0 | 数据可视化图表 |
| vue-echarts | ^7.0.0 | ECharts Vue封装 |
| axios | ^1.6.0 | HTTP客户端 |
| marked | ^12.0.0 | Markdown解析 |
| highlight.js | ^11.9.0 | 代码高亮 |
| xlsx | ^0.18.5 | Excel导入导出 |
| file-saver | ^2.0.5 | 文件下载 |
| vueuse | ^10.0.0 | Vue工具库 |

开发依赖：

| 库 | 版本 | 说明 |
|----|------|------|
| vite | ^5.4.0 | 构建工具 |
| typescript | ^5.3.0 | TypeScript支持 |
| sass | ^1.70.0 | CSS预处理 |
| eslint | ^8.56.0 | 代码检查 |
| prettier | ^3.2.0 | 代码格式化 |

#### 3.1.3 配置环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，修改数据库连接配置为本地数据库：

```bash
# ==================== PostgreSQL 配置（系统数据库 + 向量数据库） ====================
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your-password
PG_DB=steel_agent

# ==================== MySQL 配置（业务数据库） ====================
BUSINESS_DB_HOST=localhost
BUSINESS_DB_PORT=3306
BUSINESS_DB_USER=root
BUSINESS_DB_PASSWORD=your-password
BUSINESS_DB_NAME=steel_test

# ==================== Redis配置 ====================
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ==================== Xinference配置 ====================
XINFERENCE_BASE_URL=http://your-xinference-host:9997
XINFERENCE_EMBED_MODEL=bge-m3
XINFERENCE_RERANK_MODEL=bge-reranker-large
XINFERENCE_LLM_MODEL=qwen3
```

> **注意**：`PG_HOST=postgres` 适用于 Docker Compose 网络环境，本地开发时如果 PostgreSQL 运行在本机，请改为 `PG_HOST=localhost`。

### 3.2 数据库初始化

#### 3.2.1 PostgreSQL数据库初始化（系统库 + 向量库）

```sql
-- 创建数据库
CREATE DATABASE steel_agent;

-- 进入数据库
\c steel_agent;

-- 安装pgvector扩展（向量索引必需）
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建用户（可选）
CREATE USER steel_agent WITH PASSWORD 'steelagent@2024';
GRANT ALL PRIVILEGES ON DATABASE steel_agent TO steel_agent;
```

#### 3.2.2 MySQL数据库初始化（业务数据库）

```sql
-- 创建数据库
CREATE DATABASE IF NOT EXISTS steel_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建用户（可选）
CREATE USER 'steel_agent'@'%' IDENTIFIED BY 'steelagent@2024';
GRANT ALL PRIVILEGES ON steel_test.* TO 'steel_agent'@'%';
FLUSH PRIVILEGES;
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

# 使用uvicorn（推荐）
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
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

# 代码检查
pnpm lint

# 代码格式化
pnpm format
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
| 登录页 | http://localhost:5173/login | 用户登录 |
| 应用管理 | http://localhost:5173/app-management | 登录后默认跳转 |

### 3.5 数据库初始化机制

系统启动时会自动执行以下初始化：

#### 3.5.1 表结构自动创建

后端服务启动时，SQLAlchemy会根据 `app/models/` 目录下的所有模型定义，自动创建对应的数据库表。

```python
# backend/app/core/database.py
async def init_db() -> None:
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

#### 3.5.2 默认管理员自动创建

系统会自动创建默认管理员账号（admin/admin）。

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
    from app.core.database import get_session
    async with get_session() as db:
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
PostgreSQL表结构    业务数据库
自动创建            连接测试
(系统库+向量库)
```

---

## 四、Docker Compose配置说明

### 4.1 服务组件

| 服务名称 | 镜像 | 端口 | 说明 |
|---------|------|------|------|
| mysql | mysql:8.0 | 3306 | 业务数据库（钢铁生产数据） |
| postgres | pgvector/pgvector:pg16 | 5432 | 系统数据库 + 向量数据库（用户、会话、配置、文档向量索引） |
| redis | redis:7-alpine | 6379 | 缓存（会话、配置缓存） |
| backend | 自定义构建 | 8000 | FastAPI后端服务 |
| frontend | 自定义构建 | 8080 | Vue.js前端应用 |

### 4.2 环境变量说明

#### 数据库相关

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| PG_HOST | postgres | PostgreSQL主机地址（系统库+向量库） |
| PG_PORT | 5432 | PostgreSQL端口 |
| PG_USER | postgres | PostgreSQL用户名 |
| PG_PASSWORD | steelagent@2024 | PostgreSQL密码 |
| PG_DB | steel_agent | PostgreSQL数据库名 |
| BUSINESS_DB_HOST | mysql | MySQL主机地址（业务数据库） |
| BUSINESS_DB_PORT | 3306 | MySQL端口 |
| BUSINESS_DB_USER | root | MySQL用户名 |
| BUSINESS_DB_PASSWORD | steelagent@2024 | MySQL密码 |
| BUSINESS_DB_NAME | steel_test | MySQL数据库名 |
| REDIS_HOST | redis | Redis主机地址 |
| REDIS_PORT | 6379 | Redis端口 |

#### 大模型相关（Xinference）

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| XINFERENCE_BASE_URL | http://your-xinference-host:9997 | Xinference服务地址 |
| XINFERENCE_EMBED_MODEL | bge-m3 | 嵌入模型名称（向量检索） |
| XINFERENCE_RERANK_MODEL | bge-reranker-large | 重排模型名称（Rerank） |
| XINFERENCE_LLM_MODEL | qwen3 | 对话模型名称（LLM） |
| LLM_MAX_TOKENS | 20480 | 最大输出Token数 |
| LLM_TEMPERATURE | 0.7 | 温度参数 |

#### 应用相关

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| JWT_SECRET_KEY | your-secret-key | JWT密钥 |
| APP_HOST | 0.0.0.0 | 服务绑定地址 |
| APP_PORT | 8000 | 服务端口 |
| DEBUG | false | 调试模式 |
| UPLOAD_DIR | ./storage/documents | 文件上传目录 |

### 4.3 数据卷

| 数据卷名称 | 用途 | 说明 |
|-----------|------|------|
| mysql_data | MySQL数据持久化 | 存储业务数据（钢铁生产数据） |
| pg_data | PostgreSQL数据持久化 | 存储系统数据和向量数据 |
| redis_data | Redis数据持久化 | 存储缓存数据 |
| uploads_data | 文档上传持久化 | 存储上传的知识库文档 |

---

## 五、Oracle数据库支持

### 5.1 依赖安装

Oracle数据库连接需要安装 `oracledb` 库：

```bash
pip install oracledb
```

### 5.2 Oracle客户端配置

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

### 5.3 Schema同步说明

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

## 六、功能模块说明

### 6.1 应用管理

应用管理模块支持以下功能：

- 应用创建/编辑/删除
- 模型配置（大语言模型、向量模型、重排模型）
- 提示词管理
- 关联知识库
- 开场白配置
- 应用分享与嵌入

#### 6.1.1 嵌入模式（页面嵌入）

在应用管理页面点击"页面嵌入"，可获取嵌入代码。支持两种嵌入模式：

**嵌入模式**：通过 iframe 嵌入完整的对话界面

```html
<script async defer src="http://your-host:port/chat-embed.js?token=YOUR_TOKEN"></script>
```

**浮窗模式**：页面右下角悬浮助手图标，点击展开对话窗口

```html
<script async defer src="http://your-host:port/chat-embed.js?token=YOUR_TOKEN&mode=floating"></script>
```

浮窗模式特点：
- 机器人图标显示在页面右下角
- 点击图标展开对话窗口（50%视口宽度）
- 支持最小化、展开/全屏、关闭等操作
- 窗口关闭后图标自动恢复
- 支持 SSE 流式输出
- 支持知识检索和智能问数

#### 6.1.2 API密钥管理

每个应用可生成独立的 API 密钥，用于嵌入集成和 API 调用。

### 6.2 知识管理

- 文档上传与解析（PDF、Word、TXT）
- 文本切片与向量索引
- 知识库检索与问答
- 相似度分数显示

### 6.3 数据管理

- 多数据源支持（MySQL、PostgreSQL、Oracle、SQL Server）
- Schema 同步与字段结构展示
- 字段注释（中文）展示
- 数据预览

### 6.4 数据可视化

- 默认图表视图
- 表格视图切换
- 数据导出（Excel）
- 全屏查看

---

## 七、健康检查

### 7.1 API接口

| 接口路径 | 方法 | 说明 |
|---------|------|------|
| /api/v1/health | GET | 综合健康检查 |
| /api/v1/health/ready | GET | 就绪检查（K8s就绪探针） |
| /api/v1/health/live | GET | 存活检查（K8s存活探针） |

### 7.2 响应示例

```json
{
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "1.0.0",
    "checks": {
        "service": {"status": "healthy", "message": "Industrial Intelligent Assistant Platform"},
        "database": {"status": "healthy", "message": "PostgreSQL连接正常"},
        "business_database": {"status": "healthy", "message": "MySQL连接正常"},
        "redis": {"status": "healthy", "message": "Redis连接正常"}
    }
}
```

---

## 八、测试与工具脚本

### 8.1 脚本目录

所有测试脚本和工具脚本已统一存放至 `backend/tests/` 目录。这些脚本不参与业务运行，已被 `.gitignore` 排除。

详细脚本清单请参考 [backend/tests/README.md](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/backend/tests/README.md)

### 8.2 脚本分类

| 分类 | 数量 | 说明 |
|------|------|------|
| 测试 | 14 | 接口测试、功能测试、流程测试 |
| 检查 | 5 | 数据库状态检查、数据检查 |
| 分析 | 1 | Schema分析工具 |
| 调试 | 1 | pgvector调试工具 |
| 修复 | 1 | PostgreSQL序列修复 |
| 清理 | 1 | 重复数据源清理 |
| 迁移 | 7 | 数据库字段迁移、表结构迁移 |

### 8.3 运行测试脚本

```bash
# 进入tests目录
cd backend/tests

# 运行测试脚本
python test_login.py
python test_stream_chat.py

# 运行迁移脚本（注意：迁移前请备份数据库）
python migrate_add_user_fields.py
```

### 8.4 注意事项

- 运行迁移脚本前必须备份数据库
- 迁移脚本会自动连接 `.env` 配置的数据库
- 检查/分析脚本为只读操作，不会修改数据

---

## 九、常见问题

### 9.1 Docker网络问题

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

### 9.2 数据库连接失败

**现象**：后端服务启动后无法连接数据库

**解决方法**：
1. 检查环境变量配置是否正确
2. 检查数据库服务是否正常启动
3. 检查防火墙规则是否允许访问
4. 查看容器日志：`docker-compose logs -f backend`

### 9.3 Oracle连接问题

**现象**：Oracle数据源测试连接失败

**解决方法**：
1. 确认Oracle服务是否正常运行
2. 确认Oracle监听是否启动：`lsnrctl status`
3. 确认网络可访问性：`telnet host 1521`
4. 确认用户名密码正确
5. 确认服务名配置正确（使用 `tnsping` 测试）

### 9.4 Xinference模型服务连接问题

**现象**：无法连接Xinference服务

**解决方法**：
1. 确认Xinference服务是否正常运行
2. 确认网络可访问性
3. 确认模型名称配置正确
4. 测试API连通性：
   ```bash
   curl http://your-xinference-host:9997/v1/models
   ```

### 9.5 psycopg2模块未找到

**现象**：向量检索失败，报错 `No module named 'psycopg2'`

**解决方法**：
```bash
pip install psycopg2-binary
```

### 9.6 重复键违反唯一约束

**现象**：插入数据时报错 `UniqueViolationError: 重复键违反唯一约束`

**解决方法**：
这是由于PostgreSQL序列值与现有数据ID不一致导致的，需要重置序列：

```sql
-- 查看当前序列值
SELECT nextval('messages_id_seq');

-- 重置序列到最大ID+1
SELECT setval('messages_id_seq', (SELECT MAX(id) FROM messages) + 1);
```

### 9.7 登录后跳转页面

**说明**：用户登录成功后默认跳转到 `/app-management`（应用管理页面），而非智能对话页面。

如需修改跳转路径，请编辑 `frontend/src/views/LoginView.vue` 中的 `defaultRedirect` 变量。

### 9.8 前端路由切换空白

**说明**：已在路由配置中添加 `:key="$route.fullPath"` 强制组件重新渲染，避免页面切换时的空白问题。

### 9.9 流式输出自动滚动

**说明**：所有对话窗口支持流式输出时自动滚动到底部。当用户主动向上滚动查看历史时，自动滚动会暂停；当用户滚回底部时，自动滚动恢复。

---

## 十、安全建议

### 10.1 生产环境配置

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

### 10.2 数据安全

1. **定期备份**：
   ```bash
   # PostgreSQL备份（系统库+向量库）
   docker exec steel-agent-postgres pg_dump steel_agent > backup_pg.sql

   # MySQL备份（业务库）
   docker exec steel-agent-mysql mysqldump -u root -p steel_test > backup_mysql.sql
   ```

2. **敏感数据加密**：
   - 数据库密码使用环境变量
   - API密钥使用环境变量
   - 避免硬编码敏感信息

---

## 十一、项目结构

```
Steel-Industry-Agent/
├── backend/                          # 后端代码
│   ├── app/
│   │   ├── api/v1/                   # API路由
│   │   │   ├── auth.py              # 认证接口
│   │   │   ├── chat.py              # 对话接口
│   │   │   ├── chatbi.py            # ChatBI接口
│   │   │   ├── knowledge.py         # 知识库接口
│   │   │   ├── datasource.py        # 数据源接口
│   │   │   ├── application.py       # 应用管理接口
│   │   │   ├── llm_config.py        # 模型配置接口
│   │   │   ├── audit_log.py         # 审计日志接口
│   │   │   └── ...
│   │   ├── core/                     # 核心模块
│   │   │   ├── database.py          # 数据库连接
│   │   │   ├── config.py            # 配置管理
│   │   │   ├── llm_client.py        # LLM客户端
│   │   │   └── redis_client.py      # Redis客户端
│   │   ├── models/                   # 数据模型
│   │   │   ├── user.py              # 用户模型
│   │   │   ├── session.py           # 会话模型
│   │   │   ├── application.py       # 应用模型
│   │   │   ├── knowledge.py         # 知识库模型
│   │   │   ├── datasource.py        # 数据源模型
│   │   │   └── ...
│   │   ├── schemas/                  # Pydantic Schema
│   │   ├── services/                 # 业务服务
│   │   │   ├── auth_service.py      # 认证服务
│   │   │   ├── router_service.py    # 意图路由服务
│   │   │   ├── chatbi_service.py    # ChatBI服务
│   │   │   ├── knowledge_service.py # 知识库服务
│   │   │   ├── vector_service.py    # 向量服务
│   │   │   └── ...
│   │   ├── middlewares/              # 中间件
│   │   └── utils/                    # 工具函数
│   ├── tests/                        # 测试与工具脚本（已加入.gitignore）
│   │   ├── test_*.py               # 测试脚本
│   │   ├── check_*.py              # 检查脚本
│   │   ├── migrate_*.py            # 迁移脚本
│   │   └── README.md               # 脚本清单说明
│   ├── main.py                       # 应用入口
│   ├── requirements.txt              # Python依赖
│   └── Dockerfile                    # Docker配置
├── frontend/                        # 前端代码
│   ├── src/
│   │   ├── views/                    # 页面
│   │   │   ├── LoginView.vue        # 登录页
│   │   │   ├── AppListView.vue      # 应用管理页
│   │   │   ├── ChatView.vue         # 智能对话页
│   │   │   ├── ChatEmbedView.vue    # 嵌入对话页
│   │   │   ├── KnowledgeView.vue    # 知识管理页
│   │   │   ├── DataConfigView.vue   # 数据管理页
│   │   │   ├── ModelConfigView.vue  # 模型配置页
│   │   │   ├── AuditLogView.vue     # 审计日志页
│   │   │   └── ...
│   │   ├── components/               # 组件
│   │   │   ├── layout/              # 布局组件
│   │   │   │   ├── MainLayout.vue
│   │   │   │   ├── Header.vue
│   │   │   │   └── Sidebar.vue
│   │   │   ├── chat/                # 对话组件
│   │   │   │   ├── ChatPanel.vue
│   │   │   │   └── ChatMessage.vue
│   │   │   └── chart/               # 图表组件
│   │   │       ├── ChartCard.vue
│   │   │       └── DataTable.vue
│   │   ├── stores/                   # Pinia状态管理
│   │   ├── router/                   # 路由配置
│   │   └── assets/                   # 静态资源
│   │       ├── login-logo-dark.png
│   │       ├── company-logo-dark.png
│   │       └── company-logo-light.png
│   ├── chat-embed.js                 # 嵌入脚本（浮窗/嵌入模式）
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml               # Docker编排配置
├── .gitignore                       # Git忽略规则
└── DEPLOYMENT.md                    # 本文档
```

---

## 十二、技术支持

如需技术支持，请提供以下信息：

1. 系统版本
2. Docker Compose版本
3. 相关日志（`docker-compose logs`）
4. 问题描述和复现步骤
5. 网络拓扑和环境配置

---

## 十三、版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 1.0.0 | 2024-01-15 | 初始版本，支持RAG知识问答、ChatBI智能问数、Oracle数据源 |
| 1.1.0 | 2024-01-20 | 架构优化：PostgreSQL统一作为系统库+向量库，MySQL作为业务数据库；迁移至Xinference统一模型服务 |
| 1.1.1 | 2024-01-25 | 代码注释增强：为所有服务类、模型类添加详细文档注释；日志增强：关键业务流程添加INFO/DEBUG级别日志；文档更新 |
| 1.2.0 | 2024-02-01 | 新增应用管理模块：支持应用创建/编辑/删除、模型设置、提示词管理、关联知识库、开场白配置；支持嵌入集成（全屏模式），生成嵌入代码和API密钥管理 |
| 1.3.0 | 2024-08-03 | 新增浮窗助手模式；优化流式输出自动滚动；测试脚本统一整理至 backend/tests/；登录后默认跳转应用管理页；前端依赖更新（ECharts、Element Plus等）；数据可视化交互优化 |

---

## 十四、代码注释与日志说明

### 14.1 代码注释规范

项目已为所有核心文件添加详细注释，便于新手理解代码逻辑：

#### 后端服务层注释（app/services/）
- **模块文档字符串**：说明模块功能、数据关系、处理流程
- **类注释**：说明类的功能、核心属性、使用场景
- **方法注释**：使用 `:param`、`:return`、`:raises` 格式说明参数、返回值和异常

#### 数据库模型注释（app/models/）
- **模块文档字符串**：说明模型关系、处理流程、注意事项
- **类注释**：说明表的用途和核心字段
- **字段注释**：通过 `comment` 参数说明每个字段的含义

#### 示例文件
- [vector_service.py](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/backend/app/services/vector_service.py)：RAG向量检索服务
- [router_service.py](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/backend/app/services/router_service.py)：意图识别与路由分发服务
- [nl2sql_service.py](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/backend/app/services/nl2sql_service.py)：NL2SQL兜底引擎
- [session.py](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/backend/app/models/session.py)：会话与消息模型

### 14.2 日志说明

项目使用 loguru 进行日志管理，日志级别和用途如下：

| 级别 | 用途 | 示例 |
|------|------|------|
| **INFO** | 关键业务流程记录 | "意图分类结果: knowledge"、"SQL执行完成，耗时: 120ms" |
| **DEBUG** | 详细调试信息 | "图表类型匹配: 问题=xxx, 类型=bar"、"术语搜索完成: keyword=xxx, 数量=5" |
| **WARNING** | 潜在问题提醒 | "指标匹配置信度低: 0.5"、"向量检索返回结果数量不足" |
| **ERROR** | 错误信息记录 | "向量检索失败: No module named 'psycopg2'"、"SQL执行异常: xxx" |
| **SUCCESS** | 成功操作记录 | "系统启动成功!"、"文档向量入库完成" |

#### 日志配置
日志默认输出到控制台，生产环境可配置输出到文件：

```python
# backend/app/core/logging.py
logger.add(
    "logs/app_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
```

### 14.3 新手入门指南

#### 1. 理解项目架构
- 阅读 [tech_plan.md](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/.trae/specs/init-steel-agent/tech_plan.md) 了解整体技术架构
- 阅读 [spec.md](file:///e:/@wisdri2026/00_aistudio/training_camp/Steel-Industry-Agent/.trae/specs/init-steel-agent/spec.md) 了解功能需求

#### 2. 理解核心流程
- **对话流程**：`router_service.py` → 意图识别 → 路由分发 → RAG/ChatBI
- **RAG流程**：`knowledge_service.py` → 文档解析 → 文本切片 → `vector_service.py` → 向量检索 → 生成回答
- **ChatBI流程**：`chatbi_service.py` → NL2Metrics优先 → NL2SQL兜底 → 结果解释

#### 3. 调试技巧
- 使用 `logger.info()` 记录关键步骤
- 使用 `logger.debug()` 记录详细参数
- 通过 Swagger UI（`/docs`）测试 API
- 查看 Docker 日志：`docker-compose logs -f backend`
