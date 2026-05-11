import logging
import os
from typing import List

logger = logging.getLogger(__name__)

STYLE_PROMPTS = {
    "policy": (
        "你是一位政策文件撰写专家。请参考以下参考文档的表达方式、格式和知识，"
        "用正式、严谨的公文风格撰写。保持与参考文档一致的章节结构、用语规范和专业术语。"
    ),
    "report": (
        "你是一位教育成果报告撰写专家。请参考以下模板的结构和表达方式，"
        "用清晰、规范的风格撰写报告。保持与参考文档一致的标题层级、数据呈现方式和行文习惯。"
    ),
    "general": (
        "请参考以下文档的内容和表达方式，生成内容时保持相似的风格和术语。"
    ),
}


def generate_with_context(prompt: str, context_chunks: str,
                          style: str = "policy", api_key: str = None) -> tuple:
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    style_instruction = STYLE_PROMPTS.get(style, STYLE_PROMPTS["general"])

    system_prompt = f"""{style_instruction}

{context_chunks}

请确保：
1. 格式和结构与参考文档保持一致
2. 使用参考文档中的专业术语和表达方式
3. 在生成的文本末尾标注参考的文档名称和章节
"""

    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set, returning template response")
        return (
            f"[需要设置 ANTHROPIC_API_KEY 环境变量]\n\n"
            f"系统将基于以下 {context_chunks.count('[文档名') if context_chunks else 0} 篇参考文档生成内容：\n\n"
            f"{context_chunks}\n\n"
            f"任务：{prompt}",
            [],
        )

    try:
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

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        return (
            f"生成失败：{str(e)}\n\n"
            f"参考上下文：\n{context_chunks[:1000]}...",
            [],
        )


def _extract_sources(context: str) -> List[dict]:
    import re
    sources = []
    pattern = r"\[(\d+)\]\s+(.+?)\s+—\s+(.+?)\n内容：(.+?)(?:\n\n|\n(?=\[)|$)"
    for match in re.finditer(pattern, context, re.DOTALL):
        sources.append({
            "index": int(match.group(1)),
            "doc_name": match.group(2).strip(),
            "location": match.group(3).strip(),
            "content": match.group(4).strip()[:200],
        })
    return sources
