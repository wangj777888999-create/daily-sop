"""
RAG 模块召回 & 能力测试（使用知识库现有文档）
运行方式：cd backend && python rag_test.py
需要后端已启动（uvicorn main:app --port 8003）
"""
import sys
import json
import requests

BASE = "http://localhost:8003/api"


def color(text, code): return f"\033[{code}m{text}\033[0m"
def green(t):  return color(t, "32")
def red(t):    return color(t, "31")
def yellow(t): return color(t, "33")
def bold(t):   return color(t, "1")
def dim(t):    return color(t, "2")
def cyan(t):   return color(t, "36")


# ─────────────────────────────────────────────────────────────────────────────
# 1. 获取知识库文档列表
# ─────────────────────────────────────────────────────────────────────────────
def fetch_docs():
    r = requests.get(f"{BASE}/knowledge/documents", timeout=5)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 2. 搜索
# ─────────────────────────────────────────────────────────────────────────────
def search(query: str, category: str = None, top_k: int = 5):
    body = {"query": query, "top_k": top_k}
    if category:
        body["category"] = category
    r = requests.post(f"{BASE}/knowledge/search", json=body, timeout=30)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 3. RAG 生成
# ─────────────────────────────────────────────────────────────────────────────
def generate(prompt: str, category: str = None, style: str = "general", top_k: int = 5):
    body = {"prompt": prompt, "style": style, "top_k": top_k}
    if category:
        body["category"] = category
    r = requests.post(f"{BASE}/knowledge/generate", json=body, timeout=60)
    r.raise_for_status()
    return r.json()


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(bold("\n══════════════════════════════════════════════"))
    print(bold("         RAG 召回 & 生成能力测试"))
    print(bold("══════════════════════════════════════════════\n"))

    # ── 检查后端 ──────────────────────────────────────────────────────────────
    try:
        docs = fetch_docs()
    except Exception as e:
        print(red(f"❌ 无法连接后端: {e}"))
        sys.exit(1)

    if not docs:
        print(red("❌ 知识库为空，请先上传文档再运行测试"))
        sys.exit(1)

    # ── 展示文档列表 ───────────────────────────────────────────────────────────
    print(bold(f"── 知识库现有文档（共 {len(docs)} 份）────────────────────"))
    by_cat = {}
    for d in docs:
        cat = d.get("category", "未知")
        by_cat.setdefault(cat, []).append(d)

    cat_labels = {"policy": "政策文件", "activity": "活动报告", "data": "经营数据报告"}
    for cat, cat_docs in by_cat.items():
        print(f"\n  {cyan(cat_labels.get(cat, cat))} ({len(cat_docs)} 份)")
        for d in cat_docs:
            chunks = d.get("chunk_count", "?")
            size   = d.get("size_bytes", 0)
            sz_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
            print(f"    · {d['name']}  {dim(f'chunks={chunks}  {sz_str}')}")

    # ── 让用户输入测试查询 ─────────────────────────────────────────────────────
    print(bold("\n── 召回测试 ─────────────────────────────────────────────"))
    print("每次输入一条查询，回车执行。输入 'q' 退出，输入 'g:查询内容' 触发 RAG 生成。")
    print(dim("分类前缀：p: 政策  a: 活动  d: 经营数据  留空=跨库\n"))

    query_results = []

    while True:
        try:
            raw = input(bold("查询 > ")).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not raw or raw.lower() == "q":
            break

        # 解析前缀
        generate_mode = False
        category = None

        if raw.startswith("g:"):
            generate_mode = True
            raw = raw[2:].strip()

        if raw.startswith("p:"):
            category = "policy"
            raw = raw[2:].strip()
        elif raw.startswith("a:"):
            category = "activity"
            raw = raw[2:].strip()
        elif raw.startswith("d:"):
            category = "data"
            raw = raw[2:].strip()

        if not raw:
            continue

        cat_str = f"[{cat_labels.get(category, '跨库')}]" if category else "[跨库]"
        mode_str = "[生成模式]" if generate_mode else "[检索模式]"
        print(dim(f"  → {mode_str} {cat_str}"))

        if generate_mode:
            # RAG 生成
            try:
                print(dim("  正在检索+生成，请稍候..."))
                resp = generate(raw, category=category)
                print()
                print(bold("  ── 生成结果 ─────────────────────────────────"))
                print(resp.get("generated_text", "（无内容）"))
                sources = resp.get("sources", [])
                if sources:
                    print(dim(f"\n  引用来源 ({len(sources)} 条):"))
                    for s in sources[:3]:
                        print(dim(f"    · {s}"))
                print()
            except Exception as e:
                print(red(f"  ✗ 生成失败: {e}"))
        else:
            # 纯检索
            try:
                results = search(raw, category=category, top_k=5)
            except Exception as e:
                print(red(f"  ✗ 检索失败: {e}"))
                continue

            if not results:
                print(yellow("  无结果"))
                continue

            print(f"  Top-{len(results)} 结果：")
            for i, r in enumerate(results, 1):
                score   = r.get("score", 0)
                name    = r.get("doc_name", "")
                path    = r.get("heading_path", "")
                text    = r.get("chunk_text", "").replace("\n", " ")[:80]
                page    = r.get("page", 0)
                bar     = green("█") * int(score * 10) + dim("░") * (10 - int(score * 10))
                loc     = f"  §{path}" if path else (f"  p{page}" if page else "")
                print(f"  #{i} {bar} {score:.4f}  {bold(name)}{dim(loc)}")
                print(dim(f"      {text}…"))

            query_results.append({"query": raw, "category": category, "top1": results[0]})
            print()

    # ── 会话汇总 ───────────────────────────────────────────────────────────────
    if query_results:
        print(bold("\n══ 本次测试汇总 ══════════════════════════════════════"))
        for i, qr in enumerate(query_results, 1):
            top1 = qr["top1"]
            print(f"  Q{i}: {qr['query']}")
            print(dim(f"       Top1 → {top1['doc_name']}  score={top1.get('score',0):.4f}"))
        print()


if __name__ == "__main__":
    main()
