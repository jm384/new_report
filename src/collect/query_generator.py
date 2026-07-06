from __future__ import annotations

import json


BASE_QUERY_PATTERNS = [
    "{topic} New York",
    "{topic} NYC",
    "{topic} New York law",
    "{topic} New York safety",
    "{topic} ny.gov",
    "{topic} nyc.gov",
    "{topic} injury claim New York",
]


class QueryGenerator:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def generate(self, topic: str) -> dict:
        use_llm = (
            self.context.settings.llm.enable_query_generation
            and self.llm_client.is_configured
        )
        self.context.logger.info(
            "COLLECT",
            f"主题“{topic}”是否使用 LLM 生成搜索词：{'是' if use_llm else '否'}",
        )
        if use_llm:
            try:
                return self._generate_with_llm(topic)
            except Exception as exc:
                self.context.logger.warning(
                    "COLLECT",
                    f"LLM 搜索词生成失败，改用规则模式：{exc}",
                )

        self.context.logger.info("COLLECT", "当前未启用 LLM，使用规则方式处理搜索词生成")
        return self._generate_with_rules(topic)

    def _generate_with_llm(self, topic: str) -> dict:
        prompt = f"""
请围绕主题“{topic}”生成搜索词，输出 JSON。
JSON 字段要求：
{{
  "queries": {{
    "zh": [],
    "en": [],
    "new_york_state": [],
    "new_york_city": [],
    "official_sites": [],
    "news": [],
    "legal_education": [],
    "insurance_or_liability": [],
    "safety": []
  }}
}}
每个数组给 1-3 条搜索词，不要解释。
""".strip()
        payload = self.llm_client.generate_json(
            phase="COLLECT",
            purpose="搜索词生成",
            prompt=prompt,
            system_prompt="你是纽约州法律科普资料研究助手，只输出合法 JSON。",
        )
        queries = payload["queries"]
        flattened = []
        for values in queries.values():
            flattened.extend(values)
        self.context.logger.info("COLLECT", f"生成搜索词 {len(flattened)} 条")
        return {"mode": "llm", "queries": queries, "flattened": flattened}

    def _generate_with_rules(self, topic: str) -> dict:
        queries = {
            "zh": [topic, f"纽约 {topic}", f"{topic} 法律科普"],
            "en": [f"{topic} New York", f"{topic} NYC"],
            "new_york_state": [f"{topic} New York State", f"{topic} ny.gov"],
            "new_york_city": [f"{topic} New York City", f"{topic} nyc.gov"],
            "official_sites": [f"site:ny.gov {topic}", f"site:nyc.gov {topic}"],
            "news": [f"{topic} New York news", f"{topic} NYC news"],
            "legal_education": [f"{topic} New York law", f"{topic} injury claim New York"],
            "insurance_or_liability": [f"{topic} insurance liability New York"],
            "safety": [f"{topic} New York safety", f"{topic} public safety NYC"],
        }
        for pattern in BASE_QUERY_PATTERNS:
            queries["en"].append(pattern.format(topic=topic))
        flattened = []
        for values in queries.values():
            flattened.extend(values)
        flattened = list(dict.fromkeys(flattened))
        self.context.logger.info("COLLECT", f"生成搜索词 {len(flattened)} 条")
        return {"mode": "rules", "queries": queries, "flattened": flattened}
