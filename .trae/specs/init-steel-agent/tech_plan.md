# 钢铁行业工序级融合智能问答系统 - 技术方案

## 一、项目概述

### 1.1 项目名称
Steel-Industry-Agent

### 1.2 项目定位
钢铁行业工序级融合智能问答系统，面向高炉炼铁、转炉炼钢等核心场景，实现RAG工艺知识问答与ChatBI智能问数的一体化深度融合，为工艺、生产、质量人员提供单入口、可追溯、可解释的智能决策辅助。

### 1.3 核心目标
1. 单对话框同时支持纯工艺知识查询、纯生产数据查询、知识+数据混合分析，无需切换系统
2. 全链路执行过程透明可追溯，结果同时支持文档引用溯源与数据SQL溯源
3. 支持私有化部署，兼容国产大模型与工业主流数据库，适配企业内网环境

---

## 二、技术路线与选型

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        前端管理后台 (Vue.js)                              │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐                │
│  │ 登录页  │ │ 对话页   │ │知识库管理│ │数据配置/系统设置 │                │
│  └────┬────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘                │
└───────┼─────────────┼────────────┼────────────┼──────────────────────────┘
        │             │            │            │
        ▼             ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     API网关层 (FastAPI)                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                  │
│  │ Auth API │ │ Chat API │ │ KB  API  │ │Config API│                  │
│  │ 认证鉴权 │ │ 对话/SSE │ │知识库管理│ │数据配置  │                  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘                  │
└───────┼──────────────┼────────────┼────────────┼────────────────────────┘
        │              │            │            │
        ▼              ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          业务逻辑层                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐                     │
│  │  RAG模块     │  │  ChatBI模块  │  │ 配置服务  │                     │
│  │ 基于LlamaIndex│ │ 原生SQL生成  │  │ 数据源    │                     │
│  │ 混合检索/重排│ │ NL2Metrics   │  │ 指标/维度 │                     │
│  │              │ │ SQL校验/安全 │  │ 术语/模型 │                     │
│  └──────┬───────┘  └──────┬───────┘  └───────────┘                     │
│         │                 │                                              │
│  ┌──────┴─────────────────┴──────────────────────────────────────┐      │
│  │                      路由分发层                                │      │
│  │     意图识别(知识/数据/混合) → 路由分发 → 结果融合             │      │
│  └───────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
        │              │               │
        ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          数据存储层                                       │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ PostgreSQL     │  │  MySQL       │  │  Redis       │  │ 文件存储  │ │
│  │ (pgvector)     │  │ 业务库       │  │ 缓存/会话    │  │ 文档      │ │
│  │ 向量索引       │  │ 用户/会话    │  │ 配置缓存     │  │           │ │
│  │ 文档片段       │  │ 数据源/指标  │  │              │  │           │ │
│  │                │  │ 维度/术语    │  │              │  │           │ │
│  │                │  │ 溯源日志     │  │              │  │           │ │
│  └────────────────┘  └──────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 技术选型

| 分类 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| 后端语言 | Python | 3.11 | 生态成熟，机器学习库丰富，适合大模型应用开发 |
| Web框架 | FastAPI | 0.115+ | 高性能、异步支持、自动API文档、类型安全 |
| ORM | SQLAlchemy | 2.0+ | 成熟ORM框架，支持异步，支持多数据库 |
| RAG框架 | LlamaIndex | 0.11+ | 专注RAG场景，集成度高，支持pgvector，文档化好 |
| 前端框架 | Vue.js | 3.4+ | 响应式、组合式API、轻量、生态完善 |
| 前端构建 | Vite | 6.5+ | 快速构建、热更新、原生ESM支持 |
| UI组件 | Element Plus | 2.8+ | 基于Vue3的企业级组件库，样式统一 |
| 状态管理 | Pinia | 2.2+ | Vue官方推荐，轻量化状态管理 |
| 路由 | Vue Router | 4.3+ | 官方路由，支持导航守卫 |
| 数据可视化 | Echarts | 5.5+ | 功能强大，支持多种图表类型，性能优异 |
| 向量数据库 | PostgreSQL + pgvector | 16+ | 企业级数据库，支持向量索引，便于运维 |
| 关系数据库 | MySQL | 8.0+ | 工业主流数据库，性能稳定，生态成熟 |
| 缓存 | Redis | 7.2+ | 会话管理、上下文缓存、配置缓存 |
| 大模型 | OpenAI/国产模型 | - | 通过配置切换，支持Qwen、DeepSeek等 |
| 嵌入模型 | bge-m3 | - | 中文效果好，支持本地部署 |
| 重排模型 | bge-reranker-v2-m3 | - | 轻量级交叉编码器，中文效果优异 |
| 认证 | JWT + bcrypt | - | 无状态认证，密码安全存储 |
| 部署 | Docker Compose | 2.26+ | 容器化部署，一键启动所有组件 |
| 文档解析 | LlamaIndex Readers | - | LlamaIndex内置多格式文档加载器 |
| 中文分词 | jieba | 0.42+ | 中文分词，用于BM25关键词检索 |

### 2.3 框架选型分析（LlamaIndex vs LangChain）

#### RAG模块：选择LlamaIndex
**理由**：
- LlamaIndex专注于RAG场景，架构更清晰，内置数据连接器、索引构建、查询引擎等完整链路
- 原生支持pgvector向量存储，与项目技术栈完美契合
- 内置多种索引类型（VectorStoreIndex、SummaryIndex、KnowledgeGraphIndex），便于后续扩展
- 内置检索增强技术（Reranker、MultiQuery、HybridSearch），开箱即用
- 文档化完善，社区活跃，学习曲线相对平缓

