# PaperPilot

面向学术论文调研的多 Agent Research Workspace。PaperPilot 基于 GPT Researcher 二次开发，将通用深度研究流程改造成可配置的文献综述、方法对比和研究空白发现工作台。

## 项目定位

用户输入研究问题后，系统会生成结构化学术 brief，调用 Semantic Scholar、arXiv、Web 或本地论文资料进行检索，再由规划、检索、阅读和写作 Agent 协作生成带引用的研究报告。

## 核心能力

- 学科领域、研究任务、证据标准、时间范围和引用格式配置
- 文献综述、研究现状、方法对比、研究空白、论文复现调研和选题分析
- WebSocket 实时展示检索和 Agent 执行进度
- 复用 GPT Researcher 的 Basic、Detailed 和 LangGraph Multi-Agent 流程
- 输出研究空白、论文对比矩阵和 APA 7 / IEEE / MLA / Chicago 参考文献
- 支持 Web、Semantic Scholar、arXiv、本地 PDF、Hybrid 和 MCP 数据源

## 工作流

```text
研究问题 -> 学术配置校验 -> 查询拆解 -> 多源检索 -> 证据提取
         -> 论文方法对比 -> 研究空白分析 -> 引用检查 -> 报告导出
```

## 技术栈

- 前端：HTML、Bootstrap、JavaScript、WebSocket
- 后端：FastAPI、Uvicorn、Python 3.11+
- Agent：GPT Researcher、LangChain、LangGraph
- 数据源：Semantic Scholar、arXiv、Tavily/Web、本地文档、MCP
- 导出：Markdown、PDF、Word、JSON

## 快速启动

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

打开 `http://localhost:8000`，在 Academic research workspace 中选择研究类型和证据标准后提交问题。

常用环境变量包括 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`TAVILY_API_KEY`、`SEMANTIC_SCHOLAR_API_KEY`、`DOC_PATH` 和 `CONFIG_PATH`。DeepSeek 等 OpenAI-compatible 模型可通过 `OPENAI_BASE_URL` 和模型配置接入。

## 二次开发说明

`backend/academic/config.py` 提供学术配置的数据模型、枚举校验和研究 brief 构造；`server_utils.py` 负责 WebSocket payload 解包；`websocket_manager.py` 在进入上游报告 Agent 前注入学术约束。底层检索器、报告类型和 LangGraph 多 Agent 编排保持可升级，便于继续扩展论文元数据抽取、引用完整性评分和文献库。

## 面试项目亮点

- 设计了从前端配置到后端 Agent 的端到端参数契约
- 用不可变配置对象统一校验研究类型、证据标准、年份和引用格式
- 在不侵入上游核心的前提下增加领域 Prompt 适配层
- 通过 WebSocket 支持长任务实时进度和断线重连
- 结合 LangGraph 的规划、并行检索、证据汇总和报告生成流程

## 与 GPT Researcher 的关系

This project is a derivative work based on GPT Researcher by Assaf Elovic and contributors, licensed under Apache License 2.0. The academic research workflow, UI customization, configuration layer, and project-specific extensions are maintained in this repository.

本项目保留上游 `LICENSE`、版权和来源声明。论文调研工作流、Academic 配置、前端界面及项目扩展为本仓库新增内容。项目不是 GPT Researcher 官方发行版。

## License

Apache License 2.0。详见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
