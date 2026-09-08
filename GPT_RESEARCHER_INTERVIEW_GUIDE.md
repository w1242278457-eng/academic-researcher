# GPT Researcher 项目面试解析

> 本文只分析当前 `D:\简历\gpt-researcher` 仓库中的 GPT Researcher。它与之前的“校园智能客服”项目是两个独立项目，不能混用项目背景、页面功能或技术成果。
>
> 当前工作区的 `frontend/index.html`、`frontend/scripts.js` 和 `gpt_researcher/config/variables/default.py` 存在本地修改；本文按仓库的 GPT Researcher 代码架构说明，不把首页中被改造成客服的页面当作 GPT Researcher 产品功能。

## 0. 一句话介绍

GPT Researcher 是一个面向 Web、文件和外部工具数据源的自动化深度研究系统：它先让 LLM 把用户问题拆成可执行的搜索任务，再并发检索和抓取多来源内容，经过清洗、去重、相关性压缩后交给报告生成器，最终输出带引用的 Markdown/PDF/DOCX 报告，并通过 WebSocket 实时反馈研究进度。

面试时可以强调：**它不是“把问题丢给一个大模型”的问答 Demo，而是一个带检索、证据汇总、编排、流式输出和可观测性的研究工作流。**

## 1. 项目解决的问题

- 通用 LLM 的知识可能过时，无法稳定回答实时问题。
- 单次提示词容易只使用少量来源，结论有偏差。
- 长报告受上下文窗口限制，原始网页不能全部塞进 Prompt。
- 网页有动态渲染、PDF、反爬和格式噪声，需要可替换的抓取策略。
- 研究过程耗时较长，用户需要看到进度、日志、来源和最终文件。
- 复杂报告需要先规划大纲、并行研究、审核和修订，而不是一次生成。

## 2. 总体架构

```text
Next.js / 静态 HTML 前端
          │ HTTP API + WebSocket /ws
          ▼
FastAPI backend/server/app.py
          │
          ├─ WebSocketManager + CustomLogsHandler（实时日志/报告片段）
          ├─ BasicReport / DetailedReport（报告流程外壳）
          ├─ ReportStore（JSON 文件历史记录）
          ├─ ChatAgentWithMemory（报告问答，可调用 quick_search）
          └─ multi_agent_runner（LangGraph/AG2 多 Agent）
          │
          ▼
GPTResearcher
  ├─ Config：环境变量/JSON/默认值
  ├─ ResearchConductor：计划查询、并发搜索、抓取、汇总
  ├─ Retriever：Tavily、Google、Bing、arXiv、Semantic Scholar、MCP 等
  ├─ BrowserManager + Scraper：BS、浏览器、Firecrawl、PDF 等
  ├─ ContextManager：分块、Embedding 相似度过滤、上下文压缩
  ├─ ReportGenerator：报告正文、引言、结论、子主题
  ├─ SourceCurator：来源整理、去重和引用
  └─ Memory/LLM Provider：Embedding、统一模型调用、成本统计
```

这里要区分两类“Agent”：

1. `GPTResearcher`、`ResearchConductor` 等主要是普通 Python 编排器/领域服务，里面会调用 LLM，但并不等于独立自治 Agent。
2. `multi_agents/` 下的 Researcher、Editor、Reviewer、Revisor、Fact Checker、Visualizer、Publisher 等，才是以 LangGraph 状态节点形式显式协作的多 Agent 工作流。

## 3. 目录结构速览

| 目录 | 作用 |
|---|---|
| `frontend/nextjs` | 生产型 Next.js + Tailwind 前端，研究表单、结果、历史、聊天和移动端适配 |
| `frontend/index.html`、`scripts.js`、`styles.css` | FastAPI 直接挂载的轻量前端 |
| `backend/server` | FastAPI 路由、WebSocket 管理、任务启动、日志桥接 |
| `backend/report_type` | `BasicReport`、`DetailedReport` 两种单研究流程 |
| `backend/chat` | 基于报告上下文的聊天和可选联网搜索 |
| `gpt_researcher` | 可复用的核心研究引擎/Python 包 |
| `multi_agents` | LangGraph 多 Agent 研究团队 |
| `multi_agents_ag2` | AG2 兼容实现和回退路径 |
| `tests` | 检索器、成本、日志、WebSocket、MCP、报告和安全测试 |
| `outputs`、`data/reports.json` | 报告文件和本地历史记录 |

