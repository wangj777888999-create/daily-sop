# 12 · 评分与路线图：当前真实质量与下一步要做什么

这一章是**项目当前状态的快照 + 下一步的执行清单**。把它当作"和你自己（或 AI）的合同"——上面没列的事不做，列了的事一件件勾掉。

> 快照时间：2026-04 末，对应 commit `1ec1fae` 之后的工作树。

---

## 1. 评分总结

### 1.1 前端（综合 3.1 / 5）

| 维度 | 分数 | 关键证据 |
|---|---|---|
| 结构 | 3.5 | `src/services/`、`src/infrastructure/api`、`src/infrastructure/services` 三套并行；`domain/`、`use_cases/` 是空层 |
| 完成度 | 3.0 | HomePage、KnowledgePage、PolicyPage 80%+；**AnalyticsPage ~35%、DatabasePage ~25%（大量占位）**；AIPanel ~60%（无页面上下文联动）|
| 质量 | 2.5 | `any` 滥用 9 处（`src/services/sopApi.ts`、`SemanticAnnotation.vue`）；`console.error` 16 处；多处 catch 无用户反馈 |
| 一致性 | 4.0 | tokens 基本统一，少量硬编码（如 DatabasePage `#F2EDE4`）；`sopApi`/`knowledgeApi` 错误处理风格不一致 |
| 测试 | 1.0 | 无 .test/.spec、无 ESLint 配置；`vue-tsc --noEmit` 因 `any` 无法兜底 |

### 1.2 后端（综合 3.0 / 5）

| 维度 | 分数 | 关键证据 |
|---|---|---|
| 结构 | 4.0 | `sops/`、`knowledge/`、`api/` 边界清晰，无循环依赖 |
| 核心能力 | 3.0 | `code_parser.py` 支持 read/filter/merge/groupby/sort/to_excel；不支持 apply/pivot/fillna；`code_generator._validate_condition` 正则不允许 `in/not in` |
| 数据契约 | 3.0 | step↔order、status 已适配；**`output_file` 生成链断裂导致下载常 404** |
| 测试 | 2.5 | `test_models.py` / `test_data_source.py` 覆盖良好；parser/generator/sandbox/routes 几乎无测试 |
| 错误处理 | 2.5 | `backend/api/routes.py:54` 裸 `except:`；sops 路由无 logger；`sandbox.py` 把异常拍成字符串丢栈 |
| 整体质量 | 3.0 | `Dict[str, Any]` 泛滥；`parse()`、`_analyze_call()` 超 90 行；`storage.py` fcntl + atomic 写实现到位 |

### 1.3 一句话画像

> **原型完整度高，生产就绪度低。** 主要功能链路（SOP 解析 → 执行 → 下载、知识库 → RAG 检索 → 生成）能跑通；但工程基建（测试、错误处理、可观测性、个别反模式）还在初学期水平。

---

## 2. 下一步要做的事（按优先级）

### 重点 A — 完成 RAG 知识库

落地 `docs/rag-knowledge-base-plan.md` 二期：从"骨架可用"到"可检索可引用"。

#### A1. 后端

- [ ] `backend/knowledge/parser.py`：补全 docx / pdf / md / txt 解析；统一返回 `{text, metadata, chunks}`。
- [ ] `backend/knowledge/embedder.py`：模型加载逻辑加缓存，向量缓存到 `data/vectors/`（避免每次启动重 embed）。
- [ ] `backend/knowledge/vector_store.py`：按 `doc_id` 分集合；提供 `search(query, top_k, filters)` 的 metadata filter。
- [ ] `backend/knowledge/rag.py`：`build_prompt(query, chunks)` + `answer(query)`，输出 `{answer, sources:[{doc_id, chunk_id, text, score}]}`。
- [ ] `backend/api/knowledge_routes.py`：新增 `POST /api/knowledge/search`、`POST /api/knowledge/ask`。

#### A2. 前端

- [ ] `src/services/knowledgeApi.ts`：补 `search()`、`ask()` 封装；同时**把 `sopApi.ts` 也迁到 `request<T>()` 风格**（顺手统一）。
- [ ] `KnowledgePage.vue`：搜索框 + 结果卡 + 命中片段高亮；引用编号点击跳到原文。
- [ ] `PolicyPage.vue`：右栏 "参考资料" 区，AI 生成时调用 `/ask`，把 `sources` 渲染为脚注链接。
- [ ] `AIPanel.vue`：当当前页面是 Knowledge / Policy 时，把页面上下文（选中文档 ids）作为 `filters` 传入。

#### A3. 测试

- [ ] `backend/knowledge/test_rag.py` 覆盖 parser / embedder / store / rag 主路径。

