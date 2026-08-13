# Industrial Intelligent Assistant Platform 工业智能助手平台

钢铁行业工序级融合智能问答系统，集成 **RAG 工艺知识问答**、**ChatBI 智能问数**、**MCP 工具调用**、**Skill 技能执行** 四大能力，提供统一对话入口，自动识别用户意图并路由分发，支持纯知识查询、纯数据查询、知识+数据融合分析、工具调用、技能执行五种模式。

## 核心特性

- **融合推理**：单对话框同时支持工艺知识查询、生产数据查询、工具调用与技能执行，三级意图识别（关键词预判 + 工具相似度匹配 + LLM 深度分类）自动路由分发
- **RAG 知识问答**：多格式文档解析（PDF/Word/TXT/Markdown）、智能切片、向量检索、重排 Rerank、知识引用溯源
- **ChatBI 智能问数**：NL2Metrics 指标语义匹配 + NL2SQL 兜底，自动生成 SQL 并执行查询，支持表格/图表可视化
- **MCP 工具调用**：基于 MCP（Model Context Protocol）协议，SSE 长连接动态发现工具、构造参数、执行调用（如高德地图、天气服务等外部服务）
- **Skill 技能执行**：本地技能脚本包（ZIP 格式上传），支持特定领域任务执行（如高炉炉况诊断、转炉炼钢分析等）
- **全链路溯源**：文档引用溯源、SQL 执行溯源、思考过程展示、工具调用记录
- **SSE 流式响应**：知识问答与数据分析并行执行，实时流式输出，思考过程实时展示
- **可视化图表**：自动推荐图表类型（折线/柱状/饼图），ECharts 渲染，支持导出
- **应用发布与集成**：应用级配置、公开访问链接、第三方嵌入（网页嵌入/浮窗助手）、OAuth2 统一身份认证、访客模式
- **双用户体系**：系统用户（后台管理）与对话用户（应用集成）隔离，支持单点登录
- **私有化部署**：兼容国产大模型（Xinference），适配企业内网，Docker Compose 一键部署

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                    Vue3 Frontend                              │
│  (Element Plus + Pinia + ECharts + SSE Streaming)            │
└──────────────────────────┬───────────────────────────────────┘
                           │ /api
