from __future__ import annotations

from datetime import datetime
import re
from urllib.request import Request, urlopen
from urllib.parse import urlparse

from src.common.text_utils import normalize_whitespace


class ArticleScraper:
    def __init__(self, context) -> None:
        self.context = context

    def scrape_candidates(self, topic: str, candidates: list[dict]) -> list[dict]:
        articles: list[dict] = []
        for candidate in candidates:
            url = candidate["url"]
            self.context.logger.info("COLLECT", f"正在抓取链接：{url}")
            article = {
                **candidate,
                "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_site": urlparse(url).netloc,
                "status": "failed",
                "error": "",
                "published_at": "",
                "content": "",
                "summary": candidate.get("snippet", ""),
            }
            try:
                html = self._fetch_html(url)
                text = self._extract_text(html, url)
                article["status"] = "ok"
                article["content"] = text
                article["title"] = article.get("title") or self._extract_title(html)
                article["summary"] = article.get("snippet") or text[:180]
                article["published_at"] = self._extract_published_at(html)
                self.context.logger.info(
                    "COLLECT",
                    f"抓取成功：{url}，正文长度 {len(text)}",
                )
            except Exception as exc:
                article["error"] = str(exc)
                self.context.logger.warning(
                    "COLLECT",
                    f"抓取失败：{url}，原因：{exc}",
                )
            articles.append(article)
        return articles

    def _fetch_html(self, url: str) -> str:
        try:
            import requests  # type: ignore

            response = requests.get(
                url,
                headers={"User-Agent": self.context.settings.search.user_agent},
                timeout=self.context.settings.search.request_timeout_seconds,
            )
            response.raise_for_status()
            response.encoding = response.encoding or response.apparent_encoding or "utf-8"
            return response.text
        except Exception:
            request = Request(
                url,
                headers={"User-Agent": self.context.settings.search.user_agent},
            )
            with urlopen(
                request, timeout=self.context.settings.search.request_timeout_seconds
            ) as response:
                return response.read().decode("utf-8", errors="ignore")

    def _extract_text(self, html: str, url: str) -> str:
        try:
            import trafilatura  # type: ignore

            extracted = trafilatura.extract(html, url=url, include_comments=False)
            if extracted:
                return normalize_whitespace(extracted)
        except Exception:
            pass

        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            text = "\n".join(
                chunk.strip() for chunk in soup.stripped_strings if len(chunk.strip()) >= 20
            )
            return normalize_whitespace(text)
        except Exception:
            html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
            text = re.sub(r"(?s)<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text)
            return normalize_whitespace(text)

    def _extract_title(self, html: str) -> str:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "lxml")
            if soup.title and soup.title.text:
                return soup.title.text.strip()
        except Exception:
            pass
        matched = re.search(r"(?is)<title>(.*?)</title>", html)
        if matched:
            return normalize_whitespace(matched.group(1))
        return "未提取到标题"

    def _extract_published_at(self, html: str) -> str:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "lxml")
            for attr in ["article:published_time", "pubdate", "publish-date", "date"]:
                node = soup.find(attrs={"property": attr}) or soup.find(attrs={"name": attr})
                if node and node.get("content"):
                    return node["content"]
            time_node = soup.find("time")
            if time_node:
                return time_node.get("datetime", "") or time_node.get_text(strip=True)
        except Exception:
            pass
        for attr in ["article:published_time", "pubdate", "publish-date", "date"]:
            matched = re.search(
                rf'(?is)(?:property|name)=["\']{re.escape(attr)}["\'][^>]*content=["\'](.*?)["\']',
                html,
            )
            if matched:
                return normalize_whitespace(matched.group(1))
        return ""
