# LangChain 与 LangGraph 面试详解

> 适用项目：本目录的 **GPT Researcher**，以及独立目录 `../ai-customer-service` 的校园 AI 客服项目。
>
> **边界声明**：两者是两个独立项目。本文只在对比章节并列说明它们，绝不把一个项目的能力当作另一个项目的实现。所有“已使用”结论均以当前源码为准；设计意图、预留代码和真实运行主链路会明确区分。

## 1. 先用一句话建立框架认知

- **LangChain** 是搭建 LLM 应用的组件库和统一抽象层：模型、消息、提示词、结构化输出、工具、文档、Embedding、Retriever、向量库等。
- **LangGraph** 是建立有状态、可分支、可循环、可持久化 Agent 工作流的编排框架。它构建在 LangChain 的 Runnable/消息等能力之上，但二者可以分别使用。

一个容易记住的比喻是：LangChain 解决“一个节点如何调用模型、检索资料或调工具”，LangGraph 解决“多个节点以什么状态、什么顺序、在什么条件下协作”。不过面试时更应使用这句工程化表述：**LangChain 管能力单元，LangGraph 管长流程控制和状态演进。**

## 2. LangChain 核心知识点

### 2.1 模型、Prompt 与 Message

`ChatModel` 接收的是消息列表，最常见的三类是：

| 类型 | 作用 | 典型内容 |
| --- | --- | --- |
| `SystemMessage` | 约束身份、边界和输出规则 | “只能基于已检索文档回答” |
| `HumanMessage` | 用户的输入 | 用户问题 |
| `AIMessage` | 模型输出，可带 tool calls | 回答、工具调用请求 |
| `ToolMessage` | 工具执行结果回写模型 | 检索结果、订单状态 |

`PromptTemplate` 将变量填入字符串模板；`ChatPromptTemplate` 更适用于多消息 Prompt。关键不是“拼字符串”，而是把角色、变量、格式要求和业务规则作为可复用、可测试的输入契约。

### 2.2 Runnable 与 LCEL

LangChain 将模型、Prompt、解析器、Retriever 等抽象为可执行单元（Runnable）。LCEL（LangChain Expression Language）用 `|` 串起数据流：

```python
chain = prompt | model | parser
result = await chain.ainvoke(input)
```

常用运行方式：

| 方法 | 含义 | 使用场景 |
| --- | --- | --- |
| `invoke()` | 同步单次调用 | 简单脚本 |
| `ainvoke()` | 异步单次调用 | Web 服务、并发 Agent |
| `stream()` / `astream()` | 流式返回 | 打字机输出、逐步展示 |
| `batch()` / `abatch()` | 批量调用 | 离线任务 |

注意：LCEL 只是组合单个或局部链路，不等于多 Agent 工作流。存在条件分支、循环审核、可恢复任务时，更适合由 LangGraph 承担。

### 2.3 结构化输出

让模型输出 JSON 不能只依赖一句“请返回 JSON”。更可靠的方法是用 Pydantic 定义模式，并使用 `PydanticOutputParser` 或模型原生 structured output：

```python
parser = PydanticOutputParser(pydantic_object=Subtopics)
chain = prompt | model | parser
```

收益：字段可校验、下游逻辑不必猜测自然语言、失败可以重试或降级。风险：模型仍可能输出不合法内容，生产代码需要解析异常、重试和回退策略。

### 2.4 Tool Calling

工具是带名称、描述和输入 schema 的外部能力，例如搜索、查询订单、创建工单。典型闭环是：

```text
用户消息 -> 模型判断需要工具 -> AIMessage.tool_calls
        -> 执行工具 -> ToolMessage
        -> 模型根据结果组织最终回答
```

工具调用不是把函数“交给模型就结束”。工程上必须做参数校验、身份鉴权、超时、幂等、审计、错误回传和最小权限控制。MCP 是工具/上下文互操作协议；它不是 LangGraph，也不自动带来 Agent 编排能力。

### 2.5 RAG 基础链路

RAG（Retrieval-Augmented Generation）让模型在生成前读取检索到的私有或最新资料，基本流程为：

```text
源文件/网页 -> Loader -> Document -> Text Splitter -> Embedding -> Vector Store
用户问题 -> Query Embedding -> Retriever -> 相关 chunks -> Prompt -> LLM 回答
```

主要概念：

