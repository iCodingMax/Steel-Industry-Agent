# Steel-Industry-Agent 钢铁行业智能助手

钢铁行业工序级融合智能问答系统，集成 **RAG 工艺知识问答** 与 **ChatBI 智能问数**，提供统一对话入口，支持纯知识查询、纯数据查询、知识+数据融合分析三种模式。

## 核心特性

- **融合推理**：单对话框同时支持工艺知识查询与生产数据查询，自动意图识别与路由分发
- **RAG 知识问答**：多格式文档解析（PDF/Word/TXT）、智能切片、向量+BM25 混合检索、Rerank 重排
- **ChatBI 智能问数**：NL2Metrics 指标语义匹配 + NL2SQL 兜底，自动生成 SQL 并执行查询
- **全链路溯源**：文档引用溯源、SQL 执行溯源、思考过程展示
- **SSE 流式响应**：知识问答与数据分析并行执行，实时流式输出
- **可视化图表**：自动推荐图表类型（折线/柱状/饼图），ECharts 渲染
- **私有化部署**：兼容国产大模型，适配企业内网，Docker Compose 一键部署

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Vue3 Frontend                     │
│  (Element Plus + Pinia + ECharts + SSE Streaming)   │
└──────────────────────┬──────────────────────────────┘
                       │ /api
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ 路由分发  │  │ 用户认证  │  │   全链路溯源       │  │
│  └────┬─────┘  └──────────┘  └───────────────────┘  │
│       │                                               │
│  ┌────▼──────────────────────────────────────────┐   │
│  │              融合推理引擎                       │   │
│  │  ┌─────────────┐    ┌─────────────────────┐   │   │
│  │  │  RAG 知识问答 │    │  ChatBI 智能问数     │   │   │
│  │  │ (LlamaIndex  │    │ ┌────────┐┌───────┐ │   │   │
│  │  │  + pgvector  │    │ │NL2Metrics│NL2SQL │ │   │   │
│  │  │  + Rerank)   │    │ │ 指标匹配 │LLM兜底│ │   │   │
│  │  └─────────────┘    │ └────────┘└───────┘ │   │   │
│  │                     └─────────────────────┘   │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
┌────────┐      ┌──────────┐      ┌────────┐
│ MySQL  │      │PostgreSQL│      │ Redis  │
│系统+业务│      │ +pgvector│      │ 缓存   │
└────────┘      └──────────┘      └────────┘
```

## 技术栈

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行环境 |
| FastAPI | 0.111+ | Web 框架 |
| SQLAlchemy | 2.0+ (async) | ORM |
| aiomysql | 0.2+ | MySQL 异步驱动 |
| asyncpg | 0.29+ | PostgreSQL 异步驱动 |
| LlamaIndex | - | RAG 框架 |
| pgvector | - | 向量存储与检索 |
| pydantic-settings | 2.3+ | 配置管理 |
| python-jose | 3.3+ | JWT 认证 |
| loguru | 0.7+ | 日志 |

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.4+ | UI 框架 |
| Vite | 5.4+ | 构建工具 |
| Pinia | 2.2+ | 状态管理 |
| Element Plus | 2.8+ | UI 组件库 |
| ECharts | 5.5+ | 图表可视化 |
| vue-echarts | 7.0+ | Vue ECharts 封装 |
| axios | 1.6+ | HTTP 客户端 |
| marked | 12.0+ | Markdown 渲染 |
| highlight.js | 11.9+ | 代码高亮 |

### 模型服务

| 服务 | 模型 | 用途 |
|------|------|------|
| Xinference | bge-m3 | 文本嵌入 |
| Xinference | bge-reranker-large | 重排序 |
| NewAPI | glm-5.1-fp8 | 对话/推理 |

### 基础设施

| 组件 | 版本 | 用途 |
|------|------|------|
| MySQL | 8.0 | 系统数据库 + 业务数据库 |
| PostgreSQL + pgvector | pg16 | 向量索引存储 |
| Redis | 7-alpine | 缓存 |
| Nginx | alpine | 前端部署 + 反向代理 |

## 功能模块

### 智能对话

- 单对话框统一入口，自动识别用户意图（知识/数据/混合）
- RAG 知识问答与 ChatBI 数据分析并行执行
- SSE 流式响应，思考过程实时展示
- 知识引用溯源，SQL 执行溯源
- 自动推荐图表类型并渲染可视化

### 知识管理

- 创建知识库，上传多格式文档（PDF/Word/TXT/Markdown）
- 智能文档切片（可配置切片大小与重叠）
- 文档详情页：切片列表、搜索、统计
- 向量索引自动构建与更新

### 数据管理

- **数据源管理**：配置数据库连接（MySQL/PostgreSQL/Oracle），测试连接，同步 Schema
- **指标管理**：定义业务指标计算逻辑（SQL 表达式），支持分组与标签
- **维度管理**：定义查询维度、层级与枚举值，支持时间维度中文格式解析
- **术语管理**：行业术语与标准字段映射，提升 NL2SQL 准确率

### 系统设置

- **模型配置**：Xinference 嵌入/重排模型配置，NewAPI 对话模型配置
- **审计日志**：操作记录查询
- **账号管理**：密码修改

## 项目结构

```
Steel-Industry-Agent/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── api/v1/            # API 路由层
│   │   │   ├── auth.py        # 认证接口
│   │   │   ├── chat.py        # 对话接口（SSE 流式）
│   │   │   ├── chatbi.py      # 智能问数接口
│   │   │   ├── knowledge.py   # 知识管理接口
│   │   │   ├── datasource.py  # 数据源管理接口
│   │   │   ├── metric.py      # 指标管理接口
│   │   │   ├── dimension.py   # 维度管理接口
│   │   │   ├── term.py        # 术语管理接口
│   │   │   └── ...
│   │   ├── core/              # 核心模块
│   │   │   ├── config.py      # 全局配置（双数据库）
│   │   │   ├── database.py    # 数据库连接（MySQL + PostgreSQL）
│   │   │   └── llm_client.py  # LLM 客户端
│   │   ├── models/            # 数据模型
│   │   │   ├── session.py     # 会话/消息/溯源模型
│   │   │   ├── knowledge.py   # 知识库/文档/切片模型
│   │   │   ├── datasource.py  # 数据源模型
│   │   │   ├── metric.py      # 指标模型
│   │   │   ├── dimension.py   # 维度模型
│   │   │   └── term.py        # 术语模型
│   │   ├── schemas/           # 请求/响应模型
│   │   ├── services/          # 业务逻辑层
│   │   │   ├── router_service.py     # 意图识别与路由
│   │   │   ├── vector_service.py     # RAG 向量检索与知识问答
│   │   │   ├── chatbi_service.py     # ChatBI 智能问数服务
│   │   │   ├── nl2metrics_service.py # NL2Metrics 指标查询引擎
│   │   │   ├── nl2sql_service.py     # NL2SQL 兜底引擎
│   │   │   ├── llm_service.py        # LLM 调用服务
│   │   │   ├── knowledge_service.py  # 知识库管理服务
│   │   │   └── session_service.py    # 会话管理服务
│   │   └── utils/             # 工具函数
│   ├── storage/documents/     # 上传文档存储
│   ├── seed_data.py           # 种子数据初始化
│   ├── main.py                # 应用入口
│   ├── requirements.txt       # Python 依赖
│   └── Dockerfile
├── frontend/                   # 前端服务
│   ├── src/
│   │   ├── api/               # API 接口层
│   │   ├── components/        # 公共组件
│   │   │   ├── chart/         # 图表组件（ChartCard, DataTable）
│   │   │   └── layout/        # 布局组件（Header, Sidebar, MainLayout）
│   │   ├── router/            # 路由配置
│   │   ├── stores/            # Pinia 状态管理
│   │   ├── views/             # 页面视图
│   │   │   ├── ChatView.vue          # 智能对话页
│   │   │   ├── KnowledgeView.vue     # 知识管理页
│   │   │   ├── DataConfigView.vue    # 数据管理页
│   │   │   ├── DatasourceDetailView.vue # 数据源详情页
│   │   │   ├── ModelConfigView.vue   # 模型配置页
│   │   │   ├── AuditLogView.vue      # 审计日志页
│   │   │   └── LoginView.vue         # 登录页
│   │   └── styles/            # 全局样式
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml          # Docker 编排
└── DEPLOYMENT.md               # 部署文档
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pnpm
- MySQL 8.0
- PostgreSQL 16 + pgvector 扩展
- Redis 7+

