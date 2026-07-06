from __future__ import annotations


class PromptBuilder:
    def build_blog_prompt(self, *, topic: str, style_profile: dict, sources: list[dict], target_words: int) -> str:
        source_summaries = []
        for index, source in enumerate(sources[:6], start=1):
            source_summaries.append(
                f"{index}. 标题：{source.get('title', '')}\n"
                f"   URL：{source.get('url', '')}\n"
                f"   摘要：{source.get('summary', '')}\n"
                f"   正文节选：{source.get('content', '')[:500]}"
            )
        source_text = "\n".join(source_summaries)
        common_terms = "、".join(style_profile.get("common_terms", [])[:12])
        return f"""
请根据以下资料写一篇中文法律科普博客文章。
主题：{topic}
目标字数：约 {target_words} 字

风格参考：
- 结构：{style_profile.get('structure_summary', '')}
- 语气：{style_profile.get('tone_summary', '')}
- 常见术语：{common_terms}

写作要求：
1. 面向中文读者，语气自然、亲切、专业、顺畅。
2. 直接按 docx 文章结构输出，不要使用 Markdown 语法。
3. 标题、导语、小标题、正文、结尾提醒要清晰分段。
4. 小标题建议 4 到 6 个，表达要具体，不要过于学术。
5. 不要频繁重复“纽约”或“华人”；默认读者已经知道场景，不必反复说明。
6. 少用生硬套话，多用清楚易懂的日常表达。
7. 不要夸大承诺，不要制造焦虑。
8. 可以适当使用加粗强调重点，但不要整篇都加粗。
9. 内容中如涉及序号，请用自然序号，不要用 Markdown 符号代替。
10. 避免“本文将”“首先”“其次”这类过度模板化表达。

参考资料：
{source_text}
""".strip()
