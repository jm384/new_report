from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import json


class PhaseHaltError(RuntimeError):
    """Raised when a phase must stop and wait for user coordination."""


@dataclass(slots=True)
class ActionRequiredEntry:
    timestamp: str
    phase: str
    topic: str
    problem: str
    attempted_actions: list[str]
    cannot_continue_reason: str
    user_actions: list[str]
    suggested_materials: list[str]
    related_log_path: str
    generated_files: list[str]


class ActionRequiredManager:
    def __init__(self, output_path: Path, log_path: Path) -> None:
        self.output_path = output_path
        self.log_path = log_path
        self.entries: list[ActionRequiredEntry] = []

    @property
    def has_entries(self) -> bool:
        return bool(self.entries)

    def add_entry(
        self,
        *,
        phase: str,
        topic: str,
        problem: str,
        attempted_actions: list[str],
        cannot_continue_reason: str,
        user_actions: list[str],
        suggested_materials: list[str],
        generated_files: list[str],
    ) -> None:
        self.entries.append(
            ActionRequiredEntry(
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                phase=phase,
                topic=topic or "未指定主题",
                problem=problem,
                attempted_actions=attempted_actions,
                cannot_continue_reason=cannot_continue_reason,
                user_actions=user_actions,
                suggested_materials=suggested_materials,
                related_log_path=str(self.log_path),
                generated_files=generated_files,
            )
        )

    def require_and_raise(
        self,
        *,
        phase: str,
        topic: str,
        problem: str,
        attempted_actions: list[str],
        cannot_continue_reason: str,
        user_actions: list[str],
        suggested_materials: list[str],
        generated_files: list[str],
    ) -> None:
        self.add_entry(
            phase=phase,
            topic=topic,
            problem=problem,
            attempted_actions=attempted_actions,
            cannot_continue_reason=cannot_continue_reason,
            user_actions=user_actions,
            suggested_materials=suggested_materials,
            generated_files=generated_files,
        )
        raise PhaseHaltError(problem)

    def write(self) -> Path | None:
        if not self.entries:
            return None

        lines = ["# 需要用户协调解决的问题", ""]
        for index, entry in enumerate(self.entries, start=1):
            lines.extend(
                [
                    f"## 问题 {index}",
                    "",
                    f"**当前运行时间**：{entry.timestamp}",
                    "",
                    f"**当前阶段**：{entry.phase}",
                    "",
                    f"**当前主题**：{entry.topic}",
                    "",
                    "### 问题",
                    entry.problem,
                    "",
                    "### 已尝试",
                ]
            )
            lines.extend([f"- {item}" for item in entry.attempted_actions] or ["- 无"])
            lines.extend(
                [
                    "",
                    "### 无法继续的原因",
                    entry.cannot_continue_reason,
                    "",
                    "### 请用户协调解决",
                ]
            )
            lines.extend([f"- {item}" for item in entry.user_actions] or ["- 无"])
            lines.extend(
                [
                    "",
                    "### 建议用户提供的材料或配置",
                ]
            )
            lines.extend([f"- {item}" for item in entry.suggested_materials] or ["- 无"])
            lines.extend(
                [
                    "",
                    "### 日志路径",
                    entry.related_log_path,
                    "",
                    "### 已生成文件",
                ]
            )
            lines.extend([f"- {item}" for item in entry.generated_files] or ["- 无"])
            lines.append("")

        self.output_path.write_text("\n".join(lines), encoding="utf-8")

        json_path = self.output_path.with_suffix(".json")
        json_path.write_text(
            json.dumps([asdict(entry) for entry in self.entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.output_path