| 概念 | 职责 | 常见误区 |
| --- | --- | --- |
| `Document` | `page_content + metadata` 的统一文档载体 | 不是向量库记录本身 |
| Loader | 读取 PDF、网页、Word、CSV 等 | 读取成功不代表抽取质量好 |
| Text Splitter | 长文本切块并保留 overlap | chunk 过大浪费上下文，过小丢语义 |
| Embeddings | 把文本映射到语义向量 | 哈希/随机向量不是真实语义检索 |
| Vector Store | 保存向量并做相似度搜索 | 不是传统关系数据库替代品 |
| Retriever | 面向上层的“给我相关文档”接口 | 可以封装向量检索、搜索 API 或混合检索 |

检索质量通常取决于文档质量、分块策略、Embedding 模型、召回数量、重排、元数据过滤和评测集，不只是换一个大模型。

### 2.6 Context Compression 与重排

检索到的文本不能全部塞进 Prompt。常见策略是先粗召回，再按相似度过滤、重排或摘要，只把最相关片段交给模型。优点是降低 token 成本和“无关上下文干扰”；代价是可能误删关键证据，因此要评估召回率和答案引用质量。

### 2.7 Memory、Tracing 与 LangChain 的边界

“Memory”不是单一功能：会话历史、任务中间状态、长期用户画像、知识库是不同数据，存储和生命周期也不同。LangChain 可提供消息与检索抽象，但生产系统仍需要 Redis、数据库、向量库和清晰的数据保留策略。

Tracing 则记录模型/工具/Agent 的耗时、错误和输入输出摘要，用于调试、成本治理和评测。不要把模型隐藏推理文本当成业务 trace 存储。

## 3. LangGraph 核心知识点

### 3.1 State、Node、Edge

LangGraph 的最小模型是状态图：

```text
State：节点共享的数据契约
Node：读取 state 并返回 state 的部分更新
Edge：固定的下一个节点
Conditional Edge：根据 state 决定下一跳
END：终止执行
```

通常用 `TypedDict` 表达状态。它比在各 Agent 间散落地传多个参数更清晰，也让面试官能快速看到数据所有权。例如：

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str
    sub_results: dict[str, Any]
    final_response: str
```

`add_messages` 是消息字段的 reducer，表示节点返回的新消息应按消息语义合并，而不是简单覆盖原列表。对于并行分支，必须显式设计每个字段的合并规则，否则会产生状态覆盖或顺序不确定问题。

### 3.2 编译与执行

构图后调用 `compile()`，图才成为可执行对象；随后通过 `invoke`、`ainvoke` 或流式执行运行。`configurable.thread_id` 是一次会话/任务的稳定标识，供 checkpoint、恢复和追踪关联使用。

```python
graph = StateGraph(AgentState)
graph.add_node("route", route)
graph.add_conditional_edges("route", choose, mapping)
graph.add_edge("answer", END)
app = graph.compile(checkpointer=MemorySaver())
result = await app.ainvoke(initial_state, config={"configurable": {"thread_id": sid}})
```

### 3.3 条件、循环、人工介入与检查点

LangGraph 的优势在于它能明确表达：

- 路由：客服问题进入 RAG、工单或通用聊天；
- 循环：审核不通过后返回修订节点；
- 人工介入：计划被用户修改后回到规划节点；
- 持久化：checkpointer 按 `thread_id` 保存图状态，支持恢复。

要区分两个概念：**图状态 checkpoint** 保存的是 LangGraph 运行状态，**短期聊天记录**可能在 Redis，**长期知识**可能在向量库；它们互补，不能互相替代。

### 3.4 何时选 LangGraph，何时不选

单轮“Prompt -> 模型 -> 解析”的任务用 LangChain Runnable 或普通函数即可。以下情形更值得引入 LangGraph：存在多步业务流程、条件路由、循环校验、人工审批、可恢复长任务、多个 Agent 共用状态或需要可观测的节点边界。

不要为“多 Agent”而多 Agent。若所有节点只串行调用同一模型、没有明确输入输出契约和质量收益，图只会增加调试成本和延迟。

## 4. 两个框架如何配合

```text
LangChain 层：Prompt / Messages / Model / Parser / Tool / Retriever / Embedding
                                  |
                                  v
LangGraph 层：State -> Node -> Conditional Edge / Loop -> Checkpoint -> END
                                  |
                                  v
