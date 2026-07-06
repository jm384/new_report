from __future__ import annotations

import re
from html import unescape
from urllib.parse import parse_qs, quote, unquote, urlparse, urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


def _extract_domain(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    return domain.removeprefix("www.")


BLOCKED_RESULT_DOMAINS = {
    "youtube.com",
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

        manual_urls = (
            self.context.settings.manual_topic_urls.get(topic, [])
            if self.context.settings.search.enable_manual_urls
            else []
        )
        if manual_urls:
            self.context.logger.info(
                "COLLECT",
                f"主题“{topic}”使用手动 URL 补充 {len(manual_urls)} 条",
            )
        for url in manual_urls:
            if url in seen_urls:
                continue
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

        search_results: list[dict] = []
        if self.context.settings.search.enable_ddgs_search:
            search_results.extend(
                self._search_with_duckduckgo_html(topic, grouped_queries, seen_urls)
            )
        if not search_results:
            self.context.logger.warning(
                "COLLECT",
                f"主题“{topic}”未从 DuckDuckGo 获取到可用结果，继续尝试 Yahoo 搜索",
            )
            search_results.extend(self._search_with_yahoo_html(topic, grouped_queries, seen_urls))
        results.extend(search_results)

        if not search_results and self.context.settings.search.enable_seed_source_search:
            self.context.logger.warning("COLLECT", "公开搜索未拿到可用结果，继续尝试固定来源搜索兜底")
            results.extend(self._search_with_seed_sources(topic))

        if not results:
            results.extend(self._fallback_sources(topic))

        max_results = max(
            self.context.settings.search.max_articles_per_topic * 4,
            self.context.settings.search.max_results_per_query * 4,
        )
        results = results[:max_results]
        self.context.logger.info("COLLECT", f"主题“{topic}”找到候选链接 {len(results)} 条")
        return results

    def _iter_queries(self, grouped_queries: dict[str, list[str]]) -> list[tuple[str, str]]:
        flattened: list[tuple[str, str]] = []
        for category, queries in grouped_queries.items():
            for query in queries[:2]:
                flattened.append((category, query))
        return flattened[:6]

    def _search_with_duckduckgo_html(
        self, topic: str, grouped_queries: dict[str, list[str]], seen_urls: set[str]
    ) -> list[dict]:
        results: list[dict] = []
        consecutive_timeouts = 0
        for category, query in self._iter_queries(grouped_queries):
            try:
                self.context.logger.info("COLLECT", f"正在搜索：{query}")
                html = self._fetch_duckduckgo_html(query)
                consecutive_timeouts = 0
                if self._looks_like_duckduckgo_challenge(html):
                    self.context.logger.warning(
                        "COLLECT",
                        f"DuckDuckGo 返回了反爬挑战页，跳过该查询：{query}",
                    )
                    continue
                items = self._parse_duckduckgo_results(html)
                for item in items:
                    url = item.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    if not self._is_probably_article(url):
                        continue
                    seen_urls.add(url)
                    results.append(
                        {
                            "topic": topic,
                            "search_query": query,
                            "query_category": category,
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "method": "duckduckgo_html",
                        }
                    )
            except Exception as exc:
                self.context.logger.warning("COLLECT", f"搜索失败：{query}，原因：{exc}")
                if self._is_timeout_error(exc):
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= 2:
                        self.context.logger.warning("COLLECT", "DuckDuckGo 连续超时，提前结束本轮公开搜索")
                        break
        return results

    def _search_with_yahoo_html(
        self, topic: str, grouped_queries: dict[str, list[str]], seen_urls: set[str]
    ) -> list[dict]:
        results: list[dict] = []
        consecutive_timeouts = 0
        for category, query in self._iter_queries(grouped_queries):
            try:
                self.context.logger.info("COLLECT", f"正在使用 Yahoo 搜索：{query}")
                html = self._fetch_yahoo_html(query)
                consecutive_timeouts = 0
                items = self._parse_yahoo_results(html)
                for item in items:
                    url = item.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    if not self._is_probably_article(url):
                        continue
                    seen_urls.add(url)
                    results.append(
                        {
                            "topic": topic,
                            "search_query": query,
                            "query_category": category,
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "method": "yahoo_html",
                        }
                    )
            except Exception as exc:
                self.context.logger.warning("COLLECT", f"Yahoo 搜索失败：{query}，原因：{exc}")
                if self._is_timeout_error(exc):
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= 2:
                        self.context.logger.warning("COLLECT", "Yahoo 连续超时，提前结束本轮公开搜索")
                        break
        return results

    def _fetch_duckduckgo_html(self, query: str) -> str:
        url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
        request = Request(url, headers={"User-Agent": self.context.settings.search.user_agent})
        with urlopen(request, timeout=self.context.settings.search.request_timeout_seconds) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _fetch_yahoo_html(self, query: str) -> str:
        url = f"https://search.yahoo.com/search?p={quote(query)}"
        request = Request(url, headers={"User-Agent": self.context.settings.search.user_agent})
        with urlopen(request, timeout=self.context.settings.search.request_timeout_seconds) as response:
            return response.read().decode("utf-8", errors="ignore")

    def _parse_duckduckgo_results(self, html: str) -> list[dict]:
        items: list[dict] = []
        result_blocks = re.findall(r'<div class="result results_links.*?</div>\s*</div>', html, re.S)
        if not result_blocks:
            result_blocks = re.findall(r'<div class="result.*?</div>\s*</div>', html, re.S)
        for block in result_blocks:
            url_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', block)
            title_match = re.search(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', block, re.S)
            snippet_match = re.search(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
            if not url_match:
                continue
            url = unescape(url_match.group(1))
            if url.startswith("/l/?"):
                parsed = urlparse(url)
                target_url = parse_qs(parsed.query).get("uddg", [""])[0]
                if target_url:
                    url = unquote(unescape(target_url))
            title = re.sub(r"<.*?>", "", unescape(title_match.group(1))).strip() if title_match else ""
            snippet = re.sub(r"<.*?>", "", unescape(snippet_match.group(1))).strip() if snippet_match else ""
            items.append({"url": urljoin("https://html.duckduckgo.com", url), "title": title, "snippet": snippet})
        return items

    def _parse_yahoo_results(self, html: str) -> list[dict]:
        items: list[dict] = []
        soup = BeautifulSoup(html, "lxml")
        for block in soup.select("div#web ol.searchCenterMiddle li div.algo"):
            anchor = block.select_one("div.compTitle a")
            snippet_node = block.select_one("div.compText p") or block.select_one("div.compText")
            if not anchor:
                continue
            url = self._extract_yahoo_target_url(anchor.get("href", ""))
            if not url:
                continue
            title = anchor.get_text(" ", strip=True)
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            items.append({"url": url, "title": title, "snippet": snippet})
        return items

    def _extract_yahoo_target_url(self, href: str) -> str:
        if not href:
            return ""
        match = re.search(r"/RU=([^/]+)/", href)
        if match:
            return unquote(match.group(1))
        return href

    def _looks_like_duckduckgo_challenge(self, html: str) -> bool:
        lowered = html.lower()
        return "anomaly.js" in lowered or "select all squares containing a duck" in lowered

    def _search_with_seed_sources(self, topic: str) -> list[dict]:
        results: list[dict] = []
        seen_domains: set[str] = set()
        consecutive_timeouts = 0
        for seed in self.context.settings.seed_sources:
            domain = _extract_domain(seed)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            query = f"site:{domain} {topic}"
            try:
                self.context.logger.info("COLLECT", f"正在固定来源搜索：{query}")
                for item in self._search_seed_query(query):
                    url = item.get("url", "")
                    if not url or not self._is_probably_article(url):
                        continue
                    results.append(
                        {
                            "topic": topic,
                            "search_query": query,
                            "query_category": "seed_source",
                            "title": item.get("title", ""),
                            "snippet": item.get("snippet", ""),
                            "url": url,
                            "method": "seed_source_search",
                        }
                    )
                consecutive_timeouts = 0
            except Exception as exc:
                self.context.logger.warning("COLLECT", f"固定来源搜索失败：{query}，原因：{exc}")
                if self._is_timeout_error(exc):
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= 2:
                        self.context.logger.warning("COLLECT", "固定来源搜索连续超时，结束本轮兜底搜索")
                        break
            if len(seen_domains) >= 4:
                break
        return results

    def _search_seed_query(self, query: str) -> list[dict]:
        try:
            html = self._fetch_duckduckgo_html(query)
            if not self._looks_like_duckduckgo_challenge(html):
                items = self._parse_duckduckgo_results(html)
                if items:
                    return items
        except Exception:
            pass
        html = self._fetch_yahoo_html(query)
        return self._parse_yahoo_results(html)

    def _fallback_sources(self, topic: str) -> list[dict]:
        results: list[dict] = []
        for url in self.context.settings.manual_topic_urls.get(topic, []):
            if url:
                results.append(
                    {
                        "topic": topic,
                        "search_query": "FALLBACK_MANUAL_URL",
                        "query_category": "fallback",
                        "title": url,
                        "snippet": "兜底来源",
                        "url": url,
                        "method": "fallback_manual_url",
                    }
                )
        return results

    def _is_probably_article(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = _extract_domain(url)
        if _is_blocked_domain(domain):
            return False
        path = (parsed.path or "").strip("/")
        if not path:
            return False
        if path.count("/") == 0 and "." not in path and len(path) < 6:
            return False
        blocked = {"home", "index", "search", "tag", "tags", "category", "categories"}
        tail = path.split("/")[-1].lower()
        return tail not in blocked

    def check_network(self) -> bool:
        try:
            request = Request(
                "https://html.duckduckgo.com/html/?q=test",
                headers={"User-Agent": self.context.settings.search.user_agent},
            )
            with urlopen(request, timeout=10) as response:
                return response.status < 400
        except Exception:
            return False

    def _is_timeout_error(self, exc: Exception) -> bool:
        return "timed out" in str(exc).lower()
