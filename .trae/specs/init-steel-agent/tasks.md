# Tasks

## 阶段一：项目骨架与用户认证（MVP必须）

- [ ] Task 1: 初始化项目工程结构
  - [ ] SubTask 1.1: 创建后端工程目录结构（app/、api/、core/、models/、services/、schemas/、utils/、middlewares/）
  - [ ] SubTask 1.2: 初始化前端工程（Vue3 + Vite + Element Plus + Pinia + VueRouter）
  - [ ] SubTask 1.3: 创建Docker Compose编排（FastAPI、Vue、MySQL、PostgreSQL/pgvector、Redis）
  - [ ] SubTask 1.4: 编写FastAPI应用入口与基础中间件（CORS、异常处理、日志）

- [ ] Task 2: 配置管理与基础服务层
  - [ ] SubTask 2.1: 实现统一配置管理（pydantic-settings，支持env和yaml）
  - [ ] SubTask 2.2: 实现数据库连接管理（SQLAlchemy异步、MySQL、PostgreSQL/pgvector）
  - [ ] SubTask 2.3: 实现Redis连接管理（缓存、会话存储）
  - [ ] SubTask 2.4: 实现大模型客户端封装（统一API调用，支持OpenAI/国产模型切换）

- [ ] Task 3: 用户认证模块（默认admin/admin）
  - [ ] SubTask 3.1: 创建用户模型与数据库迁移
  - [ ] SubTask 3.2: 实现密码加密（bcrypt）与JWT token生成/验证
  - [ ] SubTask 3.3: 实现认证API（登录、刷新、登出、获取用户信息、修改密码）
  - [ ] SubTask 3.4: 实现JWT认证中间件
  - [ ] SubTask 3.5: 实现默认admin/admin账号初始化与首次登录强制改密
  - [ ] SubTask 3.6: 前端登录页面实现

## 阶段二：系统配置管理（MVP必须，ChatBI前置依赖）

- [ ] Task 4: 数据源管理
  - [ ] SubTask 4.1: 创建数据源模型（DataSource）与CRUD API
  - [ ] SubTask 4.2: 实现数据库连接测试功能（支持MySQL、PostgreSQL、Oracle）
  - [ ] SubTask 4.3: 实现Schema同步（获取表名、字段名、字段类型，支持Oracle全表扫描）
  - [ ] SubTask 4.4: 前端数据源管理页面（列表、新增/编辑弹窗、测试连接、Schema同步）
  - [ ] SubTask 4.5: Oracle数据库支持（连接池、Schema同步、all_tables/all_tab_columns视图查询）

- [ ] Task 5: 指标与维度管理
  - [ ] SubTask 5.1: 创建指标模型（Metric）与CRUD API
  - [ ] SubTask 5.2: 创建维度模型（Dimension）与CRUD API
  - [ ] SubTask 5.3: 实现指标分组功能
  - [ ] SubTask 5.4: 前端指标管理页面（列表、新增/编辑、SQL编辑器）
  - [ ] SubTask 5.5: 前端维度管理页面（列表、新增/编辑、层级配置）

- [ ] Task 6: 术语管理
  - [ ] SubTask 6.1: 创建术语模型（Term）与CRUD API
  - [ ] SubTask 6.2: 实现同义词管理
  - [ ] SubTask 6.3: 前端术语管理页面（列表、新增/编辑、同义词配置）

- [ ] Task 7: 大模型配置
  - [ ] SubTask 7.1: 创建大模型配置模型（LLMConfig）与API
  - [ ] SubTask 7.2: 实现配置动态加载与生效
  - [ ] SubTask 7.3: 前端系统设置页面（大模型配置、账号设置）

## 阶段三：RAG工艺知识问答（MVP必须，基于LlamaIndex）

- [ ] Task 8: 文档解析与切片引擎（基于LlamaIndex）
  - [ ] SubTask 8.1: 创建知识库数据模型（KnowledgeBase、Document、DocumentSegment）
  - [ ] SubTask 8.2: 基于LlamaIndex SimpleDirectoryReader实现多格式文档加载
  - [ ] SubTask 8.3: 配置LlamaIndex嵌入模型（bge-m3）与pgvector存储
  - [ ] SubTask 8.4: 实现文本切片（chunk_size/chunk_overlap可配置）