┌──────────────────────────▼───────────────────────────────────┐
│                  FastAPI Backend                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ 认证中间件 │  │ 审计中间件 │  │ 异常处理  │  │ 双用户体系   │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              三级意图识别与路由分发引擎                    │ │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │ │
│  │  │ 关键词预判 │→│ 工具相似度 │→│ LLM 深度分类        │    │ │
│  │  │          │  │ 匹配      │  │ (含工具描述注入)    │    │ │
│  │  └──────────┘  └──────────┘  └────────────────────┘    │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   多通道执行引擎                          │ │
│  │  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ │ │
│  │  │ RAG 知识   │ │ ChatBI    │ │ MCP 工具  │ │ Skill    │ │ │
│  │  │ 问答      │ │ 智能问数   │ │ 调用     │ │ 技能执行  │ │ │
│  │  │(LlamaIndex│ │(NL2Metrics│ │(SSE 协议)│ │(ZIP 包)  │ │ │
│  │  │+pgvector  │ │+NL2SQL)  │ │          │ │          │ │ │
│  │  │+Rerank)   │ │          │ │          │ │          │ │ │
│  │  └───────────┘ └───────────┘ └──────────┘ └──────────┘ │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────┬───────────────────────────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
┌──────────────┐    ┌────────────┐        ┌──────────────┐
│ PostgreSQL   │    │ MySQL      │        │ Xinference   │
│ + pgvector   │    │            │        │ 模型服务      │
│ 系统库+向量库 │    │ 业务数据库  │        │ (LLM/向量/重排)│
└──────────────┘    └────────────┘        └──────────────┘
```

## 技术栈

### 后端

| 技术 | 版本 | 用途 | 状态 |
|------|------|------|------|
| Python | 3.11+ | 运行环境 | ✅ 使用中 |
| FastAPI | 0.111+ | Web 框架 | ✅ 使用中 |
| SQLAlchemy | 2.0+ (async) | ORM | ✅ 使用中 |
| asyncpg | 0.29+ | PostgreSQL 异步驱动（系统库 + 向量库） | ✅ 使用中 |
| aiomysql | 0.2+ | MySQL 异步驱动（业务库） | ✅ 使用中 |
| psycopg2-binary | 2.9+ | PostgreSQL 同步驱动（pgvector 建表用） | ✅ 使用中 |
| pyodbc | 5.1+ | SQL Server 驱动（NL2SQL 跨库执行） | ✅ 使用中 |
| oracledb | 2.1+ | Oracle 驱动（NL2SQL 跨库执行） | ✅ 使用中 |
| LlamaIndex | 0.11+ | RAG 框架（向量检索 + 重排） | ✅ 使用中 |
| pgvector | - | 向量存储与检索（PostgreSQL 扩展） | ✅ 使用中 |
| sqlglot | 23.0+ | SQL 方言转换（NL2SQL 跨库适配） | ✅ 使用中 |
| httpx | 0.27+ | 异步 HTTP 客户端（调用 Xinference / MCP SSE） | ✅ 使用中 |
| python-jose | 3.3+ | JWT 认证 | ✅ 使用中 |
| passlib | 1.7+ | 密码加密（bcrypt） | ✅ 使用中 |
| pydantic-settings | 2.3+ | 配置管理 | ✅ 使用中 |
| loguru | 0.7+ | 日志 | ✅ 使用中 |
| redis | 5.0+ | 缓存 | ⚠️ **未使用**（已配置连接，暂无业务场景） |

### 前端

| 技术 | 版本 | 用途 | 状态 |
|------|------|------|------|
| Vue | 3.4+ | UI 框架（Composition API + `<script setup>`） | ✅ 使用中 |
| Vite | 5.4+ | 构建工具 | ✅ 使用中 |
| Pinia | 2.2+ | 状态管理 | ✅ 使用中 |
| Element Plus | 2.8+ | UI 组件库 | ✅ 使用中 |
| ECharts | 5.5+ | 图表可视化 | ✅ 使用中 |
| vue-echarts | 7.0+ | Vue ECharts 封装 | ✅ 使用中 |
| axios | 1.6+ | HTTP 客户端 | ✅ 使用中 |
| marked | 12.0+ | Markdown 渲染 | ✅ 使用中 |
| highlight.js | 11.9+ | 代码高亮 | ✅ 使用中 |
| katex | - | LaTeX 公式渲染 | ✅ 使用中 |

### 模型服务（Xinference）

| 服务 | 模型 | 用途 | 状态 |
|------|------|------|------|
| Xinference | bge-m3 | 文本嵌入（向量检索） | ✅ 使用中 |
| Xinference | bge-reranker-large | 重排序（Rerank） | ✅ 使用中 |
| Xinference | qwen3 / glm-5 | 对话/推理（LLM） | ✅ 使用中 |

### 基础设施

| 组件 | 版本 | 用途 | 状态 |
|------|------|------|------|
| PostgreSQL + pgvector | pg16 | 系统数据库 + 向量索引存储 | ✅ 使用中 |
| MySQL | 8.0 | 业务数据库（钢铁生产数据） | ✅ 使用中 |
| Redis | 7-alpine | 缓存 | ⚠️ **未使用**（已配置连接，暂无业务场景） |
| Nginx | alpine | 前端部署 + 反向代理 | ✅ 使用中 |
| Docker Compose | - | 容器编排 | ✅ 使用中 |

## 功能模块

### 1. 智能对话

- 单对话框统一入口，三级意图识别（关键词预判 + 工具相似度匹配 + LLM 深度分类）
- 五种执行通道：RAG 知识问答、ChatBI 数据分析、MCP 工具调用、Skill 技能执行、混合意图并行
- SSE 流式响应，思考过程实时展示（步骤、标题、描述）
- 知识引用溯源（文件列表 + 相似度分数 + 详情弹窗）
- SQL 执行溯源（查看 SQL 按钮 + 复制）
- 自动推荐图表类型并渲染可视化（折线/柱状/饼图/表格）
- AI 回复支持复制、重新生成、耗时展示
- 用户消息支持复制、编辑（转为输入框，发送后创建新历史）
- 多轮对话上下文（可配置历史消息条数，默认 10 条）
- 智能滚动（流式输出时自动滚动，用户上滚时停止）

### 2. 应用管理

- **应用设置**：创建/编辑/删除应用，配置基本信息、AI 模型设置（LLM 模型、温度、Top-P、Max Tokens）、提示词设置（系统提示词）、关联设置（知识库/数据源/MCP/Skill）、开场白设置、集成设置
- **调试预览**：应用设置页右侧实时调试预览，支持流式对话
- **集成设置**：
  - 公开访问链接（开启后生成可直接访问的 URL）
  - 第三方集成（生成 iframe 嵌入代码，支持网页嵌入 / 浮窗助手两种模式）
  - 身份验证（开启账号登录 / 关闭访客模式）
- **应用级配置**：每个应用独立配置模型参数、系统提示词、关联资源
- **应用发布**：发布后可通过公开链接或嵌入代码访问

### 3. 知识管理

- 创建知识库，上传多格式文档（PDF/Word/TXT/Markdown）
- 智能文档切片（可配置切片大小与重叠长度）
- 向量索引自动构建与更新（基于 LlamaIndex + pgvector）
- 重排检索（Rerank，提升检索准确率）
- 文档详情页：切片列表、关键词搜索、统计信息（分块数量、总字数、平均分块字数、文件大小）
- 知识库设置：名称、描述、向量模型、切片参数

### 4. 数据管理

- **数据源管理**：配置数据库连接（MySQL/PostgreSQL/Oracle/SQL Server），测试连接，同步 Schema
- **指标管理**：定义业务指标计算逻辑（SQL 表达式），支持分组与标签
- **维度管理**：定义查询维度、层级与枚举值，支持时间维度中文格式解析
- **术语管理**：行业术语与标准字段映射，提升 NL2SQL 准确率

### 5. 工具管理

- **MCP 工具配置**：
  - 配置 MCP Server（JSON 格式，包含 url、transport 等参数）
  - 支持 SSE 协议长连接
  - 动态工具发现（initialize 握手 → list_tools 获取工具列表）
  - 工具连接测试（验证真实连接状态，过滤默认 fallback 工具）
- **Skill 技能管理**：
  - 上传 Skill 技能包（ZIP 格式，包含技能脚本和配置）
  - Skill 文件路径存储为项目相对路径（`uploads/skills/xxx.zip`）
  - 支持技能执行（解析 ZIP 包 → 加载配置 → LLM 执行）
- **工具关联**：在应用设置中关联 MCP/Skill 工具，对话时自动识别和调用

### 6. 模型配置

- **LLM 模型配置**：配置 Xinference 中的 LLM 模型（如 qwen3、glm-5）
- **向量模型配置**：配置 Xinference 中的嵌入模型（如 bge-m3）
- **重排模型配置**：配置 Xinference 中的重排模型（如 bge-reranker-large）
- **默认模型管理**：每种模型类型只能有一个默认模型，类型间互不影响

### 7. 审计日志

- **自动记录**：通过中间件自动记录所有 HTTP 请求操作
- **多维度过滤**：按操作类型、资源类型、用户名、时间范围、IP 地址筛选
- **日志采集**：手动采集日志按钮（含序列自修复逻辑，防止主键冲突）
- **记录内容**：操作用户、操作类型、资源类型、资源 ID、资源名称、HTTP 方法、请求路径、IP 地址、操作状态、错误信息、操作详情（JSON）

### 8. 用户与认证

- **系统用户**（后台管理）：
  - 账号密码登录
  - OAuth2 统一身份认证（单点登录）
  - 密码修改
- **对话用户**（应用集成）：
  - OAuth2 统一身份认证（单点登录，与系统用户隔离）
  - 访客模式（无需登录，对话记录保存到本地 localStorage）
  - 对话记录隔离（每个对话用户独立会话列表）
- **双用户体系**：系统用户与对话用户完全隔离，独立认证、独立存储

### 9. 系统设置

- **OAuth2 配置**：配置系统用户和对话用户的 OAuth2 统一认证参数
- **审计日志**：操作记录查询与采集
- **账号管理**：密码修改

## 项目结构

```
Steel-Industry-Agent/
├── backend/                         # 后端服务
│   ├── app/
│   │   ├── api/v1/                  # API 路由层
│   │   │   ├── auth.py              # 系统用户认证
│   │   │   ├── chat_auth.py         # 对话用户认证
│   │   │   ├── oauth.py             # OAuth2 统一认证
│   │   │   ├── chat.py              # 对话接口（SSE 流式 + 嵌入模式）
│   │   │   ├── application.py       # 应用管理
│   │   │   ├── knowledge.py         # 知识管理
│   │   │   ├── datasource.py        # 数据源管理
│   │   │   ├── metric.py            # 指标管理
│   │   │   ├── dimension.py         # 维度管理
│   │   │   ├── term.py              # 术语管理
│   │   │   ├── tool.py              # 工具管理（MCP/Skill）
│   │   │   ├── llm_config.py        # 模型配置
│   │   │   ├── chatbi.py            # 智能问数
│   │   │   ├── chat_user.py         # 对话用户管理
│   │   │   ├── audit_log.py         # 审计日志
│   │   │   └── ...
│   │   ├── core/                    # 核心模块
│   │   │   ├── config.py            # 全局配置（双数据库 + Redis + 模型服务）
│   │   │   ├── database.py          # 数据库连接（PostgreSQL 系统库 + MySQL 业务库）
│   │   │   ├── llm_client.py        # LLM 客户端
│   │   │   └── redis_client.py      # Redis 客户端（⚠️ 未使用）
│   │   ├── models/                  # 数据模型
│   │   │   ├── user.py              # 系统用户
│   │   │   ├── chat_user.py         # 对话用户
│   │   │   ├── oauth_config.py      # OAuth2 配置
│   │   │   ├── session.py           # 会话/消息/溯源
│   │   │   ├── application.py       # 应用配置
│   │   │   ├── knowledge.py         # 知识库/文档/切片
│   │   │   ├── datasource.py        # 数据源
│   │   │   ├── metric.py            # 指标
│   │   │   ├── dimension.py         # 维度
│   │   │   ├── term.py              # 术语
│   │   │   ├── tool_config.py       # 工具配置（MCP/Skill）
│   │   │   ├── llm_config.py        # 模型配置
│   │   │   └── audit_log.py         # 审计日志
│   │   ├── schemas/                 # 请求/响应模型（Pydantic）
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── router_service.py    # 三级意图识别与路由分发
│   │   │   ├── vector_service.py    # RAG 向量检索与知识问答
│   │   │   ├── chatbi_service.py    # ChatBI 智能问数
│   │   │   ├── nl2metrics_service.py # NL2Metrics 指标查询引擎
│   │   │   ├── nl2sql_service.py    # NL2SQL 兜底引擎
│   │   │   ├── mcp_client_service.py # MCP 工具调用（SSE 协议）
│   │   │   ├── skill_executor_service.py # Skill 技能执行
│   │   │   ├── llm_service.py       # LLM 调用服务
│   │   │   ├── knowledge_service.py # 知识库管理
│   │   │   ├── session_service.py   # 会话管理
│   │   │   ├── tool_config_service.py # 工具配置管理
│   │   │   ├── oauth_service.py     # OAuth2 认证
│   │   │   ├── auth_service.py      # 认证服务
│   │   │   └── ...
│   │   ├── middlewares/             # 中间件
│   │   │   ├── auth_deps.py         # 认证依赖
│   │   │   └── exception_handler.py # 异常处理
│   │   └── utils/                   # 工具函数
│   ├── uploads/skills/              # Skill 技能包存储
│   ├── .env.example                 # 环境变量模板
│   ├── seed_data.py                 # 种子数据初始化
│   ├── main.py                      # 应用入口
│   ├── requirements.txt             # Python 依赖
│   └── Dockerfile
├── frontend/                        # 前端服务
│   ├── src/
│   │   ├── api/                     # API 接口层
│   │   ├── components/              # 公共组件
│   │   │   ├── chart/               # 图表组件（ChartCard, DataTable）
│   │   │   ├── chat/                # 对话组件（ChatMessage, ChatPanel）
│   │   │   └── layout/              # 布局组件（Header, Sidebar, MainLayout）
│   │   ├── router/                  # 路由配置
│   │   ├── stores/                  # Pinia 状态管理
│   │   ├── views/                   # 页面视图
│   │   │   ├── ChatView.vue         # 智能对话页
│   │   │   ├── ChatEmbedView.vue    # 嵌入式对话页（网页嵌入/浮窗助手）
│   │   │   ├── AppListView.vue      # 应用管理页
│   │   │   ├── KnowledgeView.vue    # 知识管理页
│   │   │   ├── DataConfigView.vue   # 数据管理页
│   │   │   ├── ToolManagementView.vue # 工具管理页
│   │   │   ├── ModelConfigView.vue  # 模型配置页
│   │   │   ├── AuditLogView.vue     # 审计日志页
│   │   │   ├── SystemSettingsView.vue # 系统设置页
│   │   │   ├── ChatUserView.vue     # 对话用户页
│   │   │   ├── LoginView.vue        # 系统登录页
│   │   │   ├── AppLoginView.vue     # 应用登录页
│   │   │   └── OAuthCallbackView.vue # OAuth2 回调页
│   │   └── styles/                  # 全局样式
│   ├── public/                      # 静态资源
│   │   ├── chat-embed.js            # 嵌入式对话脚本
│   │   └── embed.html               # 嵌入示例
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml               # Docker 编排
├── README.md                        # 项目说明文档
└── DEPLOYMENT.md                    # 部署文档
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- pnpm
- PostgreSQL 16 + pgvector 扩展
- MySQL 8.0（业务数据库）
- Xinference（模型服务）
- Redis 7+（⚠️ 已配置但暂未使用，可不启动）

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
# ==================== 服务端口配置 ====================
BACKEND_PORT=8000
FRONTEND_PORT=5173