## 4. 前端架构

### 4.1 Next.js 页面与状态

入口是 `frontend/nextjs/app/page.tsx`，研究详情页是 `app/research/[id]/page.tsx`。主要组件包括：

- `Task/ResearchForm.tsx`：问题、报告类型、数据源、语气、领域、MCP 等参数。
- `ResearchResults.tsx`：报告正文、来源、图片、日志、子问题和操作按钮。
- `ResearchHistoryContext.tsx`：历史报告列表、当前研究 ID 和本地/服务端同步。
- `hooks/useWebSocket.ts`：建立连接、发送任务、接收日志和报告片段。
- `components/Langgraph/Langgraph.js`：多 Agent 图形化展示。

桌面端长研究主要使用 WebSocket，以便持续接收日志和增量文本；移动端部分聊天逻辑直接走 `/api/chat`，降低连接管理复杂度。前端会维护 `promptValue`、`answer`、`loading`、`orderedData`、`allLogs`、`currentResearchId`、`chatMessages` 等状态。

### 4.2 研究请求在前端的参数

典型参数包括 `task`、`report_type`、`report_source`（web/local/hybrid/documents/vectorstore）、`tone`、`query_domains`、`mcp_enabled`、`mcp_strategy`、`mcp_configs`、`max_search_results` 和布局设置。前端不直接决定研究结论，只负责配置和呈现；真正的检索和生成在后端完成。

## 5. FastAPI 后端

`backend/server/app.py` 创建 FastAPI 应用，配置 CORS，挂载 `/outputs`、`/static`、`/site`，并在生命周期中创建输出目录。

主要接口：

| 接口 | 用途 |
|---|---|
| `GET /` | 返回轻量 HTML 前端（当前工作区首页可能被用户改造，不能代表核心引擎） |
| `GET /.well-known/agent-discovery.json` | Agent Discovery 能力描述 |
| `POST /report/` | HTTP 方式创建报告，可后台任务执行 |
| `GET /files/`、`POST /upload/`、`DELETE /files/{filename}` | 本地文档管理 |
| `GET/POST/PUT/DELETE /api/reports...` | 报告历史和聊天消息的 JSON 文件存储 |
| `POST /api/chat` | 对给定报告上下文进行聊天 |
| `POST /api/multi_agents` | 触发多 Agent 任务 |
| `WS /ws` | 研究任务、日志、流式报告和人工反馈 |

`ReportStore` 使用 `asyncio.Lock` 串行化读写，写入时先写 `.tmp` 再替换正式 JSON，避免并发写入产生半文件。它是轻量本地持久化，不是生产级数据库；面试时应主动说明可升级到 PostgreSQL/Redis/对象存储。

## 6. 一次普通研究请求的完整时序

```text
1. 用户在 ResearchForm 输入问题并选择参数
2. 前端连接 WS /ws，发送 "start {JSON}"
3. WebSocketManager 解析任务，创建 CustomLogsHandler
4. run_agent 按类型选择 BasicReport 或 DetailedReport
5. 报告外壳创建 GPTResearcher 和 Config
6. GPTResearcher 选择 agent/role，ResearchConductor 生成研究计划
7. 多个子查询并发调用 Retriever.search()
8. 对 URL 去重并发抓取，过滤过短或失败内容
9. ContextManager 分块并用 Embedding 过滤相关片段
10. 汇总 context、来源、访问 URL 和成本
11. ReportGenerator 调用 LLM 流式生成 Markdown
12. 日志和文本片段经 WebSocket 推送给前端
13. 后端/工具层可生成 PDF、DOCX、JSON 日志
14. 前端保存报告和 orderedData，用户可继续进行报告聊天
```

### 6.1 BasicReport

`BasicReport.run()` 只有两步：`conduct_research()` -> `write_report()`。它适合一次性研究报告，流程短、延迟低。

### 6.2 DetailedReport

`DetailedReport.run()` 会先做初始研究，再由 LLM 生成子主题；随后为每个子主题创建 `report_type="subtopic_report"` 的 GPTResearcher，复用已访问 URL 和上下文，生成各节草稿，最后补引言、目录、结论和引用。它更适合长文，但 LLM 调用和抓取次数更多。

## 7. GPTResearcher 核心类

`gpt_researcher/agent.py` 的 `GPTResearcher` 是核心会话对象，保存查询、配置、context、visited_urls、research_sources、research_images、成本和 WebSocket。