---

### 重点 B — SOP 引擎增强 + 沙箱加固

把 SOP 从"演示可用"推到"复杂脚本可用"。

#### B1. 解析覆盖（`backend/sops/code_parser.py`）

- [ ] 新增算子：`apply` / `applymap` / `pivot_table` / `fillna` / `dropna` / `assign` / `astype`。
- [ ] 把 regex fallback 替换为 AST-only；不能识别的节点保留显式"未识别"占位 step（带原始片段）。

#### B2. 反向生成（`backend/sops/code_generator.py`）

- [ ] `_validate_condition()` 用 `ast.parse(mode='eval')` + 节点白名单替代正则，支持 `in` / `not in` / `isna()`。
- [ ] 与 `code_parser` 共享一份"算子规范"（建立 `backend/sops/operators.py`，单一来源）。

#### B3. 执行链路（`backend/api/routes.py` + `sandbox.py`）

- [ ] **修 output_file 缺失**：在生成代码末尾统一注入 `print("__SOP_RESULT__:" + json.dumps({"output_file": ...}))`，路由层据此填回 `ExecutionLog.output_file`，下载接口才不再 404。
- [ ] 删除 `routes.py:54` 裸 `except:`，改精准捕获 + `logger.exception`。
- [ ] 引入 `logging`（与 `knowledge_routes.py` 一致），结构化记录 exec_id / sop_id / duration / status。

#### B4. 沙箱加固（`backend/sops/sandbox.py`）

- [ ] `Popen` 加 `preexec_fn` 调 `resource.setrlimit`（CPU、AS、NOFILE、FSIZE）。
- [ ] import 检查改为子进程启动前 `ast.parse` + 节点遍历（白名单 module），**不再用 regex**；`CLAUDE.md` 关于 "regex 可绕过" 的说明同步更新为 "AST 校验，仍非强隔离"。
- [ ] 显式禁用 `__import__` / `eval` / `exec` / `open` 写非沙箱目录；超时时保留 stderr 末 N 行返回前端。

#### B5. 测试

- [ ] `sops/test_code_parser.py`：每个算子至少一条端到端 case。
- [ ] `sops/test_code_generator.py`：parser → generator round-trip 不变形。
- [ ] `sops/test_sandbox.py`：超时、资源限制、禁用导入、output_file 回填。
- [ ] `api/test_routes.py`：FastAPI `TestClient` 覆盖 SOP CRUD + execute + download。

---

### 暂不做（明确延后）

- **Analytics / Database 页面真实数据流**：占位但不在本期重点；用户愿意时再立项。
- **多用户 / 鉴权 / CORS**：本地单用户工具，按 `docs/local-audit-report.md` Q7 延后。
- **前端 ESLint / 测试基建**：建议等 RAG 与 SOP 完工后再单独立项；不阻塞当前路径。
- **过期的 `PROJECT_GUIDE.md`**：已改写为指向 `CLAUDE.md` 与本学习资料的桩文件。

---

## 3. 长期红线（如果项目要扩张）

下面这些事在"本地单用户"假设下可以不做。**一旦你想多人用、上公网、SaaS 化，必须先补**：

| 红线 | 触发条件 | 必须补的事 |
|---|---|---|
| 多用户 | 第 2 个用户登录 | 鉴权（OAuth/Session）、CORS、用户隔离 |
| 数据规模 | sops.json > 50MB | 换 SQLite / Postgres |
| 真公网 | 上线生产域名 | HTTPS、rate limit、DDoS 防护、日志告警 |
| 跑用户上传的代码 | 沙箱里跑陌生人的脚本 | gVisor / Firecracker / 容器化沙箱 |
| 高并发 | 同时执行 SOP 数 > 5 | 异步任务队列（Celery / RQ + Redis）|

---

## 4. 如何贡献

- 修小问题（typo、过时引用）：直接编辑对应 `docs/learning/*.md`，提 PR。
- 加新章节 / 新练习：先在 `docs/learning/00-README.md` 的目录里登记，再开新文件。
- 改路线图：本章是"下次会做什么"的事实标准。**改本章前先和当前路线图设计者对齐**（默认是项目主人）。

---

## 5. 收尾

到这里，你应该：

1. ✅ 知道项目现状的客观分数。
2. ✅ 知道"下一步"具体到文件 + 函数。
3. ✅ 知道哪些事**永远不要做**（除非项目走出本地单用户假设）。

愿你写代码顺手。如果路线图任意一项你想立刻动手——回到第 11 章 "Vibe Coding 工作流"，开个 plan mode，把对应 checklist 段贴给 AI 当 prompt 就能开工。