# ==================== PostgreSQL 配置（系统数据库 + 向量库） ====================
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

# ==================== Redis 配置（⚠️ 暂未使用） ====================
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0

# ==================== Xinference 模型服务配置 ====================
XINFERENCE_BASE_URL=http://your-xinference-host:9997
XINFERENCE_EMBED_MODEL=bge-m3
XINFERENCE_LLM_MODEL=qwen3
XINFERENCE_RERANK_MODEL=bge-reranker-large
RERANK_TOP_K=5
LLM_MAX_TOKENS=20480
LLM_TEMPERATURE=0.7

# ==================== JWT 配置 ====================
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ==================== 多轮对话配置 ====================
# 加载到 LLM 上下文的历史消息条数（1轮=user+assistant=2条，10条=5轮对话）
CHAT_HISTORY_LIMIT=10
```

### 3. 启动后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动服务（自动初始化数据库和种子数据）
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
| postgres | 5432 | PostgreSQL + pgvector（系统库 + 向量库） |
| mysql | 3306 | MySQL（业务数据库） |
| redis | 6379 | Redis 缓存（⚠️ 暂未使用） |

## 数据库架构

系统采用双数据库架构，分离系统数据与业务数据：

| 数据库 | 名称 | 用途 | 核心表 |
|--------|------|------|--------|
| PostgreSQL | `steel_agent` | 系统数据库 + 向量数据库 | 用户、对话用户、OAuth2 配置、会话、消息、溯源、应用、知识库、文档切片、数据源、指标、维度、术语、工具配置(MCP/Skill)、模型配置、审计日志、向量索引(pgvector) |
| MySQL | `steel_test` | 业务数据库 | `bof_act_heat_add`（转炉炼钢）、`hgbf1_condition_result`（高炉炉况打分）等钢铁生产数据 |

### 向量索引表

每个知识库在 PostgreSQL 中对应一个独立的向量表，表名格式为 `kb_{knowledge_base_id}`，包含：
- `id`: 主键
- `text`: 文档切片内容
- `embedding`: 向量（pgvector vector 类型）
- `metadata`: JSON 格式元数据（segment_id, document_id 等）

## 意图识别与路由分发流程

```
用户提问
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                 三级意图识别引擎                          │
│                                                         │
│  第1级：关键词预判                                       │
│  ├── 强关键词命中（如"高炉炉况诊断"）→ tool 意图         │
│  ├── 询问技能类（如"你有什么技能"）→ 返回技能列表        │
│  └── 数据/知识关键词 → 进入下一级                        │
│                                                         │
│  第2级：工具相似度匹配                                   │
│  ├── MCP 工具名称/关键词匹配 → mcp 意图                 │
│  └── Skill 工具名称匹配（命中率≥80%）→ skill 意图       │
│                                                         │
│  第3级：LLM 深度分类                                     │
│  ├── 注入工具描述（MCP/Skill name+description）         │
│  ├── 注入数据源 Schema 摘要                             │
│  └── LLM 判定: knowledge / data / hybrid / mcp / skill  │
└─────────────────────────────────────────────────────────┘
    │
    ├── knowledge ──→ RAG 检索 ──→ 知识问答 + 引用溯源
    │
    ├── data ──────→ ChatBI ──┬─ NL2Metrics（指标匹配 → SQL）
    │                          └─ NL2SQL（Schema Linking → LLM 生成 SQL）
    │
    ├── mcp ───────→ MCP 工具调用 ──→ LLM 选择工具 → 执行 → 回答
    │
    ├── skill ─────→ Skill 技能执行 ──→ 加载 ZIP 包 → LLM 执行 → 回答
    │
    └── hybrid ────→ 并行执行 RAG + ChatBI ──→ 融合推理（知识 + 数据综合分析）
                        │
                        ▼
                   SSE 流式输出 + 图表可视化 + 思考过程