初始化阶段：

- `Config(config_path)` 加载模型、检索器、抓取器、并发数和报告设置。
- `get_retrievers()` 根据配置实例化检索器列表，默认通常是 Tavily。
- `Memory` 创建 Embedding。
- 初始化 `ResearchConductor`、`ContextManager`、`BrowserManager`、`SourceCurator`、`ReportGenerator`。
- 如果是 Deep Research，额外初始化 `DeepResearchSkill`。
- 如有 `mcp_configs`，只修改当前实例的 `cfg.retrievers`，不污染全局 `os.environ`，支持并发请求隔离。

`conduct_research()` 的关键分支：

- 没有预设 `agent/role` 时调用 `choose_agent()`，根据问题选择研究角色。
- 普通报告交给 `ResearchConductor`。
- `report_type=deep_research` 交给递归深度研究技能。
- 研究结束后按配置预生成图片。

`write_report()` 交给 `ReportGenerator`。其中有一个重要可靠性保护：如果最终 context 为空，不生成貌似有引用的幻觉报告，而是明确返回“没有检索到可靠来源”。

## 8. ResearchConductor 与检索链路

`gpt_researcher/skills/researcher.py` 负责研究执行：

1. 对原问题做初始搜索。
2. `plan_research_outline()` 调用战略模型生成子查询；MCP-only 时跳过额外拆题，避免重复调用。
3. 对子查询用 `asyncio.gather()` 并行执行。
4. 每个查询依次执行 Retriever -> URL 抓取 -> 内容压缩/摘要。
5. 合并结果并更新 `visited_urls`、来源和进度。

支持的 Retriever 包括 Tavily、Google、SearX、SearchAPI、SerpAPI、Serper、DuckDuckGo、Bing、Brave、Bocha、arXiv、Exa、Semantic Scholar、PubMed Central、OpenAlex、Custom、MCP、Xquik 等。统一接口的价值是：研究流程依赖 `search()` 契约，新增数据源不必修改编排器。

并发不是无限制的：搜索子查询由 `asyncio.gather` 并行，抓取由 `WorkerPool` 限制 worker；URL 先 `dict.fromkeys` 去重，已访问 URL 通过 `visited_urls` 跳过，降低延迟、重复内容和 API 成本。

## 9. 抓取、文档与上下文压缩

### 9.1 Scraper 策略

`Scraper.get_scraper()` 按 URL/配置选择：PDF 使用 PyMuPDF，arXiv 使用专用抓取器，普通网页可用 BeautifulSoup、WebBaseLoader、Browser、NoDriver、Tavily Extract 或 Firecrawl。浏览器抓取用于需要 JavaScript 渲染的页面；静态页面优先使用轻量 HTTP/BS，减少启动浏览器的开销。

`extract_data_from_url()` 会记录标题、内容长度和图片数量；内容少于 100 字或发生异常会丢弃，避免把错误页/空壳页送进 LLM。

### 9.2 本地和在线文档

`DocumentLoader` 支持 PDF、TXT、Word、PPTX、CSV、Excel、Markdown、HTML；`OnlineDocumentLoader` 下载 URL 后临时落盘，加载后删除临时文件；`LangChainDocumentLoader` 将 LangChain `Document` 统一映射为 `raw_content + url`。

### 9.3 ContextCompressor

大网页不能原样塞入 Prompt，压缩流程是：

```text
原始文档 -> RecursiveCharacterTextSplitter(chunk=1000, overlap=100)
          -> EmbeddingsFilter(similarity_threshold)
          -> 取 top-N -> pretty_print_docs()
```

当文档总字符数低于 `COMPRESSION_THRESHOLD` 且数量不多时走快速路径，直接返回文档，避免不必要的 Embedding 成本。Vectorstore 场景使用 `VectorstoreCompressor`；已写报告章节使用 `WrittenContentCompressor`，减少详细报告章节之间的重复。

## 10. LLM、Embedding 与成本控制

模型字符串采用 `provider:model`，例如 `openai:gpt-4o-mini`、`deepseek:deepseek-chat`。`Config` 的优先级是：环境变量 > 自定义 JSON > 默认配置。当前工作区默认配置已改为 DeepSeek，但这属于本地配置，不应在面试中说成框架硬编码。

