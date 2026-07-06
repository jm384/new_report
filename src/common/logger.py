from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback


LOG_LEVEL_PRIORITY = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "ACTION_REQUIRED": 45,
}


class RunLogger:
    def __init__(
        self,
        *,
        log_path: Path,
        level: str = "INFO",
        print_to_console: bool = True,
        save_to_file: bool = True,
    ) -> None:
        self.log_path = log_path
        self.level = level.upper()
        self.print_to_console = print_to_console
        self.save_to_file = save_to_file
        self._handle = None
        if save_to_file:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.log_path.open("a", encoding="utf-8")

    def _should_log(self, level: str) -> bool:
        wanted = LOG_LEVEL_PRIORITY.get(self.level, 20)
        actual = LOG_LEVEL_PRIORITY.get(level, 20)
        return actual >= wanted

    def _emit(self, level: str, phase: str, message: str) -> None:
        if not self._should_log(level):
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] [{phase}] [{level}] {message}"
        if self.print_to_console:
            print(line)
        if self._handle is not None:
            self._handle.write(line + "\n")
            self._handle.flush()

    def debug(self, phase: str, message: str) -> None:
        self._emit("DEBUG", phase, message)

    def info(self, phase: str, message: str) -> None:
        self._emit("INFO", phase, message)

    def warning(self, phase: str, message: str) -> None:
        self._emit("WARNING", phase, message)

    def error(self, phase: str, message: str) -> None:
        self._emit("ERROR", phase, message)

    def action_required(self, phase: str, message: str) -> None:
        self._emit("ACTION_REQUIRED", phase, message)

    def exception(self, phase: str, message: str, exc: Exception) -> None:
        self._emit("ERROR", phase, f"{message}: {exc}")
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        for line in tb.strip().splitlines():
            self._emit("ERROR", phase, line)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