```

## API 接口

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | `/api/v1/auth/login` | 系统用户登录 |
| 认证 | POST | `/api/v1/auth/change-password` | 修改密码 |
| OAuth2 | GET | `/api/v1/oauth/login-url` | 获取系统用户 OAuth2 授权 URL |
| OAuth2 | GET | `/api/v1/oauth/chat-login-url` | 获取对话用户 OAuth2 授权 URL |
| OAuth2 | GET | `/api/v1/oauth/callback` | OAuth2 回调 |
| 对话用户 | POST | `/api/v1/chat-users/login` | 对话用户登录 |
| 对话用户 | GET | `/api/v1/chat-users/me` | 获取当前对话用户 |
| 对话 | GET | `/api/v1/sessions` | 获取会话列表 |
| 对话 | POST | `/api/v1/sessions` | 创建会话 |
| 对话 | GET | `/api/v1/sessions/{id}/messages` | 获取会话消息 |
| 对话 | POST | `/api/v1/sessions/stream` | 发送消息（SSE 流式） |
| 对话 | POST | `/api/v1/sessions/embed/chat` | 嵌入模式对话（公开访问） |
| 对话 | POST | `/api/v1/chat/embed` | 嵌入模式对话（带身份验证） |
| 应用 | GET | `/api/v1/applications` | 应用列表 |
| 应用 | POST | `/api/v1/applications` | 创建应用 |
| 应用 | PUT | `/api/v1/applications/{id}` | 更新应用 |
| 应用 | DELETE | `/api/v1/applications/{id}` | 删除应用 |
| 应用 | POST | `/api/v1/applications/{id}/regenerate-api-key` | 重新生成 API 密钥 |
| 知识 | GET | `/api/v1/knowledge/bases` | 知识库列表 |
| 知识 | POST | `/api/v1/knowledge/bases` | 创建知识库 |
| 知识 | POST | `/api/v1/knowledge/bases/{id}/documents` | 上传文档 |
| 知识 | POST | `/api/v1/knowledge/bases/{id}/build-index` | 构建索引 |
| 工具 | GET | `/api/v1/tools` | 工具列表（MCP/Skill） |
| 工具 | POST | `/api/v1/tools` | 创建工具 |
| 工具 | POST | `/api/v1/tools/{id}/test` | 测试工具连接 |
| 工具 | POST | `/api/v1/tools/{id}/upload-skill` | 上传 Skill 文件 |
| 数据源 | GET | `/api/v1/datasources` | 数据源列表 |
| 数据源 | POST | `/api/v1/datasources/{id}/test` | 测试连接 |
| 数据源 | POST | `/api/v1/datasources/{id}/sync-schema` | 同步 Schema |
| 指标 | GET | `/api/v1/metrics` | 指标列表 |
| 维度 | GET | `/api/v1/dimensions` | 维度列表 |
| 术语 | GET | `/api/v1/terms` | 术语列表 |
| 模型配置 | GET | `/api/v1/llm-config` | 获取模型配置 |
| 模型配置 | PUT | `/api/v1/llm-config/{id}` | 更新模型配置 |
| 模型配置 | GET | `/api/v1/llm-config/default/{type}` | 获取默认模型 |
| 审计日志 | GET | `/api/v1/audit-logs` | 审计日志列表 |
| 审计日志 | POST | `/api/v1/audit-logs/collect` | 采集日志 |
| 健康检查 | GET | `/api/v1/health` | 健康检查 |

完整 API 文档请访问 Swagger UI：`http://localhost:8000/docs`