`gpt_researcher/utils/llm.py` 统一不同 provider 的调用，支持流式和非流式。失败时有指数退避重试；空响应也被视为失败。战略模型生成子查询失败时，会尝试限制 `max_tokens`，仍失败则回退到 smart LLM。流式且绑定 WebSocket 时重试次数会收紧，避免重复推送。

每次 LLM/Embedding 调用可通过 `cost_callback` 记录输入、输出、模型和 provider 成本，`GPTResearcher.add_costs()` 聚合总成本和步骤成本。面试中可以这样解释成本策略：

- 用 fast/smart/strategic 模型分层，规划不必使用最贵模型。
- 限制 `MAX_SEARCH_RESULTS_PER_QUERY`、`MAX_SUBTOPICS` 和抓取 worker。
- URL 去重、visited 集合和小文档快速路径减少重复工作。
- 研究日志记录步骤成本，便于定位最贵环节。

## 11. 报告生成

`ReportGenerator` 调用 `actions/report_generation.py`：

- `generate_report()` 根据 `report_type` 选择 Prompt；支持自定义 Prompt、语气、语言、总字数和图片嵌入。
- `write_report_introduction()`、`write_conclusion()` 单独生成引言和结论。
- `construct_subtopics()` 使用结构化输出解析子主题。
- `add_references()`、`table_of_contents()`、`extract_headers/sections()` 负责报告后处理。

报告生成采用流式输出，正文片段先到前端，完整报告结束后再发送完成事件。报告可转换为 Markdown、PDF、DOCX；多 Agent 的 Publisher 也负责按所选格式落盘。

## 12. Agent 协作：两种模式

### 12.1 核心单研究模式

这是“一个会话对象 + 多个能力服务”的编排：`GPTResearcher` 持有 conductor、context manager、browser manager 和 writer。它们共享状态和成本回调，优点是调用链短、易于复用；缺点是角色边界不如显式多 Agent 清晰。

### 12.2 LangGraph 多 Agent 模式

`multi_agents/agents/orchestrator.py` 的 `ChiefEditorAgent` 构建 `StateGraph(ResearchState)`：

```text
browser(初始研究)
  -> planner(Editor 规划大纲)
  -> human(可选人工审核)
  -> researcher(每个章节并行深度研究)
  -> writer
  -> fact_checker --发现问题--> writer（循环）
  -> visualizer
  -> publisher -> END
```

角色职责：

- Chief Editor：创建任务目录、初始化 Agent、编译图并运行。
- Researcher：获取初始资料或章节研究资料。
- Editor：根据初始摘要生成标题和章节；用 `asyncio.gather` 并发章节研究。
- Reviewer/Revisor：审阅草稿并按意见循环修改。
- Fact Checker：识别事实问题，驱动 Writer 修订。
- Visualizer：生成 Mermaid 等可视化内容。
- Writer：生成引言、正文、结论和引用所需内容。
- Publisher：拼接最终布局并输出 Markdown/PDF/DOCX。
- Human：在规划后暂停或接受人工反馈。

这里的关键设计是**状态图 + 条件边**：审核通过才继续，事实检查失败则回到 Writer；人工修订超过上限会强制接受，防止无限循环。后端 `multi_agent_runner.py` 优先导入 LangGraph 实现，失败时回退 AG2 实现。

## 13. MCP 与 Deep Research

MCP 允许接入 GitHub、数据库或自定义 API 等工具型数据源。策略有三种：

- `disabled`：不调用 MCP。
- `fast`：用原始问题调用一次，低延迟。
- `deep`：对子查询也调用，覆盖更广但成本更高。

当 MCP 是唯一 Retriever 时，系统跳过子查询生成，避免“没有必要的二次规划”。配置在当前 `GPTResearcher` 实例中传递，不写入全局环境变量，这对多用户并发很重要。

Deep Research 是另一条递归树式流程，配置 `DEEP_RESEARCH_BREADTH`、`DEEP_RESEARCH_DEPTH`、`DEEP_RESEARCH_CONCURRENCY`；它在深度和广度之间扩展子问题，并发处理分支，再汇总上下文。面试时不要把它和 LangGraph 多 Agent 混为一谈：前者是核心引擎里的递归研究技能，后者是显式角色工作流。

## 14. WebSocket、日志和聊天

### 14.1 WebSocket

