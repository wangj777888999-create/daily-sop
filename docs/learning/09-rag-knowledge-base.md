# 09 · RAG 知识库全链路：从分块到引用

> 本章你将看到的代码：
> - `backend/knowledge/parser.py`、`chunker.py`、`embedder.py`、`vector_store.py`、`generator.py`、`rag.py`
> - `backend/api/knowledge_routes.py`
> - `docs/rag-knowledge-base-plan.md`（详细规格）

**RAG**（Retrieval-Augmented Generation）= 检索增强生成。一句话讲清：**让 LLM 在生成前，先从你自己的资料库里找到相关片段，再把这些片段拼进 prompt**。

为什么不直接把所有资料塞进上下文？因为：

- 资料量动辄几十 MB，单次 prompt 装不下。
- 大部分资料和当前问题无关，塞进去反而干扰 LLM。
- 资料更新时不必重训模型。

---

## 1. 整体五段式

```
[用户问题]
   │
   ▼
1. 切分 (chunk)         ──▶ 把长文档切成 200-500 字的语义块
   │
   ▼
2. 向量化 (embed)        ──▶ 每块算一个 d 维向量
   │
   ▼
3. 检索 (retrieve)       ──▶ 拿用户问题向量，在向量库里找 top_k 相似块
   │
   ▼
4. 拼 prompt (augment)   ──▶ system_prompt + 检索结果 + user_question
   │
   ▼
5. 生成 + 引用 (generate) ──▶ 调 Claude，回答末尾标注 [1][2] 引用
```

本项目的代码按这个顺序分文件——读一段配一段就行。

---

## 2. 分块（chunker.py）：中文优化

通用 RAG 教程会让你"按 500 字滑窗切"——对中文不太适合（会切到句子中间）。本项目的做法（`chunker.py:6-43`）：

1. **尊重 parser 给出的标题/段落边界**（PDF/DOCX 解析器已经知道哪里是 H1、哪里是段落）。
2. **合并过短的相邻段**：< 50 字的孤立段拼到下一段。
3. **拆过长的段**：> 500 字的段在句号 `。`、问号 `？`、感叹号 `！` 边界拆。
4. **每个 chunk 携带 `heading_path`**："第三章 / 3.2 节 / 实施细则" —— 检索结果里展示给用户做"出处"。
5. **相邻 chunk 间 50 字 overlap**：避免句子刚好被切到块边缘时检索丢失。

> 这五步是**中文 RAG 的"基本盘"**，做对了召回率立刻拉高。

---

## 3. 向量化（embedder.py）：单例 + 1024 维

```python
# backend/knowledge/embedder.py:7-26
class EmbeddingService:
    """Singleton embedding service using text2vec-large-chinese (1024-dim)."""
    _instance = None

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info("Loading text2vec-large-chinese model (...)")
            from text2vec import SentenceModel
            self._model = SentenceModel("shibing624/text2vec-large-chinese")
        return self._model

    @property
    def dimension(self) -> int:
        return 1024

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self.model.encode(texts)
        return vectors.tolist()
```

要点：

- **单例模式**：`get_embedding_service()` 全局只加载一次模型。第一次加载十几秒，之后毫秒级。
- **`text2vec-large-chinese`**：HuggingFace 上最常用的中文 embedding 模型之一，1024 维。如果你的资料是英文为主，换成 `bge-large-en` 或 `e5-large-v2`。
- **批量 vs 单条**：`embed_texts` 接 list，让模型一次跑完更快（GPU 利好；CPU 也有少量收益）。
- **lazy load**：模型在 `model` property 第一次访问时加载——但 `backend/main.py:11-16` 的 startup 钩子提前触发了它，避免第一个用户请求等。

---

## 4. 向量存储（vector_store.py）：ChromaDB

```
data/chroma_db/
  ├── chroma.sqlite3
  └── ...
```

ChromaDB 本质是 SQLite + HNSW 索引的轻量级向量库——**单文件、零运维、10 万级别 chunk 没问题**。

接口（`vector_store.py` 的 `search`）：

```python
def search(self, query_embedding, top_k=5, doc_ids=None) -> List[dict]:
    # 返回 [{doc_id, doc_name, chunk_text, score, page, heading_path, ...}, ...]
```

**`doc_ids` filter**：用户在 KnowledgePage 里勾选了几份文档时，检索只在这几份内做——这正是 AIPanel "上下文感知" 要做的事。

---

## 5. 检索 + 上下文拼接（rag.py）

```python
# backend/knowledge/rag.py:17-49
def retrieve(self, query: str, top_k: int = 5,
             doc_ids: Optional[List[str]] = None) -> List[SearchResult]:
    query_embedding = self.embedder.embed_query(query)
    raw_results = self.vector_store.search(query_embedding, top_k=top_k, doc_ids=doc_ids)
    ...
    return results

def build_context(self, results: List[SearchResult]) -> str:
    if not results:
        return ""
    parts = ["<reference_documents>"]
    for i, r in enumerate(results, 1):
        location = r.heading_path or "正文"
        parts.append(
            f"[{i}] {r.doc_name} — {location}\n"
            f"内容：{r.chunk_text}\n"
        )
    parts.append("</reference_documents>")
    return "\n".join(parts)
```

