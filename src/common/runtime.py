from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import random

from config import AppSettings
from src.common.action_required import ActionRequiredManager
from src.common.file_utils import (
    ensure_dir,
    find_latest_run_dir_with_marker,
    timestamp_for_run,
)
from src.common.logger import RunLogger


@dataclass(slots=True)
class RunPaths:
    root: Path
    collect: Path
    check: Path
    generate: Path
    topic_research_docs: Path
    generated_blog_articles: Path
    final_articles: Path
    data: Path


@dataclass(slots=True)
class RunContext:
    project_root: Path
    settings: AppSettings
    run_id: str
    phase: str
    paths: RunPaths
    log_path: Path
    logger: RunLogger
    action_manager: ActionRequiredManager
    seed: int | None = None
    rng: random.Random = field(default_factory=random.Random)
    input_run_dir: Path | None = None
    current_topic: str = ""
    current_topic_category: str = ""
    created_files: list[Path] = field(default_factory=list)

    @property
    def created_files_as_strings(self) -> list[str]:
        return [str(path) for path in self.created_files]

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def set_topic(self, topic: str) -> None:
        self.current_topic = topic

    def set_topic_category(self, category: str) -> None:
        self.current_topic_category = category

    def record_file(self, path: Path) -> None:
        self.created_files.append(path)


def _normalize_run_dir(project_root: Path, value: Path) -> Path:
    path = value if value.is_absolute() else project_root / value
    parts = path.parts
    if path.name in {"1_collect", "2_generate", "3_check", "2_check", "3_generate"}:
        return path.parent
    if len(parts) >= 2 and parts[-2] == "outputs" and path.name.startswith(("output_", "run_")):
        return path
    if path.parent.name.startswith("output_") or path.parent.name.startswith("run_"):
        return path.parent
    return path


def resolve_input_run_dir(project_root: Path, phase: str, input_run_dir_value: str) -> Path | None:
    if phase not in {"generate", "check"}:
        return None
    if input_run_dir_value:
        return _normalize_run_dir(project_root, Path(input_run_dir_value))
    if phase == "generate":
        resolved = find_latest_run_dir_with_marker(
            project_root / "outputs",
            Path("1_collect/data/selected_topics.json"),
        )
        if resolved is not None:
            return resolved
        return find_latest_run_dir_with_marker(
            project_root / "outputs",
            Path("collect/data/selected_topics.json"),
        )
    resolved = find_latest_run_dir_with_marker(
        project_root / "outputs",
        Path("2_generate/data/generation_metadata.json"),
    )
    if resolved is not None:
        return resolved
    return find_latest_run_dir_with_marker(
        project_root / "outputs",
        Path("generate/data/generation_metadata.json"),
    )


def create_run_context(
    *,
    project_root: Path,
    settings: AppSettings,
    initial_phase: str,
    input_run_dir: Path | None,
    seed: int | None,
) -> RunContext:
    if initial_phase == "COLLECT" or input_run_dir is None:
        run_id = timestamp_for_run()
        run_root = ensure_dir(project_root / "outputs" / f"output_{run_id}")
    else:
        run_root = _normalize_run_dir(project_root, input_run_dir)
        run_id = run_root.name.replace("output_", "").replace("run_", "")
        ensure_dir(run_root)

    collect_root = run_root / "1_collect"
    generate_root = run_root / "2_generate"
    check_root = run_root / "3_check"
    paths = RunPaths(
        root=run_root,
        collect=collect_root,
        check=check_root,
        generate=generate_root,
        topic_research_docs=collect_root / "topic_research_docs",
        generated_blog_articles=generate_root / "generated_blog_articles",
        final_articles=check_root / "final_articles",
        data=collect_root / "data",
    )
    log_path = ensure_dir(project_root / "logs") / f"run_{run_id}.log"
    logger = RunLogger(
        log_path=log_path,
        level=settings.logging.level,
        print_to_console=settings.logging.print_detailed_logs,
        save_to_file=settings.logging.save_logs,
    )
    action_manager = ActionRequiredManager(
        output_path=run_root / "ACTION_REQUIRED.md",
        log_path=log_path,
    )
    context = RunContext(
        project_root=project_root,
        settings=settings,
        run_id=run_id,
        phase=initial_phase,
        paths=paths,
        log_path=log_path,
        logger=logger,
        action_manager=action_manager,
        seed=seed,
        input_run_dir=input_run_dir,
    )
    context.rng.seed(seed if seed is not None else run_id)
    logger.info(initial_phase, f"当前运行主目录：{run_root}")
    if input_run_dir:
        logger.info(initial_phase, f"读取历史输入目录：{input_run_dir}")
    return context
