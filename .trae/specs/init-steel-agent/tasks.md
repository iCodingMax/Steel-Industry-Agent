# Tasks

## 阶段一：项目骨架与用户认证（MVP必须）✅ 已完成

- [x] Task 1: 初始化项目工程结构
  - [x] SubTask 1.1: 创建后端工程目录结构（app/、api/、core/、models/、services/、schemas/、utils/、middlewares/）
  - [x] SubTask 1.2: 初始化前端工程（Vue3 + Vite + Element Plus + Pinia + VueRouter）
  - [x] SubTask 1.3: 创建Docker Compose编排（FastAPI、Vue、PostgreSQL/pgvector、MySQL、Redis）
  - [x] SubTask 1.4: 编写FastAPI应用入口与基础中间件（CORS、异常处理、日志）

- [x] Task 2: 配置管理与基础服务层
  - [x] SubTask 2.1: 实现统一配置管理（pydantic-settings，双数据库配置）
  - [x] SubTask 2.2: 实现数据库连接管理（SQLAlchemy异步、PostgreSQL系统库+MySQL业务库）
  - [x] SubTask 2.3: 实现Redis连接管理（缓存、会话存储）
  - [x] SubTask 2.4: 实现Xinference客户端封装（统一API调用，支持嵌入/重排/对话模型）

- [x] Task 3: 用户认证模块（默认admin/admin）
  - [x] SubTask 3.1: 创建用户模型与数据库迁移
  - [x] SubTask 3.2: 实现密码加密（bcrypt）与JWT token生成/验证
  - [x] SubTask 3.3: 实现认证API（登录、刷新、登出、获取用户信息、修改密码）
  - [x] SubTask 3.4: 实现JWT认证中间件
  - [x] SubTask 3.5: 实现默认admin/admin账号初始化
  - [x] SubTask 3.6: 前端登录页面实现

## 阶段二：系统配置管理（MVP必须，ChatBI前置依赖）✅ 已完成

- [x] Task 4: 数据源管理
  - [x] SubTask 4.1: 创建数据源模型（DataSource）与CRUD API
  - [x] SubTask 4.2: 实现数据库连接测试功能（支持MySQL、PostgreSQL、Oracle）
  - [x] SubTask 4.3: 实现Schema同步（获取表名、字段名、字段类型，支持Oracle全表扫描）
  - [x] SubTask 4.4: 前端数据源管理页面（列表、新增/编辑弹窗、测试连接、Schema同步）
  - [x] SubTask 4.5: Oracle数据库支持（连接池、Schema同步、all_tables/all_tab_columns视图查询）

- [x] Task 5: 指标与维度管理
  - [x] SubTask 5.1: 创建指标模型（Metric）与CRUD API
  - [x] SubTask 5.2: 创建维度模型（Dimension）与CRUD API
  - [x] SubTask 5.3: 实现指标分组功能
  - [x] SubTask 5.4: 前端指标管理页面（列表、新增/编辑、SQL编辑器）
  - [x] SubTask 5.5: 前端维度管理页面（列表、新增/编辑、层级配置）

- [x] Task 6: 术语管理
  - [x] SubTask 6.1: 创建术语模型（Term）与CRUD API
  - [x] SubTask 6.2: 实现同义词管理
  - [x] SubTask 6.3: 前端术语管理页面（列表、新增/编辑、同义词配置）

- [x] Task 7: 大模型配置（Xinference）
  - [x] SubTask 7.1: 创建大模型配置模型（LLMConfig）与API
  - [x] SubTask 7.2: 实现配置动态加载与生效
  - [x] SubTask 7.3: 前端系统设置页面（Xinference模型配置、账号设置）

## 阶段三：RAG工艺知识问答（MVP必须，基于LlamaIndex）✅ 已完成

- [x] Task 8: 文档解析与切片引擎（基于LlamaIndex）
  - [x] SubTask 8.1: 创建知识库数据模型（KnowledgeBase、Document、DocumentSegment）
  - [x] SubTask 8.2: 基于LlamaIndex SimpleDirectoryReader实现多格式文档加载
  - [x] SubTask 8.3: 配置LlamaIndex嵌入模型（通过Xinference调用bge-m3）与pgvector存储
  - [x] SubTask 8.4: 实现文本切片（chunk_size/chunk_overlap可配置）
  - [x] SubTask 8.5: 向量检索去重优化（基于segment_id去重）

