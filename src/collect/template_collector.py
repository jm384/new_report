from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.common.docx_utils import read_docx_text
from src.common.file_utils import sanitize_filename
from src.common.llm_client import LLMQuotaExceededError
from src.common.text_utils import top_terms


class TemplateCollector:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client
        self.last_bootstrap_hit_quota = False

    def collect_for_topic(self, topic: str) -> dict:
        template_root = self.context.project_root / "template_docs"
        category_dir = self._get_category_dir(template_root)
        self._migrate_legacy_templates(template_root, category_dir)
        files = self._find_template_files(category_dir)
        self.context.logger.info("COLLECT", f"当前主题模板候选数量：{len(files)}")

        if len(files) < self.context.settings.template_min_count:
            self.context.logger.info("COLLECT", "本地模板不足，开始自举补充模板")
            self._bootstrap_templates(category_dir, topic)
            files = self._find_template_files(category_dir)
            self.context.logger.info("COLLECT", f"自举后模板数量：{len(files)}")

        viable_count = self.context.settings.template_min_viable_count
        target_count = self.context.settings.template_min_count
        if len(files) == viable_count:
            self.context.logger.info("COLLECT", "模板数量达到最低可行值 3 篇，本轮继续后续分析")
        elif len(files) < viable_count:
            self.context.logger.warning(
                "COLLECT",
                f"模板不足最低可行值 {viable_count} 篇，后续风格分析质量可能受影响",
            )
        elif len(files) < target_count:
            self.context.logger.warning(
                "COLLECT",
                f"模板数量为 {len(files)} 篇，低于理想目标 {target_count} 篇，但不影响本轮继续",
            )

        payload = {
            "topic": topic,
            "topic_category": self.context.current_topic_category,
            "template_category_dir": str(category_dir),
            "templates": [],
            "template_count": len(files),
            "hit_quota_limit": self.last_bootstrap_hit_quota,
        }
        for path in files:
            text = self._read_template(path)
            payload["templates"].append(
                {
                    "path": str(path),
                    "name": path.name,
                    "text": text,
                    "top_terms": top_terms(text, limit=10),
                }
            )
        self.context.logger.info("COLLECT", f"模板文件已收集完成：{len(files)} 篇")
        return payload

    def _bootstrap_templates(self, template_root: Path, topic: str) -> None:
        self.last_bootstrap_hit_quota = False
        self._generate_seed_templates(
            template_root,
            topic,
            missing=max(
                0,
                self.context.settings.template_bootstrap_seed_target
                - len(self._find_template_files(template_root)),
            ),
        )
        current_files = self._find_template_files(template_root)
        if len(current_files) >= self.context.settings.template_min_count:
            return
        if (
            len(current_files) >= self.context.settings.template_min_viable_count
            and self.context.settings.search.template_bootstrap_skip_remote_if_viable
        ):
            self.context.logger.info("COLLECT", "模板已达到最低可行值，跳过远程模板采集以节省配额")
            return
        if self.context.settings.search.template_bootstrap_remote_enabled:
            self._collect_remote_templates(template_root, topic)
        current_files = self._find_template_files(template_root)
        if len(current_files) >= self.context.settings.template_min_viable_count:
            return
        self._generate_seed_templates(
            template_root,
            topic,
            missing=max(0, self.context.settings.template_min_viable_count - len(current_files)),
        )

    def _collect_remote_templates(self, template_root: Path, topic: str) -> None:
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError:
            self.context.logger.warning("COLLECT", "duckduckgo_search 未安装，跳过远程模板采集")
            return

        queries = [
            f"{topic} 中文 律师 博客 文章",
            "纽约 华人 律师 中文 博客 车祸 理赔",
            "纽约 华人 律师 中文 博客 滑倒 受伤",
            "纽约 华人 律师 中文 博客 房东 责任",
            "纽约 华人 律师 中文 博客 工地 事故",
        ]
        ddgs = DDGS()
        seen_urls: set[str] = set()
        max_results = self.context.settings.search.template_bootstrap_remote_max_results_per_query
        for query in queries:
            try:
                self.context.logger.info("COLLECT", f"正在搜索模板来源：{query}")
                for item in ddgs.text(query, max_results=max_results):
                    url = item.get("href", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    if len(self._find_template_files(template_root)) >= self.context.settings.template_min_viable_count:
                        return
                    text = self._fetch_article_text(url)
                    if not self._looks_like_template(text):
                        continue
                    title = item.get("title", "") or urlparse(url).netloc
                    file_name = sanitize_filename(f"{title}_远程模板") + ".md"
                    path = template_root / file_name
                    path.write_text(f"# {title}\n\n来源：{url}\n\n{text}", encoding="utf-8")
                    self.context.logger.info("COLLECT", f"已采集远程模板：{path.name}")
            except Exception as exc:
                self.context.logger.warning("COLLECT", f"模板搜索失败：{query}，原因：{exc}")

    def _generate_seed_templates(self, template_root: Path, topic: str, missing: int) -> None:
        if missing <= 0:
            return
        if not self.llm_client.is_configured:
            self.context.logger.warning("COLLECT", "LLM 不可用，无法生成种子模板")
            return

        seed_topics = [
            topic,
            "纽约州车祸后保险理赔怎么处理",
            "纽约冬季滑倒受伤后要注意什么",
            "纽约公寓楼公共区域受伤责任怎么判断",
            "纽约工地附近行人受伤后如何保留证据",
            "纽约医院误诊后先做什么",
        ]
        existing = len(self._find_template_files(template_root))
        created = 0
        for index, seed_topic in enumerate(seed_topics, start=1):
            if len(self._find_template_files(template_root)) >= self.context.settings.template_min_count:
                return
            if created >= missing:
                return
            file_name = sanitize_filename(f"seed_template_{existing + index}_{seed_topic}") + ".md"
            path = template_root / file_name
            if path.exists():
                continue
            prompt = f"""
请写一篇中文法律科普博客模板文章，用于中文律师事务所博客风格分析。
主题：{seed_topic}

要求：
1. 使用自然、完整、可发布的文章结构。
2. 包含标题、导语、4 到 5 个小标题、结尾提醒。
3. 语言要顺畅、温和、专业，不要夸大承诺。
4. 字数控制在 900 到 1400 字。
5. 只输出文章正文，不要解释。
""".strip()
            try:
                content = self.llm_client.generate_text(
                    phase="COLLECT",
                    purpose="种子模板生成",
                    prompt=prompt,
                    system_prompt="你是中文法律科普博客模板写作助手。",
                    temperature=0.7,
                )
                path.write_text(content, encoding="utf-8")
                self.context.logger.info("COLLECT", f"已生成种子模板：{path.name}")
                created += 1
            except LLMQuotaExceededError as exc:
                self.last_bootstrap_hit_quota = True
                self.context.logger.warning(
                    "COLLECT",
                    f"生成种子模板时遇到配额不足，停止继续补模板：{exc}",
                )
                return
            except Exception as exc:
                self.context.logger.warning("COLLECT", f"生成种子模板失败：{seed_topic}，原因：{exc}")
                break

    def _fetch_article_text(self, url: str) -> str:
        request = Request(
            url,
            headers={"User-Agent": self.context.settings.search.user_agent},
        )
        with urlopen(request, timeout=self.context.settings.search.request_timeout_seconds) as response:
            html = response.read().decode("utf-8", errors="ignore")
        try:
            import trafilatura  # type: ignore

            extracted = trafilatura.extract(html, url=url, include_comments=False)
            if extracted:
                return extracted.strip()
        except Exception:
            pass
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _looks_like_template(self, text: str) -> bool:
        if not text:
            return False
        chinese_char_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        if chinese_char_count < 350:
            return False
        keywords = ["纽约", "律师", "责任", "保险", "受伤", "事故", "索赔", "科普"]
        return sum(1 for keyword in keywords if keyword in text) >= 3

    def _get_category_dir(self, template_root: Path) -> Path:
        category_name = sanitize_filename(self.context.current_topic_category or "未分类")
        category_dir = template_root / category_name
        category_dir.mkdir(parents=True, exist_ok=True)
        return category_dir

    def _migrate_legacy_templates(self, template_root: Path, category_dir: Path) -> None:
        for ext in ("*.docx", "*.txt", "*.md"):
            for path in template_root.glob(ext):
                target = category_dir / path.name
                if target.exists():
                    continue
                path.replace(target)
                self.context.logger.info("COLLECT", f"已将历史模板迁移到分类目录：{target}")

    def _find_template_files(self, template_root: Path) -> list[Path]:
        files: list[Path] = []
        for ext in ("*.docx", "*.txt", "*.md"):
            files.extend(template_root.rglob(ext))
        return [path for path in sorted(files) if self._is_viable_template(path)]

    def _is_viable_template(self, path: Path) -> bool:
        try:
            text = self._read_template(path)
        except Exception as exc:
            self.context.logger.warning("COLLECT", f"读取模板失败，已忽略：{path.name}，原因：{exc}")
            return False
        chinese_char_count = len(re.findall(r"[\u4e00-\u9fff]", text))
        return bool(text.strip()) and chinese_char_count >= 250

    def _read_template(self, path: Path) -> str:
        if path.suffix.lower() == ".docx":
            return read_docx_text(path)
        return path.read_text(encoding="utf-8")