## 应用集成方式

### 1. 公开访问链接

在应用设置 → 集成设置中开启"公开访问链接"，生成可直接访问的 URL：
```
http://your-domain/chat/{appId}
```

### 2. 第三方嵌入

生成 iframe 嵌入代码，支持两种模式：

**网页嵌入模式**（fullscreen）：
```html
<iframe
  src="http://your-domain/chat/{appId}?mode=fullscreen"
  width="100%"
  height="600px"
  frameborder="0"
></iframe>
```

**浮窗助手模式**（float）：
```html
<script src="http://your-domain/chat-embed.js?appId={appId}"></script>
```
浮窗助手特性：
- 右下角浮动入口图标
- 点击展开对话窗口（右下角对齐，50% 视口宽度）
- 支持最小化/关闭/新对话
- 访客模式对话记录保存到本地 localStorage
- 多 iframe 实例间对话记录实时同步（通过 storage 事件）

### 3. 身份验证

- **开启身份验证**：对话用户通过 OAuth2 登录，对话记录关联对话用户
- **关闭身份验证**：访客模式，无需登录，对话记录保存到本地

## 代码注释规范

项目遵循以下代码注释规范，便于新手理解代码逻辑和快速上手：

### Python 代码

- **模块文档字符串**：每个模块顶部添加三重引号注释，说明模块功能、数据关系、注意事项
- **类注释**：使用三重引号，包含类的功能描述、核心属性说明、处理流程
- **方法注释**：使用三重引号，包含参数说明（:param）、返回值说明（:return）、异常说明（:raises）
- **关键逻辑注释**：复杂业务逻辑添加步骤说明注释
- **日志记录**：使用 loguru 记录关键操作、错误信息和性能指标

