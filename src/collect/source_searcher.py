from __future__ import annotations

from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _extract_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    return domain.removeprefix("www.")


BLOCKED_RESULT_DOMAINS = {
    "youtube.com",
    "mietwagen-talk.de",
    "google.com",
    "news.google.com",
    "wikipedia.org",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
}


def _is_blocked_domain(domain: str) -> bool:
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in BLOCKED_RESULT_DOMAINS)


class SourceSearcher:
    def __init__(self, context) -> None:
        self.context = context

    def search(self, topic: str, grouped_queries: dict[str, list[str]]) -> list[dict]:
        results: list[dict] = []
        seen_urls: set[str] = set()

        if self.context.settings.search.enable_manual_urls:
            manual_urls = self.context.settings.manual_topic_urls.get(topic, [])
            if manual_urls:
                self.context.logger.info("COLLECT", f"主题“{topic}”使用手动 URL 补充 {len(manual_urls)} 条")
            for url in manual_urls:
                if url not in seen_urls:
                    seen_urls.add(url)
                    results.append(
                        {
                            "topic": topic,
                            "search_query": "MANUAL_URL",
                            "title": url,
                            "snippet": "手动补充来源",
                            "url": url,
                            "method": "manual_url",
                        }
                    )

        if self.context.settings.search.enable_ddgs_search:
            ddgs_results = self._search_with_ddgs(topic, grouped_queries)
            for item in ddgs_results:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    results.append(item)
                if len(results) >= self.context.settings.search.max_articles_per_topic * 3:
                    break

        if (
            self.context.settings.search.enable_seed_source_search
            and len(results) < self.context.settings.search.min_articles_per_topic
        ):
            seed_results = self._search_with_seed_sources(topic)
            for item in seed_results:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    results.append(item)
                if len(results) >= self.context.settings.search.max_articles_per_topic * 3:
                    break

        max_results = max(
            self.context.settings.search.max_articles_per_topic * 4,
            self.context.settings.search.max_results_per_query * 4,
        )
        results = results[:max_results]
        self.context.logger.info("COLLECT", f"主题“{topic}”找到候选链接 {len(results)} 条")
        return results

    def _search_with_ddgs(self, topic: str, grouped_queries: dict[str, list[str]]) -> list[dict]:
        flattened = []
        for category, queries in grouped_queries.items():
            for query in queries[:2]:
                flattened.append((category, query))
        flattened = flattened[:6]

        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            self.context.logger.warning(
                "COLLECT",
                "duckduckgo_search 未安装，跳过 DDGS 搜索。",
            )
            return []

        all_items: list[dict] = []
        ddgs = DDGS()
        for category, query in flattened:
            try:
                self.context.logger.info("COLLECT", f"正在搜索：{query}")
                results = ddgs.text(
                    query,
                    max_results=self.context.settings.search.max_results_per_query,
                )
                for item in results:
                    all_items.append(
                        {
                            "topic": topic,
                            "search_query": query,
                            "query_category": category,
                            "title": item.get("title", ""),
                            "snippet": item.get("body", ""),
                            "url": item.get("href", ""),
                            "method": "ddgs",
                        }
                    )
            except Exception as exc:
                self.context.logger.warning(
                    "COLLECT", f"DDGS 搜索失败：{query}，原因：{exc}"
                )
        return [item for item in all_items if item.get("url") and self._is_probably_article(item["url"])]

    def _search_with_seed_sources(self, topic: str) -> list[dict]:
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            return []
        ddgs = DDGS()
        results: list[dict] = []
        for seed in self.context.settings.seed_sources[:6]:
            domain = _extract_domain(seed)
            query = f"site:{domain} {topic}"
            try:
                self.context.logger.info("COLLECT", f"正在固定来源搜索：{query}")
                for item in ddgs.text(query, max_results=2):
                    url = item.get("href", "")
                    if not url or not self._is_probably_article(url):
                        continue
                    results.append(
                        {
                            "topic": topic,
                            "search_query": query,
                            "query_category": "seed_source",
                            "title": item.get("title", ""),
                            "snippet": item.get("body", ""),
                            "url": url,
                            "method": "seed_source_search",
                        }
                    )
            except Exception as exc:
                self.context.logger.warning("COLLECT", f"固定来源搜索失败：{query}，原因：{exc}")
        return results

    def _is_probably_article(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = _extract_domain(url)
        if _is_blocked_domain(domain):
            return False
        path = (parsed.path or "").strip("/")
        if not path:
            return False
        if path.count("/") == 0 and "." not in path and len(path) < 12:
            return False
        blocked = {"home", "index", "search", "tag", "tags", "category", "categories"}
        tail = path.split("/")[-1].lower()
        return tail not in blocked

    def check_network(self) -> bool:
        try:
            try:
                import requests  # type: ignore

                response = requests.get(
                    "https://www.ny.gov/",
                    headers={"User-Agent": self.context.settings.search.user_agent},
                    timeout=10,
                )
                return response.ok
            except Exception:
                request = Request(
                    "https://www.ny.gov/",
                    headers={"User-Agent": self.context.settings.search.user_agent},
                )
                with urlopen(request, timeout=10) as response:
                    return response.status < 400
        except Exception:
            return False
