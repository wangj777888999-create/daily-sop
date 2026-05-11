# 10 · AI 应用工程模式

> 本章你将看到的代码：
> - `backend/knowledge/generator.py`（Claude 调用 + 优雅降级）
> - `src/ui/components/layout/AIPanel.vue`（流式 / 打字机效果）
> - `src/stores/aiChat.ts`

这一章不讲具体接口怎么调，而是讲**做 AI 应用绕不过去的几个工程问题**——它们不是某个框架特有，而是你做任何 AI 产品都会撞上的。

---

## 1. AI 调用的"三层结构"

不管多复杂的 AI 应用，请求路径都长这样：

```
[UI 层]                  ← 用户看到的对话气泡 / 打字机
  │
[业务层]                 ← Prompt 模板、上下文注入、对话历史管理
  │
[模型 API 层]            ← Claude / GPT 的 SDK 调用
```

本项目对应：

| 层 | 文件 |
|---|---|
| UI | `AIPanel.vue`、`PolicyPage.vue` |
| 业务 | `backend/knowledge/rag.py`、`generator.py` |
| 模型 API | `anthropic.Anthropic(api_key=...)` |

**保持三层分离的好处**：换模型时只改最底层（GPT → Claude → Gemini），prompt 工程改动只在业务层，UI 不动。

---

## 2. Prompt 工程的几条实战经验

### 2.1 系统提示与用户消息分开

```python
# backend/knowledge/generator.py:53-58
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=system_prompt,                                # ← 系统提示（角色 + 上下文）
    messages=[{"role": "user", "content": prompt}],     # ← 用户消息
)
```

**system 放角色 + 风格 + 检索上下文**；**user 只放真实的问题/任务**。这样：

- 同一份 RAG 上下文可以喂给不同的"角色"复用。
- 多轮对话时，user 消息按历史展开，system 只占 1 条。

### 2.2 用结构化标签包裹上下文

```
<reference_documents>
[1] 《2026 教育白皮书》 — 第三章
内容：…
</reference_documents>
```

LLM 对 XML 风格标签格外敏感（训练时见得多）。**比直接 `参考资料：xxxx` 效果好得多**。

### 2.3 风格指令要"带例子"

`generator.py:7-15` 的 STYLE_PROMPTS：

```python
"policy": (
    "你是一位政策文件撰写专家。请参考以下参考文档的表达方式、格式和知识，"
    "用正式、严谨的公文风格撰写。保持与参考文档一致的章节结构、用语规范和专业术语。"
),
```

> 这种"角色 + 期望 + 约束"的三段式是好开头。**进阶**：再加 1-2 个 few-shot 例子（"以下是合格输出的样例 ..."），效果会再上一个台阶。

### 2.4 prompt 永远是代码而不是字符串

把 prompt 写成 Python f-string 是 OK 的（项目这么写的）。**但当 prompt 长到 50 行以上**，建议挪到独立文件 `prompts/policy.j2`（Jinja2 模板）或 `.md`，再用模板引擎插值。

---

## 3. 上下文管理：什么时候该往里塞

### 3.1 长度预算

Claude Opus 4.7 的上下文 200K token——但**塞满不等于效果好**。检索结果太多，LLM 会"注意力稀释"，反而不如 5 段精准的更管用。

经验值：

| 任务 | 推荐上下文 token |
|---|---|
| 单轮 Q&A | 2K - 8K |
| 长文撰写 | 8K - 32K |
| 多轮对话 | 始终留 50% 给历史 |
| 复杂 agent | 32K+ + 工具调用历史 |

### 3.2 历史压缩

多轮对话开太久后历史会爆。两种办法：

1. **滚动窗口**：只保留最近 N 轮。简单粗暴，丢早期信息。
2. **摘要压缩**：让 LLM 自己把"开头到第 N 轮"压成 200 字摘要，只保留摘要 + 最近几轮。

> 本项目没做（AIChat 还很简单），但你做"长对话 agent"必然要做。

### 3.3 工具结果的去噪

如果你接入了 search/code-exec/RAG 工具，工具返回结果可能很大（一次 ripgrep 几千行）。**永远在塞回 LLM 之前做截断或摘要**——要不几轮就把上下文顶爆。

---

## 4. 流式输出：让等待"看起来"快

```python
# 假设的流式（本项目目前未做）
with client.messages.stream(...) as stream:
    for text in stream.text_stream:
        yield text
```