- [x] Task 9: 向量索引与检索引擎（基于LlamaIndex）
  - [x] SubTask 9.1: 实现向量索引构建（LlamaIndex VectorStoreIndex + PGVectorStore）
  - [x] SubTask 9.2: 实现混合检索查询（向量+BM25）
  - [x] SubTask 9.3: 实现重排Rerank（通过Xinference调用bge-reranker-large）

- [x] Task 10: 知识库管理与问答API
  - [x] SubTask 10.1: 实现知识库管理API（创建、删除、列表、详情）
  - [x] SubTask 10.2: 实现文档上传API（批量上传、处理进度、状态更新）
  - [x] SubTask 10.3: 实现知识问答API（混合检索+生成回答+引用标注）
  - [x] SubTask 10.4: 前端知识库管理页面（知识库列表、文档列表、文档上传、索引状态）

## 阶段四：ChatBI智能问数（MVP必须）✅ 已完成

- [x] Task 11: NL2Metrics指标查询引擎
  - [x] SubTask 11.1: 实现指标语义匹配（基于用户问题匹配预定义指标）
  - [x] SubTask 11.2: 实现指标SQL生成（基于指标定义+维度过滤）
  - [x] SubTask 11.3: 实现查询结果格式化

- [x] Task 12: NL2SQL兜底引擎（通过Xinference）
  - [x] SubTask 12.1: 实现Schema Linking（从问题识别需要的表和字段）
  - [x] SubTask 12.2: 实现NL2SQL Prompt模板（结合Schema、术语、指标）
  - [x] SubTask 12.3: 实现SQL语法校验（sqlglot）
  - [x] SubTask 12.4: 实现SQL安全过滤（拦截DROP/DELETE/TRUNCATE等）
  - [x] SubTask 12.5: 实现执行控制（超时限制30秒、返回行数限制1000行）
  - [x] SubTask 12.6: 通过Xinference调用LLM生成SQL
  - [x] SubTask 12.7: 智能表筛选（基于钢铁行业关键词匹配相关表）

- [x] Task 13: ChatBI问答API
  - [x] SubTask 13.1: 实现智能问数API（NL2Metrics优先 + NL2SQL兜底）
  - [x] SubTask 13.2: 实现SQL溯源记录
  - [x] SubTask 13.3: 实现结果解释生成（自然语言描述）

## 阶段五：路由分发与对话管理（MVP必须）✅ 已完成

- [x] Task 14: 路由分发层（并行执行）
  - [x] SubTask 14.1: 实现意图识别模块（知识/数据/混合 三分类，通过Xinference调用LLM）
  - [x] SubTask 14.2: 实现路由分发器（按意图分发到对应通道）
  - [x] SubTask 14.3: 实现混合分析引擎（并行调用RAG+ChatBI，结果融合）
  - [x] SubTask 14.4: 实现Fallback机制

- [x] Task 15: 多轮对话与会话管理
  - [x] SubTask 15.1: 创建会话与消息模型（Session、Message）
  - [x] SubTask 15.2: 实现会话管理API（创建、列表、详情、删除、搜索）
  - [x] SubTask 15.3: 实现上下文管理（窗口限制、压缩摘要、意图追踪）
  - [x] SubTask 15.4: 实现全链路溯源记录（Trace、Reference、SQLTrace模型）

- [x] Task 16: SSE流式响应
  - [x] SubTask 16.1: 实现SSE流式输出框架（消息格式、心跳、错误处理）
  - [x] SubTask 16.2: 实现对话流式API（调用路由分发+流式推送结果）
  - [x] SubTask 16.3: 前端SSE流式组件（逐字渲染、消息类型处理）

## 阶段六：前端管理后台（MVP必须）✅ 已完成

- [x] Task 17: 前端整体布局与路由
  - [x] SubTask 17.1: 实现主布局组件（左侧导航栏 + 顶部导航 + 主内容区）
  - [x] SubTask 17.2: 实现路由配置与权限守卫（智能对话、知识管理、数据管理、系统设置）
  - [x] SubTask 17.3: 实现Pinia状态管理（auth、chat、config、knowledge）
  - [x] SubTask 17.4: 实现设计规范（配色方案、组件样式、品牌标识「Steel Industry AI Assistant」）

