# 11 · Vibe Coding 工作流：和 Claude Code 一起开发

> 本章你将看到的：
> - `CLAUDE.md`（项目记忆）
> - `docs/规划/2026-04-26-local-audit-report.md`、`docs/规划/2026-05-11-rag-knowledge-base-plan.md`（计划与审计）
> - 本仓库历史 commit message 风格

**Vibe Coding** 不是只让 AI 替你写代码，而是**和 AI 协作设计 + 探索 + 落地 + 维护**——AI 是"会写代码的资深工程师"，你是项目主导。这一章把本项目里**已经被验证可行**的协作范式提炼出来。

---

## 1. 三种最有用的协作姿势

### 1.1 计划模式（Plan Mode）：先想清楚再动手

Claude Code 的 Plan Mode 强制让 AI **先写一份 plan 文件**，你看过 / 改过 / 批准后才动代码。

**什么时候用**：

- 任何超过"改一两个文件"的工作。
- 你自己也没完全想清楚的功能（让 AI 帮你梳理）。
- 涉及多端协作的改动（前端 + 后端 + 数据契约）。

**怎么用**（命令行）：

```bash
# 进入 Claude Code，按一次 Esc 进入 plan mode 后输入需求
> 帮我把 sopApi.ts 里的 fetch 都改成用 knowledgeApi.ts 的 request<T> 封装
```

AI 会做：

1. 调 `Explore` 子代理读相关代码。
2. 写一份 `~/.claude/plans/xxx.md` 描述要改哪些文件、按什么顺序。
3. 把这份 plan 给你看，等你 approve 才落地。

**好处**：plan 是产物，留下来是项目记忆；改 plan 比改代码便宜 100 倍。

---

### 1.2 子代理（Sub-agents）：让 AI 自己派活

Claude Code 提供几个内置子代理：

- **`Explore`**：搜代码、读文件、回答"代码库哪里干啥"的问题。**只读**。
- **`Plan`**：基于 Explore 的发现设计实现方案。**只读**。
- **`general-purpose`**：能写代码的全能型，慎用。

**典型用法（在主对话里）**：

```
（你）请帮我看看 KnowledgePage.vue 是怎么用 useKnowledgeStore 的，
列出所有调用点和它们的目的。

（Claude） 我用 Explore 子代理看一下 ...
[启动 Explore 子代理读 KnowledgePage.vue]
[Explore 返回报告]
（Claude）这是结果：...
```

**为什么不直接自己读**：

- Explore 子代理跑在独立上下文里，**返回的内容是浓缩报告而不是原文**——主对话上下文不会被一千行代码塞爆。
- 多个 Explore 可以**并行**——一次开 3 个子代理分别看 3 个模块比串行 3 倍快。

> **这个项目的 plan 文件就是用这种姿势生成的**——主对话开 3 个 Explore 并行审计前端、后端、文档，再开 1 个 Plan 设计路线图。

---

### 1.3 项目记忆（CLAUDE.md）：一份"AI 入职手册"

`CLAUDE.md` 在项目根目录，每次 Claude Code 启动**自动读入**。它该写：

- ✅ 项目定位 + 一句话用途。
- ✅ 真实技术栈（不要写过时的）。
- ✅ 关键文件结构 + 跨栈契约。
- ✅ 常用命令（`npm run dev`、`pytest`）。
- ✅ "不要做"清单（不要加 CORS、不要装某些依赖）。

**不该写**：

- ❌ AI 自己能 grep 出来的事（"`xxx.py` 第 N 行做什么"）。
- ❌ 已经过时的快照（AI 会按它行动，反而错）。
- ❌ 太长——超过 200 行就开始稀释信号。

> 本项目的 `CLAUDE.md` 是个好范本——120 行左右，覆盖项目定位、栈、命令、契约、操作注意事项五块。

---

## 2. 提示工程：怎么和 AI 说话

### 2.1 把"模糊愿望"变成"明确目标"

❌ 模糊：
> 帮我优化一下 SOP 引擎

✅ 明确：
> 在 `backend/sops/code_parser.py` 里加 `fillna` 算子的 AST 识别，对应 `backend/sops/code_generator.py` 加 `_generate_fillna`，并在 `test_code_parser.py` 加一个 case，输入是 `df = df.fillna(0)`，期望解析出 `{action: "fillna", params: {df: "df", value: 0}}`。

明确目标 = 文件 + 期望行为 + 验证方式。**这一句话顶 AI 自己来回猜半小时**。

### 2.2 给 AI 看"已知缺口"

不要让 AI 重新发现你已经知道的问题。直接说：

> 我知道 `code_parser.py:54` 有裸 `except:`，今天先不修。这次只关注新增 `fillna`。

AI 会**精准聚焦你想改的事**，不再附送一堆"顺便的修复"。

