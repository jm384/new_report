from __future__ import annotations


class PromptBuilder:
    def build_blog_prompt(
        self,
        *,
        topic: str,
        style_profile: dict,
        sources: list[dict],
        target_words: int,
    ) -> str:
        source_summaries = []
        for index, source in enumerate(sources[:8], start=1):
            source_summaries.append(
                f"{index}. 标题：{source.get('title', '')}\n"
                f"   链接：{source.get('url', '')}\n"
                f"   中文概要：{source.get('summary_zh', '') or source.get('summary', '')}\n"
                f"   正文片段：{source.get('content', '')[:900]}"
            )
        source_text = "\n".join(source_summaries) or "无可用来源。"
        common_terms = "、".join(style_profile.get("common_terms", [])[:12])
        template_count = style_profile.get("template_count", 0)
        return f"""
请根据以下资料写一篇完整、可发布的中文法律科普博客文章。

主题：{topic}
目标字数：{target_words}
模板数量：{template_count}

写作要求：
1. 第一行必须是真正的文章标题，不要写“标题：”“导语：”等说明标签。
2. 不要出现“我先按你的要求重写”“下面按几个部分来写”这类说明性废话。
3. 文章要自然分段，结构清楚，包含引入、多个小标题和结尾提醒。
4. 小标题建议 4 到 6 个，内容要展开充分，不能只写提纲。
5. 语言要通顺、自然、克制，不要生硬，不要像命令说明稿。
6. 不要频繁重复“纽约”“华人”等默认背景词。
7. 不要输出 Markdown，不要用 `#`、`**`、`-` 代替正文排版。
8. 涉及责任、保险、法律规则时要保守准确，不要绝对化承诺。
9. “温和提醒”“古灵王律师团寄语”如果要出现，只能放在文章结尾的小节里，不能作为文章标题。
10. 如果现有信息有限，可以补足背景解释，但不要编造具体案件事实。

风格参考：
- 结构：{style_profile.get('structure_summary', '')}
- 语气：{style_profile.get('tone_summary', '')}
- 常见术语：{common_terms}

参考资料：
{source_text}
""".strip()
