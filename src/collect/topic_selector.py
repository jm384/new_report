from __future__ import annotations


class TopicSelector:
    def __init__(self, context) -> None:
        self.context = context

    def select_topics(self) -> list[dict]:
        library = self.context.settings.topic_category_library
        rng = self.context.rng
        category_names = list(library.keys())
        rng.shuffle(category_names)
        selected: list[dict] = []
        manual_topics = set(self.context.settings.manual_topic_urls.keys())

        self.context.logger.info("COLLECT", "开始选择主题")
        for category in category_names:
            candidates = list(library[category])
            rng.shuffle(candidates)
            if not candidates:
                continue
            prioritized = []
            regular = []
            for candidate in candidates:
                expanded = self.context.settings.topic_expansion_patterns.get(candidate, candidate)
                if expanded in manual_topics:
                    prioritized.append(candidate)
                else:
                    regular.append(candidate)
            ordered_candidates = prioritized + regular
            base_topic = ordered_candidates[0]
            topic = self.context.settings.topic_expansion_patterns.get(base_topic, base_topic)
            selected.append(
                {
                    "category": category,
                    "base_topic": base_topic,
                    "topic": topic,
                }
            )
            self.context.logger.info(
                "COLLECT", f"已选主题：{topic}（类别：{category}）"
            )
            if len(selected) == 3:
                break

        if len(selected) < 3:
            self.context.action_manager.require_and_raise(
                phase="COLLECT",
                topic="主题选择",
                problem="主题库不足以选出 3 个来自不同大类的主题。",
                attempted_actions=["遍历主题分类库并尝试按类别去重选择主题"],
                cannot_continue_reason="主题选择不满足项目要求，无法继续进入采集阶段。",
                user_actions=["请在 config.py 中补充更多主题分类和主题。"],
                suggested_materials=["新的主题分类清单", "新增主题名称"],
                generated_files=self.context.created_files_as_strings,
            )

        final_topics = "、".join(item["topic"] for item in selected)
        self.context.logger.info("COLLECT", f"最终选中的 3 个主题：{final_topics}")
        return selected