**使用方式**：
- 使用LlamaIndex的`SimpleDirectoryReader`加载文档
- 使用`VectorStoreIndex`构建向量索引
- 使用`Settings.embed_model`配置bge-m3嵌入模型
- 使用`HybridSearchQueryEngine`实现混合检索

#### ChatBI模块：原生实现 + 轻量级依赖
**理由**：
- ChatBI核心是NL2SQL/NL2Metrics，逻辑相对独立，不需要复杂框架
- 原生实现更灵活，便于与业务配置（指标、维度、术语）深度集成
- SQL生成和校验逻辑简单，可直接调用大模型API实现
- 避免引入LangChain的复杂性和学习成本

**使用方式**：
- 直接调用大模型API生成SQL
- 使用sqlglot进行SQL语法校验
- 使用自定义规则进行安全过滤

#### 路由分发模块：原生实现
**理由**：
- 路由逻辑简单清晰：意图识别→分发→融合
- 原生实现便于与溯源模块深度集成
- 避免框架带来的额外开销

**使用方式**：
- 调用大模型进行意图分类
- 基于分类结果路由到对应服务
- 使用asyncio实现并行调用

#### 总结
| 模块 | 技术选择 | 理由 |
|------|----------|------|
| RAG知识问答 | LlamaIndex | 专注RAG，集成度高，支持pgvector |
| ChatBI智能问数 | 原生实现 | 逻辑独立，便于与业务配置集成 |
| 路由分发 | 原生实现 | 逻辑简单，便于溯源集成 |
| 大模型调用 | 原生HTTP调用 | 轻量级，灵活适配多厂商API |
| 嵌入模型 | LlamaIndex + bge-m3 | LlamaIndex内置支持，易于切换 |

---

## 三、项目结构

### 3.1 后端项目结构

```
backend/
├── app/                          # 应用主目录
│   ├── __init__.py
│   ├── main.py                   # FastAPI应用入口
│   ├── core/                     # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py             # 配置管理（pydantic-settings）
│   │   ├── database.py           # 数据库连接管理（SQLAlchemy异步）
│   │   ├── redis.py              # Redis连接管理
│   │   ├── security.py           # 安全相关（JWT、bcrypt密码）
│   │   ├── logging.py            # 日志配置（loguru）
│   │   └── llm_client.py         # 大模型客户端封装（统一API调用）
│   ├── api/                      # API路由
│   │   ├── __init__.py
│   │   ├── auth.py               # 认证API（登录、刷新、登出、改密）
│   │   ├── chat.py               # 对话API（会话、消息、SSE流式）
│   │   ├── knowledge.py          # 知识库API（CRUD、上传、查询）
│   │   ├── datasources.py        # 数据源管理API
│   │   ├── metrics.py            # 指标管理API
│   │   ├── dimensions.py         # 维度管理API
│   │   ├── terms.py              # 术语管理API
│   │   ├── llm_config.py         # 大模型配置API
│   │   └── health.py             # 健康检查API
│   ├── models/                   # 数据库模型（SQLAlchemy）
│   │   ├── __init__.py
│   │   ├── user.py               # 用户模型
│   │   ├── chat.py               # 对话模型（会话、消息）
│   │   ├── knowledge.py          # 知识库模型
│   │   ├── datasource.py         # 数据源模型
│   │   ├── metric.py             # 指标模型
│   │   ├── dimension.py          # 维度模型
│   │   ├── term.py               # 术语模型
│   │   ├── llm_config.py         # 大模型配置模型
│   │   └── tracing.py            # 溯源模型（Trace、Reference、SQLTrace）
│   ├── services/                 # 业务服务层
│   │   ├── __init__.py
│   │   ├── auth_service.py       # 认证服务
│   │   ├── rag_service.py        # RAG知识问答服务（基于LlamaIndex）
│   │   ├── chatbi_service.py     # ChatBI智能问数服务
│   │   ├── routing_service.py    # 路由分发服务（意图识别+分发）
│   │   ├── tracing_service.py    # 全链路溯源服务
│   │   ├── datasource_service.py # 数据源服务
│   │   ├── metric_service.py     # 指标服务
│   │   ├── dimension_service.py  # 维度服务
│   │   ├── term_service.py       # 术语服务
│   │   └── sse_service.py        # SSE流式服务
│   ├── schemas/                  # Pydantic数据模型
│   │   ├── __init__.py
│   │   ├── auth.py               # 认证相关Schema
│   │   ├── chat.py               # 对话相关Schema
│   │   ├── knowledge.py          # 知识库相关Schema
│   │   ├── datasource.py         # 数据源Schema
│   │   ├── metric.py             # 指标Schema
│   │   ├── dimension.py          # 维度Schema
│   │   ├── term.py               # 术语Schema
│   │   └── common.py             # 通用Schema
│   ├── utils/                    # 工具函数
│   │   ├── __init__.py
│   │   ├── bm25.py               # BM25关键词检索工具
│   │   ├── sql_generator.py      # SQL生成工具
│   │   ├── sql_validator.py      # SQL校验与安全过滤工具
│   │   └── reranker.py           # 重排工具（基于bge-reranker）
│   ├── middlewares/              # 中间件
│   │   ├── __init__.py
│   │   ├── auth_middleware.py    # JWT认证中间件
│   │   ├── cors_middleware.py    # CORS中间件
│   │   └── logging_middleware.py # 日志中间件
│   └── initializers/             # 初始化器
│       ├── __init__.py
│       ├── db_init.py            # 数据库初始化与迁移
│       └── default_data.py       # 默认数据（admin账号）
├── tests/                        # 测试目录
│   ├── __init__.py
│   ├── test_auth.py              # 认证测试
│   ├── test_rag.py               # RAG测试
│   ├── test_chatbi.py            # ChatBI测试
│   └── test_chat.py              # 对话测试
├── docker/                       # Docker配置
│   ├── Dockerfile
│   └── entrypoint.sh
├── .env.example                  # 环境变量模板
├── pyproject.toml                # 项目配置
└── README.md                     # 后端说明文档
```