- [ ] Task 9: 向量索引与检索引擎（基于LlamaIndex）
  - [ ] SubTask 9.1: 实现向量索引构建（LlamaIndex VectorStoreIndex + PGVectorStore）
  - [ ] SubTask 9.2: 实现向量检索查询（MVP：纯向量检索）
  - [ ] SubTask 9.3: 预留混合检索扩展点（v1.1：HybridSearchQueryEngine）
  - [ ] SubTask 9.4: 预留重排扩展点（v1.1：SentenceTransformerRerank）

- [ ] Task 10: 知识库管理与问答API
  - [ ] SubTask 10.1: 实现知识库管理API（创建、删除、列表、详情）
  - [ ] SubTask 10.2: 实现文档上传API（批量上传、处理进度、状态更新）
  - [ ] SubTask 10.3: 实现知识问答API（向量检索+生成回答+引用标注）
  - [ ] SubTask 10.4: 前端知识库管理页面（知识库列表、文档列表、文档上传、索引状态）

## 阶段四：ChatBI智能问数（MVP必须）

- [ ] Task 11: NL2Metrics指标查询引擎
  - [ ] SubTask 11.1: 实现指标语义匹配（基于用户问题匹配预定义指标）
  - [ ] SubTask 11.2: 实现指标SQL生成（基于指标定义+维度过滤）
  - [ ] SubTask 11.3: 实现查询结果格式化

- [ ] Task 12: NL2SQL兜底引擎
  - [ ] SubTask 12.1: 实现Schema Linking（从问题识别需要的表和字段）
  - [ ] SubTask 12.2: 实现NL2SQL Prompt模板（结合Schema、术语、指标）
  - [ ] SubTask 12.3: 实现SQL语法校验（sqlglot）
  - [ ] SubTask 12.4: 实现SQL安全过滤（拦截DROP/DELETE/TRUNCATE等）
  - [ ] SubTask 12.5: 实现执行控制（超时限制30秒、返回行数限制1000行）

- [ ] Task 13: ChatBI问答API
  - [ ] SubTask 13.1: 实现智能问数API（NL2Metrics优先 + NL2SQL兜底）
  - [ ] SubTask 13.2: 实现SQL溯源记录
  - [ ] SubTask 13.3: 实现结果解释生成（自然语言描述）

## 阶段五：路由分发与对话管理（MVP必须）

- [ ] Task 14: 路由分发层（MVP简化：串行执行）
  - [ ] SubTask 14.1: 实现意图识别模块（知识/数据/混合 三分类，基于LLM）
  - [ ] SubTask 14.2: 实现路由分发器（按意图分发到对应通道）
  - [ ] SubTask 14.3: 实现混合分析引擎（MVP：串行调用RAG+ChatBI，结果融合）
  - [ ] SubTask 14.4: 实现Fallback机制
  - [ ] SubTask 14.5: 预留并行执行扩展点（v1.1：asyncio并行调用）

- [ ] Task 15: 多轮对话与会话管理
  - [ ] SubTask 15.1: 创建会话与消息模型（Session、Message）
  - [ ] SubTask 15.2: 实现会话管理API（创建、列表、详情、删除、搜索）
  - [ ] SubTask 15.3: 实现上下文管理（窗口限制、压缩摘要、意图追踪）
  - [ ] SubTask 15.4: 实现全链路溯源记录（Trace、Reference、SQLTrace模型）

- [ ] Task 16: SSE流式响应
  - [ ] SubTask 16.1: 实现SSE流式输出框架（消息格式、心跳、错误处理）
  - [ ] SubTask 16.2: 实现对话流式API（调用路由分发+流式推送结果）
  - [ ] SubTask 16.3: 前端SSE流式组件（逐字渲染、消息类型处理）

## 阶段六：前端管理后台（MVP必须）

- [ ] Task 17: 前端整体布局与路由
  - [ ] SubTask 17.1: 实现主布局组件（左侧导航栏 + 顶部导航 + 主内容区）
  - [ ] SubTask 17.2: 实现路由配置与权限守卫（智能对话、知识管理、数据管理、系统设置）
  - [ ] SubTask 17.3: 实现Pinia状态管理（auth、chat、config、knowledge）
  - [ ] SubTask 17.4: 实现设计规范（配色方案、组件样式、品牌标识「Steel Industry AI Assistant」）

