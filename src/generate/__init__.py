from __future__ import annotations

from pathlib import Path

from src.common.file_utils import ensure_dir, load_json, save_json
from src.generate.blog_generator import BlogGenerator
from src.generate.docx_writer import BlogDocxWriter


def run_generate_phase(context, llm_client) -> None:
    context.set_phase("GENERATE")
    context.logger.info("GENERATE", "开始执行 generate 阶段")
    ensure_dir(context.paths.generate)
    ensure_dir(context.paths.generated_blog_articles)
    ensure_dir(context.paths.generate / "data")

    input_dir = context.input_run_dir or context.paths.root
    collect_dir = input_dir / "collect" if (input_dir / "collect").exists() else input_dir
    collect_data_dir = collect_dir / "data"
    selected_topics = load_json(collect_data_dir / "selected_topics.json", default=[])
    extracted_articles = load_json(collect_data_dir / "filtered_sources.json", default={})
    template_profiles = load_json(collect_data_dir / "template_style_profiles.json", default={})
    if not selected_topics and input_dir != context.paths.root:
        fallback_dir = context.paths.root / "collect" / "data"
        selected_topics = load_json(fallback_dir / "selected_topics.json", default=[])
        extracted_articles = load_json(fallback_dir / "filtered_sources.json", default={})
        template_profiles = load_json(fallback_dir / "template_style_profiles.json", default={})

    if not selected_topics:
        context.action_manager.require_and_raise(
            phase="GENERATE",
            topic="生成阶段",
            problem="未找到 selected_topics.json，无法确定要生成哪些主题。",
            attempted_actions=["读取输入目录中的 collect/data/selected_topics.json"],
            cannot_continue_reason="缺少 collect 阶段产物，无法继续生成文章。",
            user_actions=["请先运行 python main.py --phase collect。"],
            suggested_materials=["collect 阶段输出目录"],
            generated_files=context.created_files_as_strings,
        )

    generator = BlogGenerator(context, llm_client)
    writer = BlogDocxWriter(context)
    generation_metadata = {"articles": []}

    for topic_info in selected_topics:
        topic = topic_info["topic"]
        context.set_topic(topic)
        profile = template_profiles.get(topic, {})
        articles = extracted_articles.get(topic, [])
        article_payload = generator.generate(topic=topic, style_profile=profile, sources=articles)
        output_path = writer.write(article_payload)
        context.record_file(output_path)
        article_payload["output_path"] = str(output_path)
        generation_metadata["articles"].append(article_payload)

    generation_data_dir = context.paths.generate / "data"
    generation_data_dir.mkdir(parents=True, exist_ok=True)
    save_json(generation_data_dir / "generation_metadata.json", generation_metadata)
    context.record_file(generation_data_dir / "generation_metadata.json")
    context.logger.info("GENERATE", "generate 阶段完成")