### 3.2 前端项目结构

```
frontend/
├── src/
│   ├── main.ts                   # 应用入口
│   ├── App.vue                   # 根组件
│   ├── router/                   # 路由配置
│   │   └── index.ts              # 路由定义与权限守卫
│   ├── stores/                   # Pinia状态管理
│   │   ├── auth.ts               # 认证状态
│   │   ├── chat.ts               # 对话状态（会话、消息、SSE连接）
│   │   ├── config.ts             # 配置状态
│   │   └── knowledge.ts          # 知识库状态
│   ├── components/               # 组件
│   │   ├── layout/               # 布局组件
│   │   │   ├── MainLayout.vue    # 主布局（左侧导航+顶部+主内容）
│   │   │   ├── Sidebar.vue       # 左侧导航栏
│   │   │   └── Header.vue        # 顶部导航
│   │   ├── auth/                 # 认证组件
│   │   │   ├── LoginForm.vue     # 登录表单
│   │   │   └── ChangePwd.vue     # 修改密码
│   │   ├── chat/                 # 对话相关组件
│   │   │   ├── ChatDialog.vue    # 主对话框
│   │   │   ├── SessionList.vue   # 会话列表
│   │   │   ├── MessageList.vue   # 消息列表
│   │   │   ├── MessageItem.vue   # 消息项
│   │   │   ├── ChatInput.vue     # 输入框
│   │   │   └── SSEStream.vue     # SSE流式组件
│   │   ├── result/               # 结果渲染组件
│   │   │   ├── KnowledgeCard.vue # 知识引用卡片
│   │   │   ├── DataTable.vue     # 数据表格
│   │   │   ├── ChartView.vue     # 图表视图
│   │   │   └── TracePanel.vue    # 溯源面板
│   │   ├── knowledge/            # 知识库组件
│   │   │   ├── KBList.vue        # 知识库列表
│   │   │   ├── KBDetail.vue      # 知识库详情
│   │   │   ├── DocUpload.vue     # 文档上传
│   │   │   └── DocList.vue       # 文档列表
│   │   ├── config/               # 数据配置组件
│   │   │   ├── DatasourceList.vue    # 数据源列表
│   │   │   ├── DatasourceForm.vue    # 数据源表单
│   │   │   ├── MetricList.vue        # 指标列表
│   │   │   ├── MetricForm.vue        # 指标表单（含SQL编辑器）
│   │   │   ├── DimensionList.vue     # 维度列表
│   │   │   ├── DimensionForm.vue     # 维度表单
│   │   │   ├── TermList.vue          # 术语列表
│   │   │   └── TermForm.vue          # 术语表单
│   │   └── common/               # 通用组件
│   │       ├── Loading.vue       # 加载动画
│   │       └── EmptyState.vue    # 空状态
│   ├── views/                    # 页面视图
│   │   ├── LoginView.vue         # 登录页面
│   │   ├── ChatView.vue          # 智能对话页面
│   │   ├── KnowledgeView.vue     # 知识管理页面
│   │   ├── DataConfigView.vue    # 数据管理页面（Tab切换）
│   │   └── SystemSettingsView.vue # 系统设置页面
│   ├── api/                      # API请求
│   │   ├── index.ts              # axios配置与拦截器
│   │   ├── auth.ts               # 认证API
│   │   ├── chat.ts               # 对话API
│   │   ├── knowledge.ts          # 知识库API
│   │   ├── datasource.ts         # 数据源API
│   │   ├── metric.ts             # 指标API
│   │   ├── dimension.ts          # 维度API
│   │   └── term.ts               # 术语API
│   ├── utils/                    # 工具函数
│   │   ├── sse.ts                # SSE连接管理
│   │   ├── format.ts             # 格式化工具
│   │   ├── storage.ts            # 本地存储工具
│   │   └── validators.ts         # 表单校验
│   ├── styles/                   # 样式文件
│   │   ├── variables.scss        # 变量定义
│   │   ├── global.scss           # 全局样式
│   │   └── reset.scss            # 重置样式
│   └── types/                    # TypeScript类型定义
│       ├── index.ts              # 通用类型
│       ├── auth.ts               # 认证类型
│       ├── chat.ts               # 对话类型
│       ├── knowledge.ts          # 知识库类型
│       └── config.ts             # 配置类型
├── public/                       # 静态资源
├── index.html                    # HTML模板
├── vite.config.ts                # Vite配置
├── tsconfig.json                 # TypeScript配置
├── package.json                  # 依赖配置
└── README.md                     # 前端说明文档
```