### 1. 克隆项目

```bash
git clone <repository-url>
cd Steel-Industry-Agent
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，配置数据库连接、模型服务地址等
```

关键配置项：

```bash
# MySQL（系统数据库 + 业务数据库）
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your-password
MYSQL_DB=steel_agent

# 业务数据库（钢铁生产数据）
BUSINESS_DB_HOST=localhost
BUSINESS_DB_PORT=3306
BUSINESS_DB_USER=root
BUSINESS_DB_PASSWORD=your-password
BUSINESS_DB_NAME=steel_test

# PostgreSQL + pgvector
PG_HOST=localhost
PG_PORT=5432
PG_USER=postgres
PG_PASSWORD=your-password
PG_DB=steel_agent_vector

# 模型服务
XINFERENCE_BASE_URL=http://your-xinference-host:9997
NEWAPI_BASE_URL=http://your-newapi-host:3000
NEWAPI_API_KEY=your-api-key
NEWAPI_MODEL=glm-5.1-fp8
```

### 3. 启动后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt
# 或使用 poetry
# poetry install

# 启动服务（自动初始化数据库和种子数据）
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 启动前端

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

### 5. 访问系统

- 前端地址：http://localhost:5173
- API 文档：http://localhost:8000/docs
- 默认账号：admin / admin

