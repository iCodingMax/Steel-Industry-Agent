# Checklist

## 用户认证（默认admin/admin）
- [x] 用户模型完整（username、password_hash、role、created_at、last_login_at）
- [x] 密码加密使用bcrypt，单向哈希存储
- [x] JWT token生成与验证正常（access_token、refresh_token）
- [x] 认证API完整（登录、刷新、登出、获取用户信息、修改密码）
- [x] 默认admin/admin账号初始化成功
- [x] JWT过期时间配置正确（access_token 1小时，refresh_token 7天）
- [x] JWT认证中间件生效，未登录请求返回401
- [x] 前端登录页面正常，支持账号密码登录

## 系统配置管理
### 数据源管理
- [x] 数据源模型完整（name、db_type、host、port、database、username、password、pool_size）
- [x] 数据源CRUD API正常（创建、列表、详情、更新、删除）
- [x] 连接测试功能正常，支持MySQL、PostgreSQL、Oracle数据库
- [x] Schema同步功能正常，支持MySQL（SHOW TABLES）、PostgreSQL（information_schema）、Oracle（all_tables/all_tab_columns）
- [x] 密码加密存储
- [x] 前端数据源管理页面正常（列表、新增/编辑弹窗、测试连接、Schema同步）

### 指标管理
- [x] 指标模型完整（name、code、datasource_id、formula、unit、valid_range、category、dimensions）
- [x] 指标CRUD API正常
- [x] 指标分组功能正常
- [x] 指标测试功能正常（可执行计算验证结果）
- [x] 前端指标管理页面正常（列表、新增/编辑、SQL编辑器）

### 维度管理
- [x] 维度模型完整（name、code、datasource_id、table_name、field_name、hierarchy、enum_values）
- [x] 维度CRUD API正常
- [x] 维度层级配置正常
- [x] 枚举值管理正常
- [x] 前端维度管理页面正常（列表、新增/编辑、层级配置）

### 术语管理
- [x] 术语模型完整（term、standard_field、synonyms、category）
- [x] 术语CRUD API正常
- [x] 同义词管理正常
- [x] 术语分类正常
- [x] 前端术语管理页面正常（列表、新增/编辑、同义词配置）

### 大模型配置（Xinference）
- [x] 大模型配置模型完整（config_type、model_type、api_base、api_key、model_name、temperature、max_tokens）
- [x] 大模型配置API正常（获取、更新）
- [x] 配置动态加载与生效正常
- [x] API Key加密存储
- [x] 前端系统设置页面正常（Xinference模型配置、账号设置）

## RAG工艺知识问答（基于LlamaIndex）
- [x] 支持多格式文档加载（PDF、Word、TXT、Markdown、Excel）
- [x] 基于LlamaIndex SimpleDirectoryReader实现文档加载
- [x] LlamaIndex嵌入模型配置正常（通过Xinference调用bge-m3）
- [x] LlamaIndex PGVectorStore配置正常，支持pgvector存储（与系统数据库统一）
- [x] 文本切片参数可配置（chunk_size、chunk_overlap）
- [x] 切片结果保留元数据信息（来源、页码、章节）
- [x] 数据模型完整（KnowledgeBase、Document、DocumentSegment）
- [x] 向量索引构建正常（LlamaIndex VectorStoreIndex）
- [x] 混合检索功能正常（向量+BM25）
- [x] 重排Rerank功能正常（通过Xinference调用bge-reranker-large）
- [x] 检索参数可配置（top_k、similarity_threshold）
- [x] 知识库管理API（创建、删除、列表、详情、文档上传、重建索引）功能正常
- [x] 知识检索问答API返回回答并附带文档引用来源
- [x] 引用标注包含文档名、页码、章节、切片ID、置信度分数
- [x] 前端知识库管理页面正常（知识库列表、文档列表、文档上传、索引状态）
- [x] 向量检索去重优化：基于segment_id去重，保留分数最高的结果

## ChatBI智能问数
- [x] NL2Metrics优先模式：指标语义匹配，命中后按预定义逻辑查询
- [x] NL2SQL兜底模式：未匹配指标时生成SQL查询（通过Xinference调用LLM）
- [x] Schema Linking正确识别查询需要的表和字段
- [x] SQL语法校验正确（sqlglot），拦截语法错误
- [x] SQL安全过滤拦截危险操作（DROP、DELETE、TRUNCATE）
- [x] 仅允许SELECT查询
- [x] 执行控制生效（超时限制30秒、返回行数限制1000行）
- [x] 术语映射正确，行业术语→标准字段转换正常
- [x] 五维可信机制实现（口径可信、证据可信、过程可信、交付可信、组织可信）
- [x] 查询结果以自然语言+表格形式展示
- [x] 数据可视化支持表格/Echarts图表切换（柱状图、折线图）
- [x] SQL溯源记录完整（SQL语句、执行耗时、影响数据表）
- [x] 智能表筛选：基于钢铁行业关键词匹配相关表，减少Schema规模