---

## 四、功能模块设计

### 4.1 用户认证模块

#### 功能概述
基于JWT的账号密码认证体系，默认账号admin/admin，首次登录强制改密。

#### 数据库模型
```python
class User(Base):
    id: int
    username: str           # 用户名，唯一
    password_hash: str      # bcrypt密码哈希
    role: str               # admin/user
    created_at: datetime
    last_login_at: datetime
    force_change_password: bool  # 是否强制改密
```

#### API接口
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/auth/login | 登录，返回access_token + refresh_token |
| POST | /api/auth/refresh | 刷新token |
| POST | /api/auth/logout | 登出 |
| GET | /api/auth/me | 获取当前用户信息 |
| PUT | /api/auth/change-password | 修改密码 |

---

### 4.2 系统配置管理模块

#### 4.2.1 数据源管理
**功能**：管理ChatBI所需的业务数据库连接。

**数据库模型**：
```python
class DataSource(Base):
    id: int
    name: str               # 数据源名称
    db_type: str            # mysql/postgresql/clickhouse/oracle
    host: str
    port: int
    database: str
    username: str
    password: str           # 加密存储
    pool_size: int          # 连接池大小
    created_at: datetime
    updated_at: datetime
```

**核心功能**：
- CRUD管理
- 连接测试（异步测试连通性，支持MySQL、PostgreSQL、Oracle）
- Schema同步（获取表名、字段名、字段类型、注释，支持Oracle全表扫描）
- 连接池管理

**Oracle支持说明**：
- 使用 `oracledb` 库实现Oracle数据库连接和Schema同步
- 通过 `all_tables` 和 `all_tab_columns` 视图获取表结构信息
- 支持Oracle连接池（asyncio异步连接）
- 需安装Oracle Instant Client或使用thin模式

#### 4.2.2 指标管理
**功能**：定义业务指标计算逻辑，用于NL2Metrics精准查询。

**数据库模型**：
```python
class Metric(Base):
    id: int
    name: str               # 指标名称
    code: str               # 指标编码，唯一
    datasource_id: int      # 关联数据源
    formula: str            # SQL表达式/计算逻辑
    unit: str               # 单位
    valid_range: JSON       # 合理范围 [min, max]
    description: str
    category: str           # 分组（转炉/连铸/轧钢）
    dimensions: JSON        # 关联维度列表
    created_at: datetime
    updated_at: datetime
```

**核心功能**：
- CRUD管理
- SQL编辑器（前端提供代码编辑区）
- 指标分组
- 指标测试（执行计算验证结果）

#### 4.2.3 维度管理
**功能**：定义查询维度，支持层级和枚举值。

**数据库模型**：
```python
class Dimension(Base):
    id: int
    name: str               # 维度名称
    code: str               # 维度编码
    datasource_id: int      # 关联数据源
    table_name: str         # 关联表名
    field_name: str         # 关联字段名
    hierarchy: JSON         # 维度层级定义
    enum_values: JSON       # 枚举值列表
    description: str
    created_at: datetime
```

#### 4.2.4 术语管理
**功能**：行业术语与标准字段映射，提升NL2SQL准确率。

**数据库模型**：
```python
class Term(Base):
    id: int
    term: str               # 术语名称
    standard_field: str     # 标准字段名
    synonyms: JSON          # 同义词列表
    category: str           # 分类（温度类/成分类/产量类）
    description: str
    created_at: datetime
```

#### 4.2.5 大模型配置
**功能**：配置对话、嵌入、重排使用的大模型参数。

**数据库模型**：
```python
class LLMConfig(Base):
    id: int
    config_type: str        # chat/embedding/reranker
    model_type: str         # openai/qwen/deepseek/...
    api_base: str           # API地址
    api_key: str            # 加密存储
    model_name: str         # 模型名称
    temperature: float      # 温度参数
    max_tokens: int         # 最大输出token
    is_active: bool         # 是否启用
    created_at: datetime
```

---

### 4.3 RAG工艺知识问答模块（基于LlamaIndex）

#### 数据模型
```python
class KnowledgeBase(Base):
    id: int
    name: str
    description: str
    embedding_model: str
    chunk_size: int         # 默认500
    chunk_overlap: int      # 默认100
    doc_count: int
    created_at: datetime

class Document(Base):
    id: int
    kb_id: int
    filename: str
    file_type: str          # pdf/docx/txt/md/xlsx
    file_size: int
    status: str             # pending/processing/completed/failed
    page_count: int
    segment_count: int
    metadata: JSON          # 自定义元数据
    created_at: datetime

class DocumentSegment(Base):
    id: int
    doc_id: int
    kb_id: int
    content: text
    embedding: vector       # pgvector向量
    metadata: JSON          # 页码、章节、位置
    created_at: datetime
```

#### LlamaIndex集成方案

**初始化配置**：
```python
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
import psycopg2

# 配置嵌入模型
Settings.embed_model = HuggingFaceEmbedding(model_name="bge-m3")

# 配置向量存储（pgvector）
store = PGVectorStore.from_params(
    database="steel_agent",
    host="localhost",
    password="password",
    port=5432,
    user="postgres",
    table_name="document_segment",
    embed_dim=1024,  # bge-m3输出维度
)
```