业务层：研究报告、校园客服、鉴权、数据库、监控、前端体验
```

LangGraph 节点内部经常调用 LangChain 的模型或工具，但一个 LangGraph 节点也可以是普通 Python 函数。反过来，LangChain 的 RAG 或工具调用链也不必由 LangGraph 调度。

## 5. GPT Researcher：LangChain 的真实用法

### 5.1 文档抽取与统一数据模型

`gpt_researcher/document/document.py` 通过 LangChain Community loaders 读取多种格式，如 `PyMuPDFLoader`、`TextLoader`、Word/PPT/CSV/Excel/Markdown/HTML loaders。`gpt_researcher/document/langchain_document.py` 再把 LangChain `Document` 适配为项目内部格式：

```python
{"raw_content": document.page_content, "url": document.metadata.get(...)}
```

这是典型的“外部框架模型 -> 项目领域模型”适配：上游享受 Loader 生态，下游避免在业务代码到处耦合 `Document` 的具体实现。

### 5.2 文档切块、Embedding 与向量检索

`gpt_researcher/vector_store/vector_store.py` 使用 `langchain_core.documents.Document`、`VectorStore` 和 `RecursiveCharacterTextSplitter`：先把内部文本转 `Document`，按配置切块，再交给向量库做相似度搜索。

`gpt_researcher/memory/embeddings.py` 根据 provider 配置创建 LangChain Embeddings 对象，覆盖 OpenAI、Azure OpenAI、Cohere、Vertex、Google、Ollama、HuggingFace、Mistral 等。这使上层检索流程无需绑定某一家模型服务。

### 5.3 上下文压缩

`gpt_researcher/context/compression.py` 使用：

- `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)`；
- `EmbeddingsFilter`；
- `DocumentCompressorPipeline`；
- `ContextualCompressionRetriever`。

路径为“原始网页/文档 -> 切块 -> 相关度过滤 -> 只保留相关 chunks -> 拼入 Prompt”。小内容走快速路径跳过压缩，以减少 Embedding 调用和延迟。面试中可以说明：这是在回答质量、上下文窗口和成本之间做的折中，而不是简单截断文本。

### 5.4 Retriever 抽象

`gpt_researcher/context/retriever.py` 中的 `SearchAPIRetriever`、`SectionRetriever` 继承 `langchain_core.retrievers.BaseRetriever`。它们把搜索 API 和章节资料统一为“给定查询返回相关文档”的协议，后续可以与压缩器、链和其他 Retriever 组合。

### 5.5 LCEL + Pydantic 结构化主题生成

`gpt_researcher/utils/llm.py` 的 `construct_subtopics()` 是最直接的 LCEL 例子：

```python
parser = PydanticOutputParser(pydantic_object=Subtopics)
prompt = PromptTemplate(..., partial_variables={
    "format_instructions": parser.get_format_instructions()
})
chain = prompt | model | parser
output = await chain.ainvoke({...})
```

该设计把提示词渲染、模型调用、类型校验拆开。若解析失败，函数记录异常并返回已有 `subtopics` 作为降级结果，避免一次格式异常让整个研究中断。

### 5.6 Tool Calling 与 MCP

`gpt_researcher/utils/tools.py` 使用 `HumanMessage`、`SystemMessage`、`AIMessage`、`ToolMessage` 与 `@tool`，执行模型发起的工具调用并把结果返回给模型生成最终回答。MCP 相关代码位于 `gpt_researcher/mcp/` 与 `gpt_researcher/retrievers/mcp/`，通过 `langchain_mcp_adapters.client.MultiServerMCPClient` 将外部 MCP Server 工具接入研究流程。

这里的准确表述是：**LangChain 提供消息、工具和 MCP adapter 的适配能力；MCP 负责跨工具服务的协议；是否调用、何时调用仍由具体研究流程决定。**

### 5.7 一个值得如实说明的实现细节

`backend/chat/chat.py` 虽导入 `RecursiveCharacterTextSplitter` 和 `InMemoryVectorStore`，但 `_setup_vector_store()` 的调用被 `if not self.vector_store and False:` 禁用。因此当前报告聊天主路径主要将报告写入 system prompt，而非真正启用报告级向量检索。面试中不应说“报告聊天已完整 RAG 化”。可提出改进：对长报告启用切块、Embedding、检索和引用定位，降低 Prompt 超长与上下文丢失风险。

## 6. GPT Researcher：LangGraph 的真实用法

LangGraph 主要位于 `multi_agents/`，不是所有普通研究请求的必经路径。普通研究大量使用 Python 异步编排、LangChain 组件和 WebSocket；当选择多 Agent 模式时，才进入下述状态图工作流。

### 6.1 总体研究图：Chief Editor

`multi_agents/agents/orchestrator.py` 的 `ChiefEditorAgent` 建立 `StateGraph(ResearchState)`，状态定义在 `multi_agents/memory/research.py`，包括 `task`、初始研究、章节、研究数据、人工反馈、报告、事实核查备注、图表等字段。

```text
browser -> planner -> human --接受/强制接受--> researcher -> writer
                         |                                  |
                         +--修改计划--> planner              v
                                      fact_checker --接受--> visualizer -> publisher -> END
                                                    |
                                                    +--需修订--> writer
