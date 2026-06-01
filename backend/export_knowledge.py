"""
知识库导出脚本：将 chunks 导出为其他大模型可用的参考文件。

用法:
  cd backend && source .venv/bin/activate && python export_knowledge.py          # 导出全部
  cd backend && source .venv/bin/activate && python export_knowledge.py --category policy   # 仅政策
  cd backend && source .venv/bin/activate && python export_knowledge.py --search "教练考勤"  # 搜索导出
"""
import json
import argparse
from pathlib import Path

CHUNKS_PATH = Path(__file__).parent.parent / "data" / "knowledge_chunks.json"
META_PATH = Path(__file__).parent.parent / "data" / "knowledge_metadata.json"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "exports"


def load_data():
    with open(CHUNKS_PATH) as f:
        chunks = json.load(f)
    with open(META_PATH) as f:
        meta = json.load(f)
    return chunks, {m["id"]: m for m in meta}


def export_markdown(chunks, meta_by_id, output_path, category=None):
    """导出为单个 Markdown 文件，按文档组织。"""
    # 按 doc_id 分组
    docs = {}
    for c in chunks:
        if category and c.get("category") != category:
            continue
        doc_id = c["doc_id"]
        if doc_id not in docs:
            docs[doc_id] = []
        docs[doc_id].append(c)

    lines = ["# 知识库参考资料\n"]
    lines.append(f"> 导出时间: {Path(CHUNKS_PATH).stat().st_mtime}\n")
    lines.append(f"> 文档数: {len(docs)} | 片段数: {sum(len(v) for v in docs.values())}\n")
    lines.append("---\n")

    for doc_id, doc_chunks in docs.items():
        meta = meta_by_id.get(doc_id, {})
        doc_name = meta.get("name", doc_chunks[0].get("doc_name", doc_id))
        doc_cat = meta.get("category", doc_chunks[0].get("category", ""))

        lines.append(f"## {doc_name}")
        lines.append(f"- 分类: {doc_cat} | 片段数: {len(doc_chunks)}\n")

        for c in doc_chunks:
            heading = c.get("heading_path", "")
            text = c.get("text", "").strip()
            if heading:
                lines.append(f"### {heading}\n")
            lines.append(text)
            lines.append("")

        lines.append("---\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def export_search(chunks, query, output_path):
    """简单关键词搜索后导出相关片段。"""
    keywords = query.split()
    scored = []
    for c in chunks:
        text = c.get("text", "")
        score = sum(text.count(kw) for kw in keywords)
        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:30]

    lines = [f"# 搜索结果: {query}\n"]
    lines.append(f"> 匹配片段: {len(top)}\n")
    lines.append("---\n")

    for score, c in top:
        lines.append(f"**文档:** {c.get('doc_name', '')}")
        lines.append(f"**相关度:** {score}")
        if c.get("heading_path"):
            lines.append(f"**章节:** {c['heading_path']}")
        lines.append("")
        lines.append(c.get("text", "").strip())
        lines.append("\n---\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def main():
    parser = argparse.ArgumentParser(description="导出知识库")
    parser.add_argument("--category", choices=["policy", "activity"], help="按分类筛选")
    parser.add_argument("--search", type=str, help="关键词搜索导出")
    parser.add_argument("--output", type=str, help="输出文件路径")
    args = parser.parse_args()

    chunks, meta_by_id = load_data()

    if args.search:
        name = f"knowledge_search_{args.search[:20]}.md"
        path = Path(args.output) if args.output else OUTPUT_DIR / name
        export_search(chunks, args.search, path)
        print(f"已导出搜索结果 → {path}")
    else:
        cat_suffix = f"_{args.category}" if args.category else "_all"
        path = Path(args.output) if args.output else OUTPUT_DIR / f"knowledge{cat_suffix}.md"
        export_markdown(chunks, meta_by_id, path, args.category)
        print(f"已导出知识库 → {path}")


if __name__ == "__main__":
    main()