### 2.3 给"不要做"清单

> 不要：① 加新依赖；② 改 sandbox.py；③ 重写已有测试。

这种"负面清单"在 vibe coding 里**比正向需求还管用**——AI 默认勤奋会想多做。

---

## 3. 调试范式：让 AI 帮你 systematic debug

### 3.1 报现象不报推断

❌ "我觉得 RAG 检索逻辑有 bug"  
✅ "在 PolicyPage 选了文档 A 提问，返回 sources 里出现了文档 B 的 chunk。后端日志附上。"

### 3.2 让 AI 形成多个假设

> 请列出 3 个可能导致这种现象的假设，并对每个假设给出验证步骤（grep / 加 print / 跑测试）。

**这是 systematic debugging skill 的核心**——AI 给你的不是"猜"，而是"3 条可验证的路径"。

### 3.3 修复后必复测

修好了之后**让 AI 自己跑一遍验证**：

> 请用 pytest 跑 `backend/sops/test_code_parser.py`，确认所有 case 通过。

如果它说"应该没问题"——你回它"请实际跑一遍"。**让 AI 自验证是基本素养**。

---

## 4. 长任务的拆分：TaskCreate / TodoList

写本套学习资料时，第一步是建任务列表（13 个文件 → 8 个任务批次）：

```
#1. Read key source files
#2. Write 00-README + 01-architecture
#3. Write 02 + 03 (frontend)
...
```

**为什么要拆**：

1. **进度可见**：你能看到"哪些做完、哪些还在排队"。
2. **失败可恢复**：某个任务挂了不影响其它。
3. **对话上下文清晰**：每完成一项标 done，AI 自己也知道做到哪了。

> 在 Claude Code 里直接跟它说"帮我把这件事拆成任务列表追踪"就行。

---

## 5. 持续改进：Memory + Feedback

Claude Code 有个`memory/` 系统：你说"以后写测试都用 pytest 的 fixture 而不是 setUp"，AI 会写到 memory 文件，**未来对话里自动遵守**。

**典型该 memory 的内容**：

| 类型 | 例子 |
|---|---|
| 用户角色 | 我是数据分析师，Python 熟，前端 React 不熟（→ 解释前端时类比后端术语）|
| 工作偏好 | 不要在 docstring 里写 type hint，用注解就行 |
| 项目反复出现的痛点 | RAG 检索调试时，先看 `data/chroma_db/` 是否有数据再排查 |

> **善用 memory**：第二次告诉 AI 同样的偏好就该 memory，第三次还要重复说就是工具用得不好。

---

## 6. 一个完整的 vibe coding 工作循环

```
1. 需求来了
   ↓
2. 和 AI 聊，让它写 plan（plan mode）
   ↓
3. 看 plan，挑战 / 改 / 批准
   ↓
4. AI 落地代码（subagent-driven 或主对话直接做）
   ↓
5. 跑测试 / 起服务验证
   ↓
6. 复盘：把"踩到的坑" 沉淀到 memory 或 CLAUDE.md
   ↓
7. commit + 写好 commit message
```

> 第 6 步最重要也最容易被跳过——这是"vibe coding 越来越好用"的复利来源。

---

## 7. 不要让 AI 做的事

| 不要 | 为什么 |
|---|---|
| 没批准就 push 到 main | 不可逆，破坏团队信任 |
| 没批准就 `git reset --hard` / 删除文件 | 容易丢未提交的工作 |
| 在你不在时回复用户 / 同事消息 | 沟通必须你审 |
| 装陌生新依赖 | 供应链风险，先你自己评估 |
| 改你没让它改的代码 | 哪怕"顺便修复"也要先告知 |

> CLAUDE.md / memory 里**写明授权范围**，比每次反复说省事——但即便写了，遇到不可逆操作 AI 仍应再确认。

---

## 动手练习

1. **改造一个小需求走全流程**：选第 6 章末尾的 "加 `fillna` 算子" 练习，**强制走 plan mode**——你会感受到"先 plan 再 code" 比"直接 code"省时间。
2. **维护 CLAUDE.md**：在 CLAUDE.md 里加一段"已知反模式"区，把第 12 章总结的待修项列进去。下次 AI 改这些区域会自动绕开。
3. **写自己的子代理**：给项目加 `.claude/agents/sop-tester.md`，定义一个专门跑 SOP 测试的子代理。试试调用它。

## 延伸阅读

- Anthropic 官方 [Claude Code 文档](https://docs.claude.com/en/docs/claude-code/overview)。
- 仓库内 `CLAUDE.md` 本身——每个项目都该有一份。
- 想体验更深的 agent：本项目的 `~/.claude/skills/` 下有几十个内置 skill（systematic-debugging、planning-with-files、karpathy-guidelines 等），逐个读会大开眼界。