**文档加载与索引构建**：
```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader

# 加载文档（支持PDF、Word、TXT、Markdown等）
documents = SimpleDirectoryReader(
    input_dir="./uploads/kb_xxx",
    required_exts=[".pdf", ".docx", ".txt", ".md"]
).load_data()

# 构建向量索引
index = VectorStoreIndex.from_documents(
    documents,
    vector_store=store,
)

# 持久化索引
index.storage_context.persist()
```

**混合检索查询**：
```python
from llama_index.core.query_engine import HybridSearchQueryEngine
from llama_index.core.retrievers import BM25Retriever
from llama_index.core.postprocessor import SentenceTransformerRerank

# 创建向量检索器
vector_retriever = index.as_retriever(
    similarity_top_k=8,
)

# 创建BM25检索器（基于jieba中文分词）
bm25_retriever = BM25Retriever.from_defaults(
    docstore=index.docstore,
    similarity_top_k=8,
)

# 创建重排器
rerank = SentenceTransformerRerank(
    model="bge-reranker-v2-m3",
    top_n=5,
)

# 创建混合查询引擎
query_engine = HybridSearchQueryEngine(
    vector_retriever=vector_retriever,
    bm25_retriever=bm25_retriever,
    similarity_top_k=5,
    reranker=rerank,
)

# 执行查询
response = query_engine.query("转炉炼钢的脱碳方式有哪些？")
```

#### 核心流程
```
文档上传 → LlamaIndex加载 → 文本切片 → 向量化入库(pgvector)
                                                        ↓
用户提问 ← 生成回答 ← LlamaIndex查询引擎 ← 重排Rerank ← 混合检索(向量+BM25)
```

---

### 4.4 ChatBI智能问数模块

#### 双模式架构
```
用户提问 → 意图识别 → 指标匹配（NL2Metrics）
                              ↓ 匹配成功
                        按指标定义生成SQL → SQL校验 → 执行查询 → 结果解释
                              ↓ 匹配失败
                        NL2SQL生成 → SQL校验 → 安全过滤 → 执行查询 → 结果解释
```

#### SQL生成与校验

**NL2Metrics优先模式**：
```python
def query_by_metric(question: str, metric_name: str, dimensions: dict) -> dict:
    """按指标查询"""
    metric = MetricService.get_by_name(metric_name)
    sql = generate_sql_from_metric(metric, dimensions)
    result = execute_sql(metric.datasource_id, sql)
    return {
        "type": "data_table",
        "data": result,
        "sql": sql,
        "metric_name": metric.name,
    }
```

**NL2SQL兜底模式**：
```python
def query_by_nl2sql(question: str, datasource_id: int) -> dict:
    """通过NL2SQL查询"""
    schema = DatasourceService.get_schema(datasource_id)
    terms = TermService.get_all()
    
    prompt = build_nl2sql_prompt(question, schema, terms)
    sql = LLMClient.generate(prompt)
    
    if not validate_sql(sql):
        raise ValueError("SQL语法错误")
    
    if not is_safe_sql(sql):
        raise ValueError("SQL包含危险操作")
    
    result = execute_sql(datasource_id, sql)
    return {
        "type": "data_table",
        "data": result,
        "sql": sql,
    }
```

**SQL安全机制**：
- **语法校验**：使用sqlglot校验SQL语法
- **危险操作拦截**：禁止DROP、DELETE、TRUNCATE、ALTER等DDL/DML操作
- **权限控制**：仅允许SELECT查询
- **超时限制**：默认30秒超时
- **行数限制**：默认最多返回1000行

---

### 4.5 路由分发模块（技术可行性验证）

#### 意图分类（LLM驱动）

**意图分类Prompt**：
```
你是一个钢铁行业智能问答系统的意图分类器。请根据用户的问题，判断其意图类型。

意图类型：
1. KNOWLEDGE：工艺知识查询，如"转炉炼钢的工艺流程是什么"、"高炉炼铁的原理"
2. DATA：生产数据查询，如"本月转炉钢水合格率是多少"、"昨天1#转炉产量"
3. HYBRID：知识+数据混合查询，如"根据工艺规程，分析本月钢水合格率偏低的原因"

请只返回意图类型（KNOWLEDGE/DATA/HYBRID），不要返回其他内容。

用户问题：{question}
```

**意图识别服务**：
```python
class IntentClassifier:
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    async def classify(self, question: str) -> str:
        prompt = build_intent_prompt(question)
        response = await self.llm_client.generate(prompt)
        intent = response.strip().upper()
        
        if intent not in ["KNOWLEDGE", "DATA", "HYBRID"]:
            # 默认回退到知识查询
            return "KNOWLEDGE"
        
        return intent
```

#### 路由分发器