- [x] Task 18: 智能对话页面
  - [x] SubTask 18.1: 实现左侧历史会话栏（新建按钮、会话列表、搜索）
  - [x] SubTask 18.2: 实现消息列表组件（用户消息、AI回答、流式渲染）
  - [x] SubTask 18.3: 实现输入框组件（多行输入、Enter发送）
  - [x] SubTask 18.4: 实现消息渲染器（知识卡片、数据表格、图表、溯源信息）

- [x] Task 19: 知识管理页面
  - [x] SubTask 19.1: 实现知识库列表（卡片式展示、文档数、创建时间）
  - [x] SubTask 19.2: 实现知识库详情（文档列表、状态、页数）
  - [x] SubTask 19.3: 实现文档上传组件（拖拽上传、进度条、批量上传）
  - [x] SubTask 19.4: 实现索引状态展示

- [x] Task 20: 数据管理页面
  - [x] SubTask 20.1: 实现数据源管理Tab（列表、新增/编辑、测试连接、Schema同步）
  - [x] SubTask 20.2: 实现指标管理Tab（列表、新增/编辑、SQL编辑器、指标分组）
  - [x] SubTask 20.3: 实现维度管理Tab（列表、新增/编辑、层级配置）
  - [x] SubTask 20.4: 实现术语管理Tab（列表、新增/编辑、同义词管理）

- [x] Task 21: 系统设置页面
  - [x] SubTask 21.1: 实现模型配置Tab（Xinference配置、模型参数展示）
  - [x] SubTask 21.2: 实现账号设置Tab（修改密码、个人信息）

- [x] Task 22: 数据可视化组件
  - [x] SubTask 22.1: 实现数据表格组件（分页、排序、筛选）
  - [x] SubTask 22.2: 实现Echarts图表组件（柱状图、折线图）

## 阶段七：部署与测试 ✅ 已完成

- [x] Task 23: 私有化部署支持
  - [x] SubTask 23.1: 完善Docker Compose配置（环境变量、数据卷、网络）
  - [x] SubTask 23.2: 实现健康检查API
  - [x] SubTask 23.3: 编写部署文档与配置指南
  - [x] SubTask 23.4: 实现启动自检流程

- [x] Task 24: 集成测试
  - [x] SubTask 24.1: 用户认证模块测试（登录、鉴权、改密）
  - [x] SubTask 24.2: 系统配置模块测试（数据源、指标、维度、术语）
  - [x] SubTask 24.3: RAG全流程测试（文档入库→向量检索→问答→溯源）
  - [x] SubTask 24.4: ChatBI全流程测试（NL2Metrics/NL2SQL→校验→执行→结果解释）
  - [x] SubTask 24.5: 对话API测试（SSE流式、会话管理、意图路由）
  - [x] SubTask 24.6: 端到端混合查询场景测试（并行执行、溯源验证）

## 阶段八：代码质量优化 ✅ 已完成

- [x] Task 25: 代码注释增强
  - [x] SubTask 25.1: 为核心服务类添加详细文档注释（模块、类、方法）
  - [x] SubTask 25.2: 为数据库模型添加详细文档注释（模块、类、字段）
  - [x] SubTask 25.3: 更新代码注释规范文档（README.md）

- [x] Task 26: 日志增强
  - [x] SubTask 26.1: 为关键业务流程添加INFO级别日志
  - [x] SubTask 26.2: 为详细调试信息添加DEBUG级别日志
  - [x] SubTask 26.3: 更新日志说明文档（DEPLOYMENT.md）

- [x] Task 27: 文档更新
  - [x] SubTask 27.1: 更新README.md（代码注释规范、日志规范）
  - [x] SubTask 27.2: 更新DEPLOYMENT.md（版本历史、代码注释说明、新手入门指南）
  - [x] SubTask 27.3: 更新checklist.md（标记已完成项、添加代码质量检查项）
  - [x] SubTask 27.4: 更新tasks.md（标记已完成项、添加代码质量优化阶段）

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