### 代码示例规范

```python
"""
模块文档字符串：说明模块功能、数据关系、注意事项
"""
class ExampleService:
    """
    类文档字符串：说明类的功能、核心属性和处理流程
    """

    def example_method(self, param1: str) -> dict:
        """
        方法文档字符串：详细说明方法功能和参数

        :param param1: 参数说明
        :return: 返回值说明
        :raises BusinessException: 异常说明
        """
        # 步骤1：参数校验
        # 步骤2：业务逻辑处理
        # 步骤3：返回结果
        pass
```

### Vue/TypeScript 代码

- **组件注释**：使用 JSDoc 格式，说明组件功能和 props
- **方法注释**：使用 JSDoc 格式，说明参数和返回值
- **类型定义**：完整的 TypeScript 类型标注

### 日志规范

- **INFO**：记录关键业务流程（如"意图分类结果"、"SQL 执行完成"）
- **DEBUG**：记录详细调试信息（如"图表类型匹配"、"术语搜索完成"）
- **WARNING**：记录潜在问题（如"指标匹配置信度低"、"Redis 连接失败"）
- **ERROR**：记录错误信息（如"向量检索失败"、"SQL 执行异常"）

## 开发流程

1. **环境准备**：安装 Python 3.11+、Node.js 18+、PostgreSQL、MySQL、Xinference
2. **代码克隆**：git clone 项目代码
3. **配置环境变量**：复制 .env.example 为 .env，配置数据库和模型服务
4. **安装依赖**：后端 pip install，前端 pnpm install
5. **启动服务**：后端 uvicorn，前端 pnpm dev
6. **开发调试**：使用 IDE 调试，查看日志
7. **代码提交**：遵循 Commitlint 规范