前端用 SSE（Server-Sent Events）或 WebSocket 接，逐字渲染——**用户感受到的延迟降一半以上**，哪怕总耗时一样。

`AIPanel.vue` 现在用的是"假打字机"（前端 setInterval 一字一字加），等接入流式后可以无缝切换到真流。

---

## 5. 优雅降级：AI 失败时仍要"有用"

`backend/knowledge/generator.py:39-47` 的写法值得抄：

```python
if not api_key:
    logger.warning("No ANTHROPIC_API_KEY set, returning template response")
    return (
        f"[需要设置 ANTHROPIC_API_KEY 环境变量]\n\n"
        f"系统将基于以下 {context_chunks.count('[文档名')} 篇参考文档生成内容：\n\n"
        f"{context_chunks}\n\n"
        f"任务：{prompt}",
        [],
    )
```

**关键："API 用不了"是一种业务状态而不是异常**——返回检索到的资料原文 + 说明文案，用户至少有东西用。

同理，try/except 里 catch 模型错误后也别 raise，应该返回"生成失败 + 部分上下文"，让用户能复制走。

---

## 6. 安全：API key、PII、注入

| 关注点 | 做法 |
|---|---|
| API key | **永远后端**。前端永远只发请求，后端读环境变量。本项目就是这么做的（`api_key = os.environ.get("ANTHROPIC_API_KEY")`）|
| PII（用户身份信息） | 在送进 prompt 前先脱敏（电话、身份证、邮箱）|
| Prompt 注入 | 用户输入永远在 user 消息里，不要拼进 system；用 `<user_input>` 标签包裹更安全 |
| 输出校验 | 让 LLM 输出 JSON 时，**用 `try: json.loads(text)` 兜底**；失败重试 1 次或返回原文 |

---

## 7. 评估：什么算"做得好"

AI 应用很难像传统软件那样写单元测试（输入 → 期望输出）。常见做法：

1. **eval 数据集**：手工攒 50-100 个"典型问题 → 期望要点"的 case，每次改 prompt 后跑一遍人工打分。
2. **A/B 实验**：两版 prompt 各跑 100 个 case，让人选更好的那条。
3. **LLM-as-judge**：用更强的模型（Claude Opus）打分弱模型（Haiku）的输出。

本项目还在原型期，没做 eval。**当你的产品有 1000 用户时，eval 不做就翻车**——记下这条。

---

## 8. 成本：永远在的紧箍咒

每次模型调用都花钱。建议：

- **缓存频繁出现的相同 prompt**（比如 system_prompt + 同一份 RAG 上下文 + 不同问题）。Anthropic 提供 prompt caching，可以**只对变化部分计费**。
- **Haiku 兜底**：简单分类任务（"这个问题是政策类还是报告类？"）用 Haiku 比 Sonnet/Opus 便宜 10 倍。
- **观测**：每次调用记录 input_tokens / output_tokens，给月成本算账。

---

## 9. 对话状态：什么放前端、什么放后端

本项目当前：

- **前端 Pinia store** (`aiChat.ts`)：消息列表、isTyping 状态、quickActions。
- **后端**：完全无状态——每次请求都自带完整 prompt。

**这种"无状态后端 + 有状态前端"是单用户工具的合理选择**——刷新就丢历史，但部署、扩展简单。

如果你做多人 / 跨设备同步的 AI 应用，把对话历史挪到后端 + 数据库（Postgres / DynamoDB / Redis）是必修课。

---

## 动手练习

1. **接 prompt caching**：把 `generator.py` 改成用 [Anthropic prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)，看同一组 RAG 上下文重复使用时成本下降多少。
2. **写第一份 eval 集**：手攒 10 个"政策撰写"任务（含输入文档 + 期望要点），写一个脚本跑当前 RAG，输出表格让你打分。
3. **加 Haiku 路由**：在 `RAGPipeline.generate` 入口先用 Haiku 跑一次"分类"——如果用户问的是"日常闲聊"，直接拒绝走 RAG（节省钱 + 快）。

## 延伸阅读

- Anthropic [Prompt Engineering Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering)。
- [Prompt Engineering Guide](https://www.promptingguide.ai/) —— 涵盖 zero-shot、few-shot、CoT、Tree of Thought 等。
- 想理解流式：[Anthropic Streaming](https://docs.anthropic.com/en/api/messages-streaming)。
- 评估方面，[OpenAI Evals](https://github.com/openai/evals) 是个不错的起点（即使你用 Claude，框架可以照搬）。