### Docker Compose 部署

```bash
# 一键启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

服务组件：

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 8080 | Nginx 前端 |
| backend | 8000 | FastAPI 后端 |
| mysql | 3306 | MySQL 数据库 |
| postgres | 5432 | PostgreSQL + pgvector |
| redis | 6379 | Redis 缓存 |

## 双数据库架构

系统采用双数据库架构，分离系统数据与业务数据：

| 数据库 | 名称 | 用途 | 核心表 |
|--------|------|------|--------|
| MySQL | `steel_agent` | 系统数据库 | 用户、会话、消息、数据源、指标、维度、术语、知识库等 |
| MySQL | `steel_test` | 业务数据库 | `bof_act_heat_add`（转炉炼钢）、`hgbf1_condition_result`（高炉炉况打分）等 |
| PostgreSQL | `steel_agent_vector` | 向量数据库 | 文档切片向量索引（pgvector） |

## 融合推理流程

```
用户提问
    │
    ▼
意图识别（知识/数据/混合）
    │
    ├── 知识意图 ──→ RAG 检索 ──→ 知识问答
    │
    ├── 数据意图 ──→ ChatBI ──┬─ NL2Metrics（指标匹配 → SQL）
    │                         └─ NL2SQL（Schema Linking → LLM 生成 SQL）
    │
    └── 混合意图 ──→ 并行执行 RAG + ChatBI
                        │
                        ▼
                   融合推理（知识 + 数据综合分析）
                        │
                        ▼
                   SSE 流式输出 + 图表可视化
```

## API 接口

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/api/v1/auth/login` | 用户登录 |
| 对话 | GET | `/api/v1/chat` | 获取会话列表 |
| 对话 | POST | `/api/v1/chat` | 创建会话 |
| 对话 | POST | `/api/v1/chat/{id}/message` | 发送消息（SSE） |
| 知识 | GET | `/api/v1/knowledge/bases` | 知识库列表 |
| 知识 | POST | `/api/v1/knowledge/bases` | 创建知识库 |
| 知识 | POST | `/api/v1/knowledge/bases/{id}/documents` | 上传文档 |
| 数据源 | GET | `/api/v1/datasources` | 数据源列表 |
| 数据源 | POST | `/api/v1/datasources/{id}/test` | 测试连接 |
| 数据源 | POST | `/api/v1/datasources/{id}/sync-schema` | 同步 Schema |
| 指标 | GET | `/api/v1/metrics` | 指标列表 |
| 维度 | GET | `/api/v1/dimensions` | 维度列表 |
| 术语 | GET | `/api/v1/terms` | 术语列表 |

完整 API 文档请访问 Swagger UI：`http://localhost:8000/docs`

## License

Private - All Rights Reserved