注意几点：

- **`<reference_documents>` 标签包裹**：Claude / GPT 类模型对结构化标签的"理解力"很好，比裸贴文本更不会"忘记这段是引用"。
- **`[1] [2] [3]`** 从 1 开始编号：让模型在生成时能用 `[1]` 来引用，前端再把数字换成可点链接（脚注）。

---

## 6. 生成（generator.py）：风格切换 + 引用提取

```python
# backend/knowledge/generator.py:7-19
STYLE_PROMPTS = {
    "policy": "你是一位政策文件撰写专家。请参考以下参考文档的表达方式、格式和知识，"
              "用正式、严谨的公文风格撰写。保持与参考文档一致的章节结构、用语规范和专业术语。",
    "report": "你是一位教育成果报告撰写专家。...",
    "general": "请参考以下文档的内容和表达方式，生成内容时保持相似的风格和术语。",
}
```

**为什么按场景分 prompt？** 因为政策文件的口吻和报告完全不同——同一段检索结果，生成出来的形态应该截然有别。

调用 Claude（`generator.py:49-63`）：

```python
import anthropic
client = anthropic.Anthropic(api_key=api_key)
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    system=system_prompt,
    messages=[{"role": "user", "content": prompt}],
)
generated_text = message.content[0].text
sources = _extract_sources(context_chunks)
return generated_text, sources
```

`_extract_sources` 用正则反向解析出"参考文档了哪些"——**这一步未来应该让 LLM 在响应里自己标注，而不是从 context 反推**（因为 LLM 实际可能只用了 5 篇里的 2 篇）。这是路线图 A 的优化点。

---

## 7. 优雅降级：没有 API key 时怎么办

```python
# backend/knowledge/generator.py:39-47
if not api_key:
    logger.warning("No ANTHROPIC_API_KEY set, returning template response")
    return (
        f"[需要设置 ANTHROPIC_API_KEY 环境变量]\n\n"
        f"系统将基于以下 ... 篇参考文档生成内容：\n\n"
        f"{context_chunks}\n\n"
        f"任务：{prompt}",
        [],
    )
```

**没有 key 时不抛错，而是把检索结果原样返回**——用户能看到"我们至少找到了哪些资料"。这是 AI 应用的关键素养（详见第 10 章）。

---

## 8. 完整链路：用户点"撰写政策"那一秒发生了什么

1. 前端 `PolicyPage.vue` → `knowledgeApi.generateContent({ prompt, doc_ids, top_k: 5, style: 'policy' })`。
2. POST `/api/knowledge/generate` → `RAGPipeline.generate(...)`。
3. `embed_query` → 1024 维向量。
4. `vector_store.search(query_emb, top_k=5, doc_ids=...)` → 5 个 chunk。
5. `build_context(results)` → `<reference_documents>...` 字符串。
6. `generate_with_context` → 调 Claude → 生成文本 + sources。
7. 响应给前端 `{ generated_text, sources: [{index:1, name, location, text}, ...] }`。
8. 前端把 `[1][2]` 在生成正文里替换为 `<sup><a href="#ref-1">[1]</a></sup>`，右栏渲染脚注。

---

## 9. RAG 不是银弹（已知坑）

| 坑 | 怎么办 |
|---|---|
| 检索召回差（用户问得抽象时找不到对的片段）| 多查询重写（HyDE）、混合检索（BM25 + 向量）、Re-rank |
| 同义词召不到（"老师"找不到"教师"）| 用更强 embedding（BGE-Reranker、Cohere）；或事先建同义词表 |
| 引用乱编 | `_extract_sources` 改为让 LLM 自己输出 JSON 格式 sources |
| 长文档关键信息被切散 | 加"hierarchy 检索"：先匹配章节标题，再深入到段落 |
| API key 在前端 / 后端怎么管 | **永远后端管**；前端只发 prompt，后端读环境变量 |

---

## 动手练习

1. **跑通整条链路**：上传一份 docx 到 KnowledgePage，在 PolicyPage 选中它、问一个问题，看返回的 sources 字段——脑里把第 8 节那 8 步对应到代码上。
2. **加一个 BM25 兜底**：在 `vector_store.search` 召回结果不足时，回退到 ripgrep 或全文检索（`re.search`）；目标是"召回不要全靠向量"。
3. **写"引用 JSON 协议"**：改 `system_prompt` 让 Claude 在末尾输出 `<sources>[{"id":1,"used":true}, ...]</sources>` JSON，再删掉 `_extract_sources` 的 regex 反推。

## 延伸阅读

- 项目内 `docs/rag-knowledge-base-plan.md` —— 完整规格的事实标准。
- [Anthropic 的 Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval) —— 给 chunk 自动加上下文摘要后再 embed。
- [HyDE 论文](https://arxiv.org/abs/2212.10496) —— 用 LLM 改写用户 query 提高召回。
- ChromaDB [docs](https://docs.trychroma.com/)：collection、metadata filter、where 子句。