**技术方案**：
```python
class RoutingService:
    def __init__(self, rag_service, chatbi_service, llm_client):
        self.rag_service = rag_service
        self.chatbi_service = chatbi_service
        self.intent_classifier = IntentClassifier(llm_client)
    
    async def route(self, question: str) -> dict:
        """路由分发主入口"""
        intent = await self.intent_classifier.classify(question)
        
        if intent == "KNOWLEDGE":
            return await self._route_knowledge(question)
        elif intent == "DATA":
            return await self._route_data(question)
        elif intent == "HYBRID":
            return await self._route_hybrid(question)
    
    async def _route_knowledge(self, question: str) -> dict:
        """路由到RAG模块"""
        result = await self.rag_service.query(question)
        return {
            "intent": "KNOWLEDGE",
            "source": "rag",
            "result": result,
        }
    
    async def _route_data(self, question: str) -> dict:
        """路由到ChatBI模块"""
        result = await self.chatbi_service.query(question)
        return {
            "intent": "DATA",
            "source": "chatbi",
            "result": result,
        }
    
    async def _route_hybrid(self, question: str) -> dict:
        """混合查询：并行调用RAG和ChatBI，结果融合"""
        # 并行执行两个查询
        rag_task = asyncio.create_task(self.rag_service.query(question))
        chatbi_task = asyncio.create_task(self.chatbi_service.query(question))
        
        rag_result, chatbi_result = await asyncio.gather(
            rag_task, chatbi_task,
            return_exceptions=True
        )
        
        # 结果融合
        merged_result = await self._merge_results(
            question, rag_result, chatbi_result
        )
        
        return {
            "intent": "HYBRID",
            "source": "hybrid",
            "result": merged_result,
            "rag_result": rag_result if not isinstance(rag_result, Exception) else None,
            "chatbi_result": chatbi_result if not isinstance(chatbi_result, Exception) else None,
        }
    
    async def _merge_results(self, question: str, rag_result: dict, chatbi_result: dict) -> dict:
        """融合RAG和ChatBI结果"""
        # 构建融合Prompt
        merge_prompt = f"""
        请基于以下知识和数据，综合回答用户问题。
        
        用户问题：{question}
        
        知识信息：
        {rag_result.get('content', '') if rag_result else '无'}
        
        数据信息：
        {chatbi_result.get('data', '') if chatbi_result else '无'}
        
        请输出综合分析回答，同时说明哪些内容来自知识、哪些来自数据。
        """
        
        merged_content = await self.llm_client.generate(merge_prompt)
        
        return {
            "content": merged_content,
            "rag_references": rag_result.get('references', []) if rag_result else [],
            "chatbi_sql": chatbi_result.get('sql', '') if chatbi_result else '',
        }
```

#### 技术可行性验证

| 技术点 | 方案 | 可行性 | 风险点 |
|--------|------|--------|--------|
| LLM意图分类 | 调用大模型API，few-shot示例 | 高 | 分类准确率依赖模型，需准备示例 |
| 并行调用 | asyncio.create_task + gather | 高 | 需要处理单个任务失败的情况 |
| 结果融合 | LLM重新生成综合回答 | 高 | 融合质量依赖模型能力 |
| Fallback机制 | try-catch + 默认路由 | 高 | 需定义明确的降级策略 |

**优化策略**：
1. **意图分类优化**：使用few-shot示例提升准确率，准备钢铁行业场景的示例问题
2. **超时控制**：为每个子任务设置超时，避免整体阻塞
3. **错误处理**：单个子任务失败不影响整体，使用Exception返回
4. **缓存机制**：对重复问题的意图分类结果进行缓存

---

### 4.6 对话管理与SSE

#### 数据模型
```python
class Session(Base):
    id: int
    user_id: int
    title: str              # 会话标题（首条消息摘要）
    message_count: int
    created_at: datetime
    updated_at: datetime

class Message(Base):
    id: int
    session_id: int
    role: str               # user/assistant
    content: text
    msg_type: str           # text/data_table/chart/reference
    metadata: JSON          # 引用、溯源等附加信息
    created_at: datetime
```

#### SSE消息格式
```json
{
  "type": "text",           // text / data_table / chart / reference / error / finish
  "content": "回答内容...",
  "source": "rag",          // rag / chatbi / hybrid
  "metadata": {},
  "timestamp": "2024-01-01T12:00:00Z"
}
```

#### SSE实现方案
```python
async def chat_stream(session_id: int, question: str):
    """SSE流式对话"""
    async for chunk in routing_service.stream_route(question):
        yield {
            "type": chunk["type"],
            "content": chunk["content"],
            "source": chunk["source"],
            "metadata": chunk.get("metadata", {}),
            "timestamp": datetime.now().isoformat(),
        }
```

---

### 4.7 全链路溯源模块

#### 数据模型
```python
class Trace(Base):
    id: int
    session_id: int
    message_id: int
    step: str               # 步骤名称
    step_type: str          # intent/rag/chatbi/merge
    input_data: JSON
    output_data: JSON
    execution_time: float   # 执行耗时（秒）
    timestamp: datetime

class Reference(Base):
    id: int
    trace_id: int
    doc_id: int
    segment_id: int
    content: text
    confidence: float
    source_info: JSON       # 文档名、页码、章节

class SQLTrace(Base):
    id: int
    trace_id: int
    sql_statement: text
    execution_time: float
    row_count: int
    affected_tables: JSON
    datasource_id: int
```

---

## 五、API接口汇总

### 5.1 认证接口
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/auth/login | 登录 |
| POST | /api/auth/refresh | 刷新token |
| POST | /api/auth/logout | 登出 |
| GET | /api/auth/me | 获取用户信息 |
| PUT | /api/auth/change-password | 修改密码 |

### 5.2 对话接口
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/chat/sessions | 创建会话 |
| GET | /api/chat/sessions | 获取会话列表 |
| GET | /api/chat/sessions/{id} | 获取会话详情 |
| DELETE | /api/chat/sessions/{id} | 删除会话 |
| GET | /api/chat/search | 搜索历史会话 |
| POST | /api/chat/sessions/{id}/messages | 发送消息（同步） |
| GET | /api/chat/sessions/{id}/stream | SSE流式对话 |
| GET | /api/chat/sessions/{id}/messages | 获取消息列表 |