`WebSocketManager` 为每个连接创建发送队列和 sender task；研究代码只需把消息放入队列，发送任务负责顺序发送，避免多个协程同时写 socket。前端每 30 秒 ping，服务端返回 pong。消息类型包括 `logs`、`report`、`report_complete`、`path`、`human_feedback`。

选择 WebSocket 的原因是研究通常持续几十秒到数分钟，HTTP 请求不适合频繁轮询；它能同时承载进度、日志、增量报告和人工反馈。HTTP `/report/` 仍保留，适合后台任务或不需要实时 UI 的调用。

### 14.2 报告聊天

`ChatAgentWithMemory` 将报告放入系统 Prompt，要求回答必须基于报告并带引用；当问题需要实时信息时，通过工具调用 `quick_search`。Tavily key 不存在时显式禁用联网搜索并返回元数据，而不是静默失败。当前 `_setup_vector_store()` 被条件关闭，说明报告聊天主要依赖 Prompt 上下文；如果报告很长，生产改造应启用向量检索或外部 RAG 存储。

## 15. 配置、安全与错误处理

重点配置：`RETRIEVER`、`SCRAPER`、`EMBEDDING`、`FAST_LLM`、`SMART_LLM`、`STRATEGIC_LLM`、`MAX_SEARCH_RESULTS_PER_QUERY`、`MAX_SUBTOPICS`、`MAX_SCRAPER_WORKERS`、`LANGUAGE`、`REPORT_SOURCE`、`DOC_PATH`、MCP 和 Deep Research 参数。

安全/健壮性要点：

- 上传文件、删除文件和报告 ID 需要限制路径，使用 `sanitize_filename` 防止路径穿越。
- 抓取异常、HTTP 非 200、过短页面统一丢弃并记录日志。
- LLM 空响应和异常有重试/回退；无 context 时拒绝生成“可信外观”报告。
- MCP 配置不污染进程级环境变量。
- WebSocket 断开时取消 sender task、清理队列并关闭连接。
- CORS 默认只允许本地前端和官方域名，可用 `CORS_ALLOW_ORIGINS` 覆盖。

可改进点：报告存储目前是单机 JSON；缺少统一认证、速率限制和任务队列；抓取端仍可能受到网站策略影响；引用可增加事实级校验；多实例部署需要 Redis Pub/Sub、对象存储和分布式锁。

## 16. 测试体系

`tests/` 覆盖的能力包括：

- Retriever：Brave、CRW、自定义检索器和检索编排。
- LLM：`max_tokens`、usage/cost tracking、不同 provider。
- 研究行为：报告类型、文档来源、Deep Research 解析、quick search。
- 基础设施：日志输出、WebSocketManager、Agent Discovery。
- 多 Agent：新 Agent、人工计划修订、事实检查相关流程。
- 安全与回归：`test_security_fix.py` 等。

面试时可以说测试策略是“核心纯逻辑单测 + provider 边界测试 + WebSocket/编排集成测试”；真实外部搜索和 LLM 测试应使用 mock，避免不稳定和实际费用。

## 17. 关键代码路径

```text
frontend/nextjs/app/page.tsx
  -> hooks/useWebSocket.ts
  -> backend/server/app.py:/ws
  -> backend/server/server_utils.py:handle_websocket_communication
  -> backend/server/websocket_manager.py:run_agent
  -> backend/report_type/basic_report/basic_report.py
  -> gpt_researcher/agent.py:GPTResearcher.conduct_research
  -> gpt_researcher/skills/researcher.py:ResearchConductor
  -> gpt_researcher/actions/retriever.py
  -> gpt_researcher/scraper/scraper.py
  -> gpt_researcher/skills/context_manager.py
  -> gpt_researcher/skills/writer.py:ReportGenerator
  -> gpt_researcher/actions/report_generation.py
```

详细报告分支从 `DetailedReport.run()` 进入子主题研究；多 Agent 分支从 `multi_agent_runner.py` 进入 `ChiefEditorAgent` 的 LangGraph。

## 18. 面试高频问题与参考回答

### Q1：你如何概括这个项目？

这是一个研究型 Agent 平台。用户输入问题后，系统由规划模型拆分子问题，多个检索器并发获取来源，抓取器抽取网页内容，Embedding 压缩上下文，报告生成器基于证据生成带引用报告；FastAPI 提供 API/WebSocket，Next.js 展示实时进度，LangGraph 提供更严格的多角色审核流程。

### Q2：为什么不用一次 LLM 调用直接生成？