- [ ] Task 18: 智能对话页面
  - [ ] SubTask 18.1: 实现左侧历史会话栏（新建按钮、会话列表、搜索）
  - [ ] SubTask 18.2: 实现消息列表组件（用户消息、AI回答、流式渲染）
  - [ ] SubTask 18.3: 实现输入框组件（多行输入、Enter发送）
  - [ ] SubTask 18.4: 实现消息渲染器（知识卡片、数据表格、图表、溯源信息）

- [ ] Task 19: 知识管理页面
  - [ ] SubTask 19.1: 实现知识库列表（卡片式展示、文档数、创建时间）
  - [ ] SubTask 19.2: 实现知识库详情（文档列表、状态、页数）
  - [ ] SubTask 19.3: 实现文档上传组件（拖拽上传、进度条、批量上传）
  - [ ] SubTask 19.4: 实现索引状态展示

- [ ] Task 20: 数据管理页面
  - [ ] SubTask 20.1: 实现数据源管理Tab（列表、新增/编辑、测试连接、Schema同步）
  - [ ] SubTask 20.2: 实现指标管理Tab（列表、新增/编辑、SQL编辑器、指标分组）
  - [ ] SubTask 20.3: 实现维度管理Tab（列表、新增/编辑、层级配置）
  - [ ] SubTask 20.4: 实现术语管理Tab（列表、新增/编辑、同义词管理）

- [ ] Task 21: 系统设置页面
  - [ ] SubTask 21.1: 实现模型配置Tab（Xinference配置、NewAPI配置、参数展示）
  - [ ] SubTask 21.2: 实现账号设置Tab（修改密码、个人信息）

- [ ] Task 22: 数据可视化组件
  - [ ] SubTask 22.1: 实现数据表格组件（分页、排序、筛选）
  - [ ] SubTask 22.2: 实现Echarts图表组件（柱状图、折线图）
  - [ ] SubTask 22.3: 预留更多图表类型扩展点（v1.1：饼图、仪表盘等）

## 阶段七：部署与测试

- [ ] Task 23: 私有化部署支持
  - [ ] SubTask 23.1: 完善Docker Compose配置（环境变量、数据卷、网络）
  - [ ] SubTask 23.2: 实现健康检查API
  - [ ] SubTask 23.3: 编写部署文档与配置指南
  - [ ] SubTask 23.4: 实现启动自检流程

- [ ] Task 24: 集成测试
  - [ ] SubTask 24.1: 用户认证模块测试（登录、鉴权、改密）
  - [ ] SubTask 24.2: 系统配置模块测试（数据源、指标、维度、术语）
  - [ ] SubTask 24.3: RAG全流程测试（文档入库→向量检索→问答→溯源）
  - [ ] SubTask 24.4: ChatBI全流程测试（NL2Metrics/NL2SQL→校验→执行→结果解释）
  - [ ] SubTask 24.5: 对话API测试（SSE流式、会话管理、意图路由）
  - [ ] SubTask 24.6: 端到端混合查询场景测试（串行执行、溯源验证）

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 2
- Task 5 depends on Task 4
- Task 6 depends on Task 4
- Task 7 depends on Task 2
- Task 8 depends on Task 2
- Task 9 depends on Task 8
- Task 10 depends on Task 9
- Task 11 depends on Task 5
- Task 12 depends on Task 4, Task 6
- Task 13 depends on Task 11, Task 12
- Task 14 depends on Task 10, Task 13
- Task 15 depends on Task 14
- Task 16 depends on Task 15
- Task 17 depends on Task 3
- Task 18 depends on Task 16, Task 17
- Task 19 depends on Task 17
- Task 20 depends on Task 17
- Task 21 depends on Task 17
- Task 22 depends on Task 18
- Task 23 depends on Task 22
- Task 24 depends on Task 23

# v1.1 增强功能（MVP之后迭代）
- RAG优化：混合检索（向量+BM25 RRF融合）、重排Rerank、多Query扩展
- ChatBI优化：更多图表类型（饼图、仪表盘等）、图表自动推荐、数据导出
- 路由优化：混合查询并行执行、意图分类few-shot优化、缓存机制
- 溯源增强：完整数据血缘追踪、执行链路可视化、审计日志
- 技能包引擎：SKILL.md规范、执行引擎、Rules约束、技能包管理界面、对话集成
- 更多文档格式：OCR扫描件、PPT
- 用户权限：多用户、角色权限管理