```

节点职责：

| 图节点 | 对应角色 | 输出/作用 |
| --- | --- | --- |
| `browser` | ResearchAgent | 初始研究素材 |
| `planner` | EditorAgent | 报告标题、日期、章节计划 |
| `human` | HumanAgent | 审阅和反馈计划 |
| `researcher` | EditorAgent | 并行完成章节研究 |
| `writer` | WriterAgent | 形成报告草稿 |
| `fact_checker` | FactCheckerAgent | 通过或给出修改意见 |
| `visualizer` | VisualizerAgent | 生成可视化内容 |
| `publisher` | PublisherAgent | 写出最终产物 |

人工反馈条件边最多允许 5 次修订，避免无止境回环；事实核查发现 `fact_check_notes` 时返回 writer，直到通过。这正是状态图比简单线性 chain 更合适的地方。

`run_research_task()` 中 `compile()` 后用 `chain.ainvoke({"task": self.task}, config=...)` 执行，并传入 `thread_id`、时间戳类配置做任务关联。当前文件的 `MemorySaver` 导入被注释，因此不要夸大为“这个研究图已在此处启用 checkpoint 持久化”。

### 6.2 章节级子图与并发

`multi_agents/agents/editor.py` 为单章节构建 `StateGraph(DraftState)`：

```text
researcher -> reviewer --接受--> END
                 ^
                 |
              reviser <- 需修订
