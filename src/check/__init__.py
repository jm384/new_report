from __future__ import annotations

import shutil

from src.check.auto_rewriter import AutoRewriter
from src.check.compliance_checker import ComplianceChecker
from src.check.language_style_checker import LanguageStyleChecker
from src.check.report_builder import ReportBuilder
from src.check.structure_checker import StructureChecker
from src.common.file_utils import ensure_dir, load_json
from src.generate.docx_writer import BlogDocxWriter


def run_check_phase(context, llm_client) -> None:
    context.set_phase("CHECK")
    context.logger.info("CHECK", "开始执行 check 阶段")
    ensure_dir(context.paths.check)
    if context.paths.final_articles.exists():
        shutil.rmtree(context.paths.final_articles)
    ensure_dir(context.paths.final_articles)
    ensure_dir(context.paths.check / "data")
    for suffix in (".docx", ".md", ".json"):
        report_file = context.paths.check / f"quality_check_report{suffix}"
        if report_file.exists():
            report_file.unlink()

    input_dir = context.input_run_dir or context.paths.root
    if (input_dir / "2_generate").exists():
        generation_dir = input_dir / "2_generate"
    elif (input_dir / "3_generate").exists():
        generation_dir = input_dir / "3_generate"
    elif (input_dir / "generate").exists():
        generation_dir = input_dir / "generate"
    else:
        generation_dir = input_dir

    if (input_dir / "1_collect").exists():
        collect_dir = input_dir / "1_collect"
    elif (input_dir / "collect").exists():
        collect_dir = input_dir / "collect"
    else:
        collect_dir = input_dir

    generation_metadata = load_json(generation_dir / "data" / "generation_metadata.json", default={})
    template_profiles = load_json(collect_dir / "data" / "template_style_profiles.json", default={})

    articles = generation_metadata.get("articles", [])
    if not articles:
        context.action_manager.require_and_raise(
            phase="CHECK",
            topic="检查阶段",
            problem="未找到 generation_metadata.json，无法继续检查与修复。",
            attempted_actions=["读取输入目录中的 2_generate/data/generation_metadata.json"],
            cannot_continue_reason="缺少 generate 阶段结果，无法继续检查和修复。",
            user_actions=["请先运行 python main.py --phase generate。"],
            suggested_materials=["generate 阶段输出目录"],
            generated_files=context.created_files_as_strings,
        )

    structure_checker = StructureChecker(context)
    language_checker = LanguageStyleChecker(context, llm_client)
    compliance_checker = ComplianceChecker(context, llm_client)
    rewriter = AutoRewriter(context, llm_client)
    report_builder = ReportBuilder(context)
    final_writer = BlogDocxWriter(context, output_dir=context.paths.final_articles)

    results = []
    for article in articles:
        topic = article["topic"]
        context.set_topic(topic)
        profile = template_profiles.get(topic, article.get("style_profile", {}))
        context.logger.info("CHECK", f"当前检查文章：{article.get('title', topic)}")
        result = {
            "topic": topic,
            "title": article.get("title", topic),
            "article_path": article.get("output_path", ""),
            "word_count": article.get("word_count", 0),
            "supplemental_source_count": article.get("supplemental_source_count", 0),
            "generation_attempts": article.get("generation_attempts", []),
            "quality_gate_failures": article.get("quality_gate_failures", []),
        }
        result["structure"] = structure_checker.check(article, profile)
        result["language"] = language_checker.check(article, profile)
        result["compliance"] = compliance_checker.check(article)

        rewritten, repair_actions = rewriter.rewrite_if_needed(article, result)
        if rewritten is not None:
            article = rewritten
            result["rewritten"] = True
            result["repair_actions"] = repair_actions
            result["structure"] = structure_checker.check(article, profile)
            result["language"] = language_checker.check(article, profile)
            result["compliance"] = compliance_checker.check(article)
        else:
            result["rewritten"] = False
            result["repair_actions"] = repair_actions

        remaining_issues = []
        for group in ("structure", "language", "compliance"):
            remaining_issues.extend(result.get(group, {}).get("issues", []))
        if remaining_issues:
            result["final_conclusion"] = "自动修复后仍未通过，需要补充素材或人工复核。"
            results.append(result)
            report_builder.write(results, context.paths.check)
            context.action_manager.require_and_raise(
                phase="CHECK",
                topic=topic,
                problem=f"文章修复后仍未达标：{'；'.join(remaining_issues)}",
                attempted_actions=repair_actions or ["执行检查但未能自动修复到达标"],
                cannot_continue_reason="最终文章仍存在结构、语言或合规风险，不能假装通过。",
                user_actions=["请补充素材或人工调整后重新运行 check。"],
                suggested_materials=["2_generate/generated_blog_articles", "3_check/quality_check_report.docx"],
                generated_files=context.created_files_as_strings,
            )

        final_output_path = final_writer.write(article, file_suffix="_最终文章")
        context.record_file(final_output_path)
        result["final_article_path"] = str(final_output_path)
        result["final_conclusion"] = report_builder.summarize_result(result)
        results.append(result)

    report_builder.write(results, context.paths.check)
    context.logger.info("CHECK", "check 阶段完成")
