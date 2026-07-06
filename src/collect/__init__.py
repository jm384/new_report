from __future__ import annotations

from src.collect.article_scraper import ArticleScraper
from src.collect.query_generator import QueryGenerator
from src.collect.research_doc_builder import ResearchDocBuilder
from src.collect.source_filter import SourceFilter
from src.collect.source_searcher import SourceSearcher
from src.collect.template_collector import TemplateCollector
from src.collect.template_style_analyzer import TemplateStyleAnalyzer
from src.collect.topic_selector import TopicSelector
from src.common.docx_utils import DocxDependencyError
from src.common.file_utils import save_json


def _flush_collect_data(context, *, queries, raw_results, filtered, extracted, styles) -> None:
    payloads = {
        "generated_queries.json": queries,
        "raw_search_results.json": raw_results,
        "filtered_sources.json": filtered,
        "extracted_articles.json": extracted,
        "template_style_profiles.json": styles,
    }
    for file_name, payload in payloads.items():
        path = context.paths.data / file_name
        save_json(path, payload)
        if path not in context.created_files:
            context.record_file(path)


def run_collect_phase(context, llm_client) -> None:
    context.set_phase("COLLECT")
    logger = context.logger
    logger.info("COLLECT", "开始执行 collect 阶段")
    context.paths.collect.mkdir(parents=True, exist_ok=True)
    context.paths.data.mkdir(parents=True, exist_ok=True)
    context.paths.topic_research_docs.mkdir(parents=True, exist_ok=True)

    selector = TopicSelector(context)
    topics = selector.select_topics()
    save_json(context.paths.data / "selected_topics.json", topics)
    context.record_file(context.paths.data / "selected_topics.json")

    query_generator = QueryGenerator(context, llm_client)
    searcher = SourceSearcher(context)
    scraper = ArticleScraper(context)
    source_filter = SourceFilter(context, llm_client)
    research_builder = ResearchDocBuilder(context)
    template_collector = TemplateCollector(context, llm_client)
    style_analyzer = TemplateStyleAnalyzer(context, llm_client)

    all_queries: dict[str, dict] = {}
    all_raw_results: dict[str, list[dict]] = {}
    all_filtered: dict[str, list[dict]] = {}
    all_extracted: dict[str, list[dict]] = {}
    all_styles: dict[str, dict] = {}
    network_available = searcher.check_network()
    context.logger.info(
        "COLLECT",
        f"当前网络状态：{'可访问公开网站' if network_available else '当前环境无法正常访问外网'}",
    )

    for topic_info in topics:
        topic = topic_info["topic"]
        category = topic_info.get("category", "")
        context.set_topic(topic)
        context.set_topic_category(category)
        logger.info("COLLECT", f"开始处理主题：{topic}")

        query_result = query_generator.generate(topic)
        all_queries[topic] = query_result
        _flush_collect_data(
            context,
            queries=all_queries,
            raw_results=all_raw_results,
            filtered=all_filtered,
            extracted=all_extracted,
            styles=all_styles,
        )

        raw_results = searcher.search(topic, query_result["queries"])
        all_raw_results[topic] = raw_results
        _flush_collect_data(
            context,
            queries=all_queries,
            raw_results=all_raw_results,
            filtered=all_filtered,
            extracted=all_extracted,
            styles=all_styles,
        )

        extracted_articles = scraper.scrape_candidates(topic, raw_results)
        all_extracted[topic] = extracted_articles
        filtered_articles = source_filter.filter_articles(
            topic=topic,
            query_result=query_result,
            articles=extracted_articles,
        )
        all_filtered[topic] = filtered_articles
        _flush_collect_data(
            context,
            queries=all_queries,
            raw_results=all_raw_results,
            filtered=all_filtered,
            extracted=all_extracted,
            styles=all_styles,
        )

        if len(filtered_articles) < context.settings.search.min_articles_per_topic:
            logger.warning(
                "COLLECT",
                f"主题“{topic}”过滤后的有效资料仅有 {len(filtered_articles)} 篇，已继续采集并记录质量信息，不作为终止条件。",
            )

        try:
            research_path = research_builder.build(topic, query_result, filtered_articles)
            context.record_file(research_path)
        except DocxDependencyError as exc:
            context.action_manager.require_and_raise(
                phase="COLLECT",
                topic=topic,
                problem=str(exc),
                attempted_actions=["尝试使用 python-docx 生成主题采集文档。"],
                cannot_continue_reason="缺少 docx 写入能力，无法输出必须的采集文档。",
                user_actions=["请执行 pip install -r requirements.txt 安装依赖。"],
                suggested_materials=["requirements.txt", "pip 安装日志"],
                generated_files=context.created_files_as_strings,
            )

        template_payload = template_collector.collect_for_topic(topic)
        style_profile = style_analyzer.analyze(
            topic=topic,
            template_payload=template_payload,
        )
        all_styles[topic] = style_profile
        _flush_collect_data(
            context,
            queries=all_queries,
            raw_results=all_raw_results,
            filtered=all_filtered,
            extracted=all_extracted,
            styles=all_styles,
        )

    _flush_collect_data(
        context,
        queries=all_queries,
        raw_results=all_raw_results,
        filtered=all_filtered,
        extracted=all_extracted,
        styles=all_styles,
    )

    logger.info("COLLECT", "collect 阶段完成")