```

规划完成多个章节后，`run_parallel_research()` 对每个章节调用子图的 `ainvoke()`，再通过 `asyncio.gather()` 并发等待。这里要准确区分：**LangGraph 表达每个章节内部的研究-审阅-修订循环；Python `asyncio.gather` 实现多个章节子图的并发调度。**

### 6.3 前端如何接入 LangGraph

`frontend/nextjs/app/page.tsx` 在 `report_type === 'multi_agents'` 且存在 `LANGGRAPH_HOST_URL` 时调用 `startLanggraphResearch()`。`frontend/nextjs/components/Langgraph/Langgraph.js` 使用 `@langchain/langgraph-sdk` 的 `Client` 启动任务并拿到 stream、host、`thread_id`；前端还能构造 LangSmith Studio 的 thread 链接进行运行观察。

因此可用如下方式说明前后端：普通研究使用仓库既有 WebSocket 路径；多 Agent 研究可走 LangGraph host/SDK 路径。前端不是直接“运行 Agent”，而是把任务提交给后端图运行时并展示流和状态。

## 7. AI 客服项目：LangChain 的真实用法

### 7.1 已使用的部分：消息类型

客服项目的 `python-impl/llm_client.py` 导入 `langchain_core.messages` 的 `BaseMessage`、`AIMessage`；各 Agent 使用 `SystemMessage` 和 `HumanMessage`。`OpenAICompatibleChatModel.ainvoke()` 将这些消息转换为 OpenAI 兼容 Chat Completions payload，并返回 `AIMessage`。

这带来的价值是保留 LangChain 标准消息语义，模型调用层可被图节点以统一方式使用。它是一个很轻量的集成，而不是直接使用 `ChatOpenAI`。

### 7.2 必须如实说明：未大量采用 LangChain RAG 组件

尽管 `requirements.txt` 依赖了 `langchain` 与 `langchain-community`，当前客服 RAG **没有**使用 LangChain 的 `Document`、TextSplitter、Embeddings、VectorStore 或 Retriever。它在 `memory/long_term.py` 自行实现：

- 文本分块：`_chunk_text(text, chunk_size=512, overlap=128)`；
- 索引：FAISS `IndexFlatIP`；
- Embedding：`_simple_embedding()` 用文本哈希生成可重复的随机向量；
- 检索：`search()` 搜索 FAISS，不可用时退化为关键词匹配；
- RAG 链路：改写 query -> 召回 5 篇 -> LLM 重排 3 篇 -> 基于上下文回答。

这套实现适合演示接口和流程，但哈希随机向量不表达语义，因此不能宣称为可生产的“语义 RAG”。真实改进方向是替换为 LangChain Embeddings 或供应商 SDK 的真实 Embedding，并重建索引；如果采用 LangChain `Document`/VectorStore/Retriever，可减少自定义适配代码并提高组件可替换性。

### 7.3 Prompt、结构化解析与防御

`KnowledgeRAGAgent`、`TicketHandlerAgent`、`ComplianceCheckerAgent` 都以 `SystemMessage + HumanMessage` 构造 Prompt 并异步调用客户端。工单和合规模块要求模型返回 JSON，但当前使用 `json.loads()` 解析并在 `JSONDecodeError` 时回退默认结果。

面试中可以主动指出改进：定义 Pydantic schema，并采用 LangChain `PydanticOutputParser` 或提供商原生 JSON Schema/structured output。这样可校验字段范围，例如工单优先级只能是 `low|medium|high|urgent`，避免模型格式漂移。

### 7.4 MCP 的实际状态

`mcp/mcp_server.py` 是项目自定义的 “MCP 风格”工具注册和 JSON-RPC 处理器，提供 `tools/list`、`tools/call`、`ping`，并由 API 暴露 `/api/tools` 与 `/api/tools/call`。它并未使用 `langchain-mcp-adapters`，也没有进入主聊天图由模型自动 tool-call。

所以正确表述是：该项目实现了可扩展工具层原型；主聊天里的 Ticket Agent 当前使用内存 `TicketStore`，不是自动调用该 MCP 工具服务。生产接入时需把工具 schema 注册到模型、在图中放置 ToolNode/工具节点，并加入鉴权、确认和幂等控制。

## 8. AI 客服项目：LangGraph 的真实用法

### 8.1 状态与检查点

`agents/supervisor.py` 定义 `AgentState`：

| 字段 | 用途 |
| --- | --- |
| `messages` | LangChain 消息列表，使用 `add_messages` reducer 合并 |
| `user_id` / `session_id` | 用户与会话隔离 |
| `intent` | 路由结果 |
| `sub_results` | 各业务 Agent 产生的结果 |
| `compliance_passed` | 是否通过最终合规门禁 |
| `final_response` | 返回 API 的最终文本 |
| `trace` | 前端可展示的阶段摘要 |

`create_supervisor_graph()` 通过 `StateGraph(AgentState)` 组装节点，并以 `MemorySaver()` 作为 checkpointer。`api/main.py` 调用图时传入：

```python
config = {"configurable": {"thread_id": session_id}}
result = await graph.ainvoke(initial_state, config=config)
```

这使 LangGraph checkpoint 能按会话标识关联状态。它与 Redis 的短期消息记录并存，不是二选一。

### 8.2 客服主图

```text
START
  -> supervisor_route
      -> knowledge_rag   -> compliance_check -> synthesize -> END
      -> ticket_handler  -> compliance_check -> synthesize -> END
      -> general_chat    -> compliance_check -> synthesize -> END