## 路由分发与混合分析
- [x] 意图识别模块准确分类（知识意图、数据意图、混合意图）
- [x] 意图识别通过Xinference调用LLM进行分类
- [x] 置信度阈值生效，低于阈值返回澄清问题
- [x] 路由分发器根据意图正确分发至对应通道
- [x] 混合分析引擎并行调用RAG与ChatBI
- [x] 融合结果连贯完整，无重复或冲突
- [x] Fallback机制主通道失败时自动切换备选通道

## 多轮对话与SSE
- [x] 会话管理功能正常（创建、列表、详情、删除）
- [x] 会话搜索功能正常（按关键词搜索历史会话）
- [x] 对话历史正确持久化
- [x] 长对话上下文压缩后关键信息保留完整
- [x] 意图追踪识别多轮对话中的意图延续
- [x] SSE流式响应正常（Server-Sent Events实时推送）
- [x] SSE消息格式正确（JSON格式，包含type、content、source等字段）
- [x] SSE心跳检测正常（定期发送心跳保持连接）
- [x] SSE错误处理正常（错误消息发送并关闭连接）
- [x] 前端SSE流式组件正常（逐字渲染、消息类型处理）

## 全链路溯源
- [x] 文档引用溯源可定位到原文档、页码、章节
- [x] 引用置信度标注准确
- [x] SQL溯源可查看完整SQL语句、执行耗时、影响数据表
- [x] SQL血缘追踪记录数据表与字段关系（基础版本）
- [x] 执行链路日志完整记录每步输入输出、时间戳
- [x] 证据标注关键数字溯源正确
- [x] 结论依据标注可复核验证
- [x] 前端溯源面板正常展示

## 前端管理后台
- [x] 主布局正常（左侧导航栏 + 顶部导航 + 主内容区）
- [x] 路由配置与权限守卫正常（智能对话、知识管理、数据管理、系统设置）
- [x] Pinia状态管理正常（auth、chat、config、knowledge）
- [x] 设计规范符合要求（配色方案、组件样式统一）
- [x] 品牌标识正常显示（左上角「Steel Industry AI Assistant」）
- [x] 侧边栏样式正常（深色渐变背景、激活项高亮）
- [x] 智能对话页面正常（左侧会话栏 + 中间对话区 + 输入框）
- [x] 消息列表组件正常（用户消息、AI回答、流式渲染）
- [x] 消息渲染器正常（知识卡片、数据表格、图表、溯源信息）
- [x] 知识管理页面正常（知识库列表、文档上传、索引状态）
- [x] 数据管理页面Tab切换正常（数据源、指标、维度、术语）
- [x] 系统设置页面正常（Xinference模型配置、账号设置）
- [x] 数据表格组件正常（分页、排序、筛选）
- [x] Echarts图表组件正常（柱状图、折线图）

## 私有化部署
- [x] Docker Compose一键部署成功，所有服务健康
- [x] PostgreSQL统一作为系统库+向量库，MySQL作为业务数据库
- [x] Xinference模型服务可通过配置接入（嵌入/重排/对话模型）
- [x] 国产大模型（千问等）可通过Xinference接入
- [x] MySQL/PostgreSQL/Oracle数据库可通过配置接入
- [x] 数据库连接池配置支持高并发
- [x] 环境健康检查接口正常返回各组件状态
- [x] 启动自检流程正常
- [x] 部署文档与配置指南完整

## 代码质量
- [x] 核心服务类添加详细文档注释（模块、类、方法）
- [x] 数据库模型添加详细文档注释（模块、类、字段）
- [x] 关键业务流程添加INFO级别日志
- [x] 详细调试信息添加DEBUG级别日志
- [x] 错误信息添加ERROR级别日志
- [x] 代码注释规范文档更新（README.md）
- [x] 日志说明文档更新（DEPLOYMENT.md）

## 集成测试
- [x] 用户认证模块测试通过（登录、鉴权、改密）
- [x] 系统配置模块测试通过（数据源、指标、维度、术语）
- [x] RAG全流程测试通过（文档入库→向量检索→问答→溯源）
- [x] ChatBI全流程测试通过（NL2Metrics/NL2SQL→校验→执行→结果解释）
- [x] 对话API测试通过（SSE流式、会话管理、意图路由）
- [x] 端到端混合查询场景测试通过（并行执行、溯源验证）