一次调用缺少实时数据、来源覆盖和可审计性，也受上下文窗口限制。拆题、并发检索、来源去重和压缩能提高覆盖率与稳定性；报告阶段只接收相关证据，降低幻觉概率。

### Q3：并发如何实现？

子查询使用 `asyncio.gather` 并发；抓取使用 `WorkerPool` 控制最大 worker；URL 去重和 `visited_urls` 防止重复访问。并发上限由配置控制，避免把速度换成限流、费用或目标站点压力。

### Q4：WebSocket 和 HTTP 怎么取舍？

长研究任务需要实时日志、增量报告和人工反馈，所以主 UI 用 WebSocket；后台批处理可用 `/report/` + `BackgroundTasks`，简单聊天则用 HTTP `/api/chat`。两种协议服务不同交互场景。

### Q5：如何控制成本？

模型分层、限制搜索结果和子主题数量、抓取去重、短文档快速路径、Embedding/LLM 成本回调和步骤级统计。还可以按任务预算动态降低深度、MCP 从 deep 切 fast，或缓存相同 URL 的抽取结果。

### Q6：Agent 协作在哪里？

核心单研究主要是 Python 服务编排，不应把每个类都称作 Agent；显式 Agent 协作在 `multi_agents`，由 LangGraph 状态图连接 Researcher、Editor、Writer、Fact Checker、Visualizer 和 Publisher，并通过条件边实现审核与修订循环。

### Q7：如果搜索没有结果怎么办？

Retriever/抓取异常返回空列表并记录日志；`ReportGenerator` 检查 context，空上下文时返回无法获得可靠来源的说明，不生成伪造引用的报告。更进一步可以增加来源重试、备用 Retriever 和人工介入。

### Q8：最难的工程问题是什么？

一是把多个搜索/抓取 provider 统一成可替换协议；二是长任务的异步并发、WebSocket 顺序发送和断线清理；三是长上下文的压缩与成本平衡；四是让 MCP 配置、visited URL、报告状态在并发请求间隔离；五是让多 Agent 的审核循环有上限。

### Q9：你会怎么优化？

短期增加 URL/摘要缓存、任务队列、结构化引用校验、失败重试分类和更细的指标；中期把 JSON ReportStore 换成数据库+对象存储，引入 Redis 事件流和分布式限流；长期增加评测集，衡量检索召回、引用正确率、事实一致性、延迟和单次成本。

### Q10：项目有什么不足？

当前本地存储和单进程 WebSocket 更适合单机演示；聊天的向量检索路径默认关闭，超长报告会增加 Prompt 成本；外部网站抓取稳定性受站点影响；认证、配额和多租户隔离仍需补齐。主动说明边界比把 Demo 说成生产系统更可信。

## 19. 可直接用于简历/自我介绍

**项目：GPT Researcher 自动化深度研究平台**

负责/参与构建一个支持 Web、本地文档和 MCP 数据源的自动化研究系统。基于 FastAPI + Next.js 实现研究任务提交、WebSocket 实时日志/流式报告、历史记录和报告聊天；在核心引擎中设计“子问题规划 -> 多检索器并发 -> 网页抓取 -> Embedding 上下文压缩 -> 带引用报告生成”的异步流水线，支持多模型 provider、PDF/DOCX 输出、成本统计和失败回退。基于 LangGraph 实现 Editor、Researcher、Writer、Reviewer、Fact Checker、Visualizer、Publisher 等多 Agent 协作，并通过条件边实现人工审核和事实修订闭环。

面试表达时请根据真实参与范围把“负责”改为“实现/参与/分析”，不要把仓库已有能力全部包装成个人独立完成；也不要把本项目与校园智能客服项目合并描述。

## 20. 运行与验证提示

常用入口：

```bash
pip install -r requirements.txt
python -m uvicorn backend.server.app:app --reload --port 8000
cd frontend/nextjs
npm install --legacy-peer-deps
npm run dev -- --port 3000
```

需要配置至少一个 LLM provider key 和搜索 key（例如 `OPENAI_API_KEY`/`DEEPSEEK_API_KEY`、`TAVILY_API_KEY`）。当前环境中 Next.js 前端可通过 `http://localhost:3000` 访问，FastAPI API 在 `http://localhost:8000`；但 8000 首页受工作区本地客服页面修改影响，验证核心 GPT Researcher 前端应优先查看 Next.js 页面和 API/WebSocket。