```

节点分工：

1. `supervisor_route`：确定用户进入知识问答、工单或通用聊天。
2. `knowledge_rag`：改写查询、召回、重排、生成基于知识的回答。
3. `ticket_handler`：从文本提取工单字段，创建或查询内存工单。
4. `general_chat`：处理问候、身份咨询和非知识库问题。
5. `compliance_check`：先规则识别隐私/禁用词，再可选 LLM 审查。
6. `synthesize`：合并业务结果；未通过合规时输出安全兜底答复。

### 8.3 路由实现的真实情况

虽然项目存在 `IntentRouterAgent`，可用 LLM 生成细粒度意图 JSON，但当前 `create_supervisor_graph()` 并没有把它注册为图节点。真正执行的是 `SupervisorNode.route_decision()` 前半段的确定性关键词路由：工单关键词进入 `ticket_handler`，选课/成绩等关键词进入 `knowledge_rag`，其余进入 `general_chat`。

`route_decision()` 后面还保留一段 LLM 路由代码，但位于前面的 `return` 之后，当前不可达。面试中应坦诚说明：这是为了演示稳定性而采用的规则路由主链路，LLM 意图路由是保留的扩展实现；应删除死代码或通过显式配置开关选择策略。

### 8.4 三层记忆不是一回事

| 类型 | 实现 | 生命周期 | 当前作用 |
| --- | --- | --- | --- |
| 工作记忆 | `WorkingMemory` 进程内字典 | 进程内、按 session | 保存最近路由等临时上下文 |
| 短期记忆 | `ShortTermMemory`，优先 Redis | 最多 20 条、默认 TTL 1800 秒 | API 写入与读取聊天历史 |
| 长期记忆 | `LongTermMemory`，FAISS + 元数据文件 | 可持久化 | 作为校园知识库供 RAG 检索 |
| 图 checkpoint | `MemorySaver` | 取决于 checkpointer 实现/进程 | 保存 LangGraph 图执行状态 |

当前 API 会把用户和助手消息写入短期记忆，但没有在每次调用图前把完整 Redis 历史回填到 `initial_state["messages"]`；因此多轮上下文在主图里主要依赖图 checkpoint 与工作记忆，而不是已读回的 Redis 历史。若要稳定支持多轮，应显式加载并转换历史消息，定义 token window，并清晰规定冲突时哪个状态源优先。

### 8.5 合规门禁的价值与边界

`ComplianceCheckerAgent` 的规则层匹配手机号、身份证、学号、邮箱及禁止承诺词，并可进行脱敏；低风险内容再通过 LLM 审查。所有业务分支都必须经过该节点后才能综合回答。

这是良好的“输出前统一门禁”结构。但它不是完整安全体系：真实部署还要有用户认证、权限校验、数据库审计、日志脱敏、限流、CORS 收紧、工具审批与人工复核。

## 9. 两个项目的端到端数据流对比

### 9.1 GPT Researcher 多 Agent 研究

```text
前端提交研究主题
  -> LangGraph host / ChiefEditor 状态图
  -> 初步检索 -> 规划章节 -> 人工审阅
  -> 各章节子图并发：研究 -> 审阅 -> 修订循环
  -> 写作 -> 事实核查循环 -> 可视化 -> 发布
  -> 报告与运行信息返回前端
```

核心目标是“长研究任务的计划、并发、质量闭环和交付”，因此有章节级子图和事实核查回路。

### 9.2 AI 客服单次请求

```text
浏览器 POST /api/chat
  -> FastAPI 生成/复用 session_id，写入短期记忆
  -> graph.ainvoke(initial_state, thread_id=session_id)
  -> Supervisor 条件路由
  -> RAG / 工单 / 通用聊天之一
  -> 合规检查
  -> 汇总最终文本、trace、intent
  -> 写入助手短期记忆 -> JSON 响应
