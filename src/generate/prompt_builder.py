from __future__ import annotations


class PromptBuilder:
    def build_blog_prompt(self, *, topic: str, style_profile: dict, sources: list[dict], target_words: int) -> str:
        source_summaries = []
        for index, source in enumerate(sources[:8], start=1):
            source_summaries.append(
                f"{index}. 标题：{source.get('title', '')}\n"
                f"   链接：{source.get('url', '')}\n"
                f"   概要：{source.get('summary', '')}\n"
                f"   摘要片段：{source.get('content', '')[:700]}"
            )
        source_text = "\n".join(source_summaries) or "无可用来源"
        common_terms = "、".join(style_profile.get("common_terms", [])[:12])
        template_count = style_profile.get("template_count", 0)
        return f"""
请根据以下资料写一篇完整的中文法律科普博客文章。

主题：{topic}
目标字数：{target_words}
模板数量：{template_count}

写作要求：
1. 输出必须是一篇完整文章，不要包含“标题：”“导语：”这类说明标签。
2. 文章要自然分段，结构清晰，包含引言、主体小标题和结尾提醒。
3. 小标题建议 4 到 6 个，且内容要充实。
4. 不要频繁重复“纽约”“华人”等默认背景词。
5. 语言要通顺、克制、温和，不要生硬，不要过度营销。
6. 不要输出 Markdown 符号，不要用 `#`、`**`、`-` 来代替正文排版。
7. 如果涉及序号，请直接写自然序号内容，避免像笔记一样零散。
8. 如果信息不足，也要合理扩展背景解释，但不要编造具体事实。
9. 结尾要有温和提醒，便于读者下一步行动。

风格参考：
- 结构：{style_profile.get('structure_summary', '')}
- 语气：{style_profile.get('tone_summary', '')}
- 常见术语：{common_terms}

参考资料：
{source_text}
""".strip()
