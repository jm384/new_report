from __future__ import annotations

import os
from pathlib import Path

from config import (
    AppSettings,
    CheckSettings,
    GenerationSettings,
    LLMSettings,
    LoggingSettings,
    SearchSettings,
)


def _load_dotenv(project_root: Path) -> None:
    env_path = project_root / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    load_dotenv(env_path)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def load_settings(project_root: Path) -> AppSettings:
    _load_dotenv(project_root)

    llm = LLMSettings(
        provider=os.getenv("LLM_PROVIDER", "openai"),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", ""),
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        enable_query_generation=_get_bool("LLM_ENABLE_QUERY_GENERATION", True),
        enable_source_filter=_get_bool("LLM_ENABLE_SOURCE_FILTER", True),
        enable_blog_generation=_get_bool("LLM_ENABLE_BLOG_GENERATION", True),
        enable_check_and_rewrite=_get_bool("LLM_ENABLE_CHECK_AND_REWRITE", True),
    )
    search = SearchSettings(
        mode=os.getenv("SEARCH_MODE", "no_api"),
        max_results_per_query=_get_int("SEARCH_MAX_RESULTS_PER_QUERY", 10),
        max_articles_per_topic=_get_int("SEARCH_MAX_ARTICLES_PER_TOPIC", 7),
        min_articles_per_topic=_get_int("SEARCH_MIN_ARTICLES_PER_TOPIC", 4),
        enable_ddgs_search=_get_bool("ENABLE_DDGS_SEARCH", True),
        enable_seed_source_search=_get_bool("ENABLE_SEED_SOURCE_SEARCH", True),
        enable_manual_urls=_get_bool("ENABLE_MANUAL_URLS", True),
        enforce_min_articles_per_topic=_get_bool(
            "ENFORCE_MIN_ARTICLES_PER_TOPIC", False
        ),
        template_bootstrap_remote_enabled=_get_bool(
            "TEMPLATE_BOOTSTRAP_REMOTE_ENABLED", True
        ),
        template_bootstrap_remote_max_results_per_query=_get_int(
            "TEMPLATE_BOOTSTRAP_REMOTE_MAX_RESULTS_PER_QUERY", 6
        ),
        template_bootstrap_skip_remote_if_viable=_get_bool(
            "TEMPLATE_BOOTSTRAP_SKIP_REMOTE_IF_VIABLE", True
        ),
    )
    generation = GenerationSettings(
        target_article_word_count=_get_int("TARGET_ARTICLE_WORD_COUNT", 3200),
        min_article_word_count=_get_int("MIN_ARTICLE_WORD_COUNT", 2800),
        max_article_word_count=_get_int("MAX_ARTICLE_WORD_COUNT", 3600),
        include_brand_message_probability=_get_float(
            "INCLUDE_BRAND_MESSAGE_PROBABILITY", 0.6
        ),
        include_phone_cta_probability=_get_float("INCLUDE_PHONE_CTA_PROBABILITY", 0.5),
        phone_cta_text=os.getenv("PHONE_CTA_TEXT", "致电212-899-8888，获取免费咨询！"),
        brand_message_title=os.getenv("BRAND_MESSAGE_TITLE", "古灵王律师团寄语"),
    )
    check = CheckSettings(
        max_template_overall_similarity=_get_float(
            "MAX_TEMPLATE_OVERALL_SIMILARITY", 0.30
        ),
        max_template_paragraph_similarity=_get_float(
            "MAX_TEMPLATE_PARAGRAPH_SIMILARITY", 0.60
        ),
        max_continuous_duplicate_chars=_get_int("MAX_CONTINUOUS_DUPLICATE_CHARS", 30),
        structure_style_pass_score=_get_int("STRUCTURE_STYLE_PASS_SCORE", 75),
        language_style_pass_score=_get_int("LANGUAGE_STYLE_PASS_SCORE", 75),
    )
    logging = LoggingSettings(
        level=os.getenv("LOG_LEVEL", "INFO"),
        print_detailed_logs=_get_bool("PRINT_DETAILED_LOGS", True),
        save_logs=_get_bool("SAVE_LOGS", True),
    )
    return AppSettings(
        project_root=project_root,
        llm=llm,
        search=search,
        generation=generation,
        check=check,
        logging=logging,
        template_min_count=_get_int("TEMPLATE_MIN_COUNT", 4),
        template_min_viable_count=_get_int("TEMPLATE_MIN_VIABLE_COUNT", 3),
        template_bootstrap_seed_target=_get_int("TEMPLATE_BOOTSTRAP_SEED_TARGET", 4),
    )