### 5.3 知识库接口
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/knowledge | 创建知识库 |
| GET | /api/knowledge | 获取知识库列表 |
| GET | /api/knowledge/{id} | 获取知识库详情 |
| PUT | /api/knowledge/{id} | 更新知识库 |
| DELETE | /api/knowledge/{id} | 删除知识库 |
| POST | /api/knowledge/{id}/documents | 上传文档 |
| GET | /api/knowledge/{id}/documents | 获取文档列表 |
| DELETE | /api/knowledge/{id}/documents/{doc_id} | 删除文档 |
| POST | /api/knowledge/{id}/rebuild-index | 重建索引 |
| POST | /api/knowledge/query | 知识问答 |

### 5.4 数据配置接口
| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/datasources | 创建数据源 |
| GET | /api/datasources | 获取数据源列表 |
| GET | /api/datasources/{id} | 获取数据源详情 |
| PUT | /api/datasources/{id} | 更新数据源 |
| DELETE | /api/datasources/{id} | 删除数据源 |
| POST | /api/datasources/{id}/test | 测试连接 |
| POST | /api/datasources/{id}/sync-schema | 同步Schema |
| POST | /api/metrics | 创建指标 |
| GET | /api/metrics | 获取指标列表 |
| PUT | /api/metrics/{id} | 更新指标 |
| DELETE | /api/metrics/{id} | 删除指标 |
| POST | /api/dimensions | 创建维度 |
| GET | /api/dimensions | 获取维度列表 |
| PUT | /api/dimensions/{id} | 更新维度 |
| DELETE | /api/dimensions/{id} | 删除维度 |
| POST | /api/terms | 创建术语 |
| GET | /api/terms | 获取术语列表 |
| PUT | /api/terms/{id} | 更新术语 |
| DELETE | /api/terms/{id} | 删除术语 |
| GET | /api/llm-config | 获取大模型配置 |
| PUT | /api/llm-config | 更新大模型配置 |

### 5.5 健康检查
| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/health | 健康检查 |

---

## 六、部署方案

### 6.1 Docker Compose部署

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    container_name: steel-agent-backend
    ports:
      - "8000:8000"
    environment:
      - MYSQL_URL=mysql+pymysql://root:password@mysql:3306/steel_agent
      - POSTGRES_URL=postgresql+asyncpg://postgres:password@postgres:5432/steel_agent
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=your-secret-key
    volumes:
      - ./backend/uploads:/app/uploads
    depends_on:
      - mysql
      - postgres
      - redis
    networks:
      - steel-agent-net

  frontend:
    build: ./frontend
    container_name: steel-agent-frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000
    depends_on:
      - backend
    networks:
      - steel-agent-net

  mysql:
    image: mysql:8.0
    container_name: steel-agent-mysql
    ports:
      - "3306:3306"
    environment:
      - MYSQL_ROOT_PASSWORD=password
      - MYSQL_DATABASE=steel_agent
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - steel-agent-net

  postgres:
    image: pgvector/pgvector:pg16
    container_name: steel-agent-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=steel_agent
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - steel-agent-net

  redis:
    image: redis:7.2-alpine
    container_name: steel-agent-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - steel-agent-net

volumes:
  mysql_data:
  postgres_data:
  redis_data:

networks:
  steel-agent-net:
    driver: bridge
```

### 6.2 环境变量模板（.env.example）

```bash
# ========== 数据库配置 ==========
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=@Maxwell2024
MYSQL_DB=steel_agent

# PostgreSQL (pgvector)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=steel_agent

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# ========== 大模型配置 ==========
# 对话模型
CHAT_MODEL_TYPE=qwen          # openai / qwen / deepseek
CHAT_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
CHAT_API_KEY=your-api-key
CHAT_MODEL_NAME=qwen2.5-72b-instruct
CHAT_TEMPERATURE=0.7
CHAT_MAX_TOKENS=2048

# 嵌入模型
EMBEDDING_MODEL_TYPE=local    # openai / qwen / local
EMBEDDING_API_BASE=
EMBEDDING_API_KEY=
EMBEDDING_MODEL_NAME=bge-m3

# 重排模型
RERANKER_ENABLED=true
RERANKER_MODEL_TYPE=local     # openai / qwen / local
RERANKER_MODEL_NAME=bge-reranker-v2-m3

# ========== JWT配置 ==========
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ========== 应用配置 ==========
APP_HOST=0.0.0.0
APP_PORT=8000
APP_WORKERS=1
DEBUG=false
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=104857600    # 100MB

# ========== RAG配置 ==========
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=8
RAG_SIMILARITY_THRESHOLD=0.6
RAG_RERANKING_ENABLED=true
RAG_RERANK_TOP_K=5

