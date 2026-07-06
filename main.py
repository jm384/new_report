from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.collect import run_collect_phase
from src.check import run_check_phase
from src.common.action_required import PhaseHaltError
from src.common.env_loader import load_settings
from src.common.llm_client import LLMClient
from src.common.runtime import create_run_context, resolve_input_run_dir
from src.generate import run_generate_phase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="纽约州华人律师事务所中文法律科普博客自动生成项目"
    )
    parser.add_argument(
        "--phase",
        choices=["collect", "generate", "check", "all"],
        default="all",
        help="要运行的阶段",
    )
    parser.add_argument(
        "--input-run-dir",
        default="",
        help="单独运行 generate/check 时读取的历史 outputs/output_* 主目录",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="随机种子，便于复现主题选择结果",
    )
    return parser


def run() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parent
    settings = load_settings(project_root)
    input_run_dir = resolve_input_run_dir(project_root, args.phase, args.input_run_dir)
    context = create_run_context(
        project_root=project_root,
        settings=settings,
        initial_phase=args.phase.upper(),
        input_run_dir=input_run_dir,
        seed=args.seed,
    )
    llm_client = LLMClient(settings=settings, logger=context.logger)

    try:
        if args.phase == "collect":
            run_collect_phase(context, llm_client)
        elif args.phase == "generate":
            run_generate_phase(context, llm_client)
        elif args.phase == "check":
            run_check_phase(context, llm_client)
        else:
            run_collect_phase(context, llm_client)
            run_generate_phase(context, llm_client)
            run_check_phase(context, llm_client)

        context.logger.info("ALL", "本次任务完成")
        if context.action_manager.has_entries:
            context.action_manager.write()
        return 0
    except PhaseHaltError as exc:
        context.logger.error("ALL", f"任务中止：{exc}")
        context.action_manager.write()
        return 2
    except Exception as exc:  # pragma: no cover - fallback protection
        context.logger.exception("ALL", "出现未处理异常", exc)
        context.action_manager.add_entry(
            phase=context.phase,
            topic=context.current_topic,
            problem=f"程序出现未处理异常：{exc}",
            attempted_actions=["捕获顶层异常并记录日志"],
            cannot_continue_reason="存在未处理异常，当前阶段无法安全继续执行。",
            user_actions=["请检查日志并修复报错，或将日志提供给开发人员排查。"],
            suggested_materials=["完整日志文件", "当前 outputs 目录中的中间数据"],
            generated_files=context.created_files_as_strings,
        )
        context.action_manager.write()
        return 3
    finally:
        context.logger.close()


if __name__ == "__main__":
    sys.exit(run())