```

核心目标是“低延迟服务分流与统一安全出口”，因此图结构比研究项目短，且所有业务分支都汇聚至合规节点。

## 10. 面试中可直接使用的对比回答

### 问：两个项目为什么都用 LangGraph？

答：它们都有明确的状态和决策流，但目标不同。GPT Researcher 是长任务编排，需要人工改计划、按章节并发研究、事实核查不通过回写，因此采用带循环的分层状态图。客服项目是短链路服务编排，Supervisor 根据意图进入 RAG、工单或通用聊天，之后统一通过合规节点。LangGraph 使路由、状态字段和终止条件可视化、可测试，而不是把控制流散落在 if/else 中。

### 问：LangChain 和 LangGraph 是替代关系吗？

答：不是。LangChain 提供模型调用、消息、Prompt、解析、Retriever、工具等能力；LangGraph 把这些能力放进有状态的节点，并管理分支、循环和 checkpoint。在 GPT Researcher 中，`PromptTemplate | model | PydanticOutputParser` 是 LangChain 链，研究审核循环是 LangGraph；在客服中，LangChain 消息对象被自定义模型客户端使用，LangGraph 管理客服协作图。

### 问：如何避免多 Agent 无效协作？

答：先定义每个 Agent 的专属输入、输出和质量责任，再决定是否需要它。研究项目中规划、章节研究、写作、事实核查的产物不同，回路有明确终止条件；客服项目中路由、业务处理、合规检查职责也不同。对于简单问答，直接模型调用更低延迟。还要评估每个节点的命中率、耗时、成本和对最终质量的增益。

### 问：客服项目的 RAG 有什么风险？

答：流程完整，但当前 `_simple_embedding()` 是哈希生成的随机向量，不能表达真实语义，检索结果只适合原型演示；工单也存于内存。上线应换真实 Embedding、重建索引、加入文档版本/权限过滤和离线检索评测，并将工单迁移到受鉴权的持久化数据库。

### 问：`thread_id` 和 `session_id` 有什么区别？

答：`session_id` 是业务会话标识，由 API 和短期记忆使用；这里将它传给 LangGraph 作为 `thread_id`，从而把一个用户会话映射到一条图执行线程。概念上二者可以不同，例如一个会话内并行发起多个长任务时，应使用不同 `thread_id` 并建立显式关联。

### 问：为什么合规检查放在业务 Agent 之后？

答：这样能审查最终候选答复和工单处理结果，形成统一出口。但高风险输入也应尽早拦截，生产方案通常是“输入预检 + 工具调用前鉴权 + 输出审查”三层防护，而不是只做最后一次检查。

## 11. 面试可讲的改进路线

### GPT Researcher

1. 恢复报告聊天的向量检索路径，按报告分块、加引用和重排，避免整份报告塞入 Prompt。
2. 为多 Agent 图接入明确的 checkpoint 持久化、失败恢复和幂等发布，特别是长研究任务。
3. 给事实核查与上下文压缩建立离线评测集，观察引用正确率、召回率、延迟和 token 成本。
4. 对 MCP 工具实行白名单、参数 schema、超时和调用审计，避免把不可信工具输出直接注入模型上下文。

### AI 客服

1. 将随机哈希 Embedding 替换为真实模型，并以 `Document + metadata + Retriever` 或等价的受测实现重构 RAG。
2. 用 Pydantic/JSON Schema 取代裸 `json.loads`，对工单与合规结果做强类型校验和重试。
3. 清理不可达的 LLM 路由代码；规则、LLM、混合路由以配置和评测决定，不要同时保留模糊的两条真相来源。
4. 将 `TicketStore` 改为数据库，增加身份认证、角色权限、幂等键、状态机和审计日志。
5. 把 Redis 历史在请求前回填图状态，或明确以持久 checkpointer 为唯一会话状态源，避免多轮上下文断裂。
6. 将当前一次性返回的 trace 改为 SSE/WebSocket 或 LangGraph streaming，才能让前端展示真实实时进度。

## 12. 简历表述模板

以下表述应按你实际完成和能演示的内容使用，不要把计划项写成已上线能力。

- 基于 LangGraph 设计多 Agent 有状态研究工作流，覆盖规划、人工反馈、章节级并发研究、审阅修订和事实核查回路；通过条件边表达审核闭环与最大修订次数。
- 基于 LangChain Loader、Document、Text Splitter、Embedding、Retriever 与上下文压缩组件构建研究资料处理链路，并通过 Pydantic 输出解析保障主题规划结构化。
- 基于 FastAPI 与 LangGraph 实现校园客服路由图，将知识问答、工单处理、通用对话统一接入合规审查出口，并以 `session_id/thread_id` 关联会话状态。
- 为客服原型实现 FAISS 知识检索、Redis 短期历史、MCP 风格工具注册及 OpenTelemetry 调用追踪；明确原型向量与内存工单的生产化改造边界。

## 13. 最后背诵版

**GPT Researcher** 中，LangChain 是多源资料处理、检索压缩、结构化输出和工具接入的基础组件；LangGraph 用于多 Agent 研究的计划、审阅、人工反馈和事实核查闭环。**AI 客服** 中，LangGraph 是 Supervisor 驱动的服务路由和合规汇聚图；LangChain 当前主要用于标准消息对象，RAG 向量部分为自定义原型实现，尚未全面使用 LangChain RAG 抽象。两者的共同点是“用状态管理协作”，差异是研究项目强调长任务质量闭环，客服项目强调请求分流、响应时延与安全出口。
