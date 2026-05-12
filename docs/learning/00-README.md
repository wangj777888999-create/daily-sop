# 智能工作台 学习手册（导览）

这是一份"项目导览式"中文教程：**不重复百科式概念**，而是带你穿过本仓库（`ai_analyst_v2`）的真实代码，搞清楚为什么这一处要这么写、这么写带来什么取舍。

读完之后你应该能：

1. 一眼看懂本项目的整体架构与数据流；
2. 在 Vue 3 + FastAPI + Pandas + RAG 这套组合里独立做小改动；
3. 把"项目导览 + Vibe Coding 工作流"复制到自己的下一个项目去。

---

## 适合谁读

- 已经能看懂 Python 和 JavaScript / TypeScript 基础语法。
- 用过至少一次 Vue 或 React、用过一次 FastAPI 或 Flask；不需要精通。
- 想从"按教程写 Demo"过渡到"看真实代码做改动 / 用 AI 协作开发"。

> 完全零基础读者建议先快速过一遍 [MDN JavaScript 入门](https://developer.mozilla.org/zh-CN/docs/Learn/JavaScript) 和 [FastAPI 官方教程前 4 节](https://fastapi.tiangolo.com/tutorial/)。

---

## 推荐学习路径

> 全部章节都假设你已经能在本机跑起来项目（`npm run dev` + `uvicorn main:app --reload --port 8003`）。如果还没跑起来，先按 `CLAUDE.md` 的 "Commands" 章节配好环境。

| 路径 | 推荐顺序 | 适合谁 |
|---|---|---|
| **快速通读**（半天）| 01 → 05 → 09 → 11 | 想 1 小时建立全景、快速进入 vibe coding |
| **前端方向**（1–2 天）| 01 → 02 → 03 → 05 → 10 → 11 | 偏前端 / UI / 设计系统 |
| **后端方向**（1–2 天）| 01 → 04 → 05 → 08 → 09 | 偏数据、存储、RAG |
| **AI 应用方向**（2–3 天）| 01 → 09 → 10 → 11 → 12 | 想做 AI 产品/RAG/Agent |
| **彻底通读**（3–5 天）| 00 → 12 顺序（跳过归档章节）| 想把这套技能整体内化 |

---

## 章节目录

| # | 标题 | 核心问题 |
|---|---|---|
| 01 | [架构总览](./01-architecture-overview.md) | 为什么是 Vue + FastAPI + JSON 这套组合，不是别的 |
| 02 | [前端 Vue 3 实战](./02-frontend-vue.md) | `main.ts` → 一个页面之间发生了什么 |
| 03 | [前端设计系统](./03-frontend-design-system.md) | tokens、Tailwind、composable 三层是怎么衔接的 |
| 04 | [后端 FastAPI 实战](./04-backend-fastapi.md) | 路由、Pydantic、依赖注入怎么落地 |
| 05 | [前后端契约与适配器](./05-cross-stack-contracts.md) | 两端字段不一致时，单点适配器怎么救场 |
| ~~06~~ | ~~SOP 引擎与 AST~~ | _已归档（SOP 废弃）_ |
| ~~07~~ | ~~沙箱与执行~~ | _已归档（SOP 废弃）_ |
| 08 | [JSON 持久化与文件锁](./08-storage-json-locking.md) | 不上数据库时，怎样把"工程靠谱"做出来 |
| 09 | [RAG 知识库全链路](./09-rag-knowledge-base.md) | 分块 → 向量化 → 检索 → prompt → 引用 |
| 10 | [AI 应用工程模式](./10-ai-application-patterns.md) | 上下文注入、流式、回退、prompt 设计 |
| 11 | [Vibe Coding 工作流](./11-vibe-coding-workflow.md) | 与 Claude Code / 子代理 / 计划模式协作 |
| 12 | [评分与路线图](./12-roadmap-and-quality.md) | 当前真实质量、下一步要修什么 |

---

## 阅读约定

- **代码引用格式**：`backend/sops/sandbox.py:81`（路径 + 行号），点过去能直接定位。
- **粗体强调**：通常表示"决策点"或"已知坑"。
- **本仓库一切以 `CLAUDE.md` 为事实标准**。如果你发现教程里的某行号已对不上代码，欢迎修订（见 12 章末尾的"如何贡献"）。

---

## 与 Vibe Coding 的关系

每章末尾都有一节"动手练习"，所有练习都设计成"可以让你和 Claude Code 协作完成"——比如：

- "给 `code_parser.py` 加 `fillna` 算子的支持，并补一个测试。"
- "把 `sopApi.ts` 也改用 `knowledgeApi.ts` 的 `request<T>()` 封装。"

第 11 章会专门讲怎么把这种"小改动"做得高效：什么时候用 Plan Mode、什么时候开 Explore 子代理、怎么用 `CLAUDE.md` 持久化项目知识。

> **建议读法**：先读章节本体，遇到练习时不要立刻动手，先在本机用 Claude Code 复现一遍——这才是 vibe coding。