## 模块状态说明

| 模块 | 状态 | 说明 |
|------|------|------|
| RAG 知识问答 | ✅ 已实现 | LlamaIndex + pgvector + Rerank |
| ChatBI 智能问数 | ✅ 已实现 | NL2Metrics + NL2SQL + 可视化 |
| MCP 工具调用 | ✅ 已实现 | SSE 协议 + 动态工具发现 |
| Skill 技能执行 | ✅ 已实现 | ZIP 包上传 + LLM 执行 |
| 混合意图 | ✅ 已实现 | RAG + ChatBI 并行 + 融合推理 |
| 应用发布与集成 | ✅ 已实现 | 公开链接 + iframe 嵌入 + 浮窗助手 |
| OAuth2 统一认证 | ✅ 已实现 | 系统用户 + 对话用户双通道 |
| 审计日志 | ✅ 已实现 | 自动记录 + 多维度过滤 |
| Redis 缓存 | ⚠️ 未使用 | 已配置连接，暂无业务场景 |
| Agent 智能体模式 | 📋 规划中 | ReAct 引擎 + 统一工具注册（阶段一） |
| 任务规划 (Planning) | 📋 规划中 | 复杂任务拆解为子任务 DAG（阶段二） |
| 反思纠错 (Reflection) | 📋 规划中 | 工具失败自动重试 + Query 改写（阶段三） |
| 长期记忆 (Memory) | 📋 规划中 | 跨会话用户偏好 + 历史交互（阶段四） |

## License

Private - All Rights Reserved