# ========== ChatBI配置 ==========
CHATBI_SQL_TIMEOUT=30
CHATBI_MAX_ROWS=1000
CHATBI_USE_NL2METRICS_FIRST=true
```

---

## 七、MVP版本规划（重新梳理）

### 7.1 MVP必做功能（可启动、可使用、核心链路完整）

**核心功能（必须完成，否则系统不可用）**：
1. **用户认证**：admin/admin登录、JWT鉴权、改密
2. **系统配置**：数据源管理（连接测试）、指标管理、维度管理、术语管理、大模型配置
3. **RAG知识问答**：知识库管理、文档上传解析、向量检索、知识问答（混合检索和重排可v1.1完善）
4. **ChatBI智能问数**：NL2Metrics指标查询、NL2SQL兜底、SQL安全、数据表格展示（图表可v1.1完善）
5. **路由分发**：意图识别（知识/数据/混合）、路由分发、混合分析（简化版：串行执行而非并行）
6. **对话管理**：会话管理、多轮上下文、SSE流式响应、历史会话搜索
7. **全链路溯源**：文档引用溯源、SQL溯源、执行链路日志（基础版本）
8. **前端管理后台**：登录页、对话页、知识库管理、数据管理页、系统设置页
9. **部署支持**：Docker Compose一键部署、健康检查

**MVP简化策略**：
- RAG：先实现纯向量检索，混合检索和重排作为v1.1优化
- ChatBI：先实现基本图表（柱状图、折线图），更多图表类型v1.1扩展
- 路由：混合查询先串行执行（保证正确性），并行执行v1.1优化
- 溯源：基础版本，完整血缘追踪v1.1完善

### 7.2 v1.1增强功能（后续迭代）

**功能增强**：
1. **RAG优化**：混合检索（向量+BM25 RRF融合）、重排Rerank、多Query扩展
2. **ChatBI优化**：更多图表类型（饼图、仪表盘、地图等）、图表自动推荐、数据导出
3. **路由优化**：混合查询并行执行、意图分类few-shot优化、缓存机制
4. **溯源增强**：完整数据血缘追踪、执行链路可视化、审计日志
5. **技能包引擎**：SKILL.md规范、执行引擎、Rules约束、技能包管理界面、对话集成
6. **更多文档格式**：OCR扫描件、PPT
7. **用户权限**：多用户、角色权限管理

---

## 八、安全考虑

### 8.1 认证安全
- JWT token过期机制（access_token 1小时，refresh_token 7天）
- 密码使用bcrypt加密存储
- 首次登录强制修改默认密码
- Token刷新机制

### 8.2 SQL安全
- SQL语法校验（sqlglot）
- 危险操作拦截（DROP、DELETE、TRUNCATE等）
- 仅允许SELECT查询
- 参数化查询，防止SQL注入
- 查询超时限制
- 返回行数限制

### 8.3 数据安全
- 敏感数据加密存储（密码、API Key）
- HTTPS传输加密
- 最小权限原则
- 操作审计日志

### 8.4 大模型安全
- 指标合理范围校验
- 敏感信息过滤
- 输出内容审核

---

## 九、前后端交互逻辑

### 9.1 登录流程
```
前端 → POST /api/auth/login → 后端验证 → 返回token → 前端存储token → 跳转首页
```

### 9.2 对话流程（SSE流式）
```
前端 → GET /api/chat/sessions/{id}/stream → 后端建立SSE连接
前端发送问题 → 后端路由分发 → 执行查询 → SSE逐帧推送结果 → 前端流式渲染
```

### 9.3 知识库文档上传流程
```
前端上传文档 → POST /api/knowledge/{id}/documents → 后端接收文件
后端 → LlamaIndex加载 → 文本切片 → 向量化入库 → 更新文档状态 → 前端显示进度
```

### 9.4 数据源配置流程
```
前端填写表单 → POST /api/datasources → 后端保存配置
前端点击测试连接 → POST /api/datasources/{id}/test → 后端测试 → 返回结果
前端点击同步Schema → POST /api/datasources/{id}/sync-schema → 后端获取表结构 → 返回前端
```

### 9.5 指标查询流程（NL2Metrics）
```
前端发送问题 → 后端意图识别 → 指标匹配 → 生成SQL → 执行查询 → 返回结果（数据表格+图表）
```

### 9.6 混合查询流程（MVP简化版）
```
前端发送问题 → 后端意图识别（HYBRID）
              → 串行执行RAG查询 → 串行执行ChatBI查询
              → LLM融合结果 → 返回前端（知识引用+数据表格+综合分析）
```

---

## 十、核心依赖清单

### 后端核心依赖（pyproject.toml）
```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115.0"
uvicorn = "^0.30.0"
sqlalchemy = "^2.0.0"
asyncpg = "^0.29.0"          # PostgreSQL异步驱动
aiomysql = "^0.2.0"          # MySQL异步驱动
redis = "^5.0.0"
python-jose = "^3.3.0"       # JWT
passlib = "^1.7.4"           # bcrypt密码加密
bcrypt = "^4.0.0"
pydantic-settings = "^2.0.0"
loguru = "^0.7.0"
python-multipart = "^0.0.6"  # 文件上传
sqlglot = "^18.0.0"          # SQL语法校验
llama-index-core = "^0.11.0"
llama-index-embeddings-huggingface = "^0.1.0"
llama-index-vector-stores-postgres = "^0.1.0"
transformers = "^4.40.0"
sentence-transformers = "^3.0.0"
jieba = "^0.42.1"
aiohttp = "^3.9.0"
python-dotenv = "^1.0.0"
```

### 前端核心依赖（package.json）
```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.2.0",
    "element-plus": "^2.8.0",
    "axios": "^1.6.0",
    "echarts": "^5.5.0",
    "@vueuse/core": "^10.0.0",
    "highlight.js": "^11.9.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "typescript": "^5.3.0",
    "vite": "^6.5.0",
    "sass": "^1.70.0",
    "@types/node": "^20.0.0"
  }
}
```
