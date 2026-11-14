"""CUDA worker process.

The Qt UI must not run torch / diffusers in-process: inference there
crashes Qt6Core on this machine. This module is launched as a child
process and speaks one JSON object per line.
"""

from __future__ import annotations

import json
import os
import sys

os.environ["IMPRESSION_OIL_CUDA_WORKER"] = "1"
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def _configure_stdio() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def _reply(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def main() -> int:
    _configure_stdio()
    from impression_oil.logging_setup import get_logger, setup_logging
    from impression_oil.paths import models_dir

    setup_logging()
    logger = get_logger("cuda_worker")

    from impression_oil.backends.local import create_engine

    engine = create_engine(models_dir())
    if engine is None:
        _reply({"ok": False, "error": "本机模型不可用，无法启动出图进程。"})
        return 1

    _reply({"ok": True, "ready": True})
    logger.info("cuda worker ready")

    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            _reply({"ok": False, "error": "invalid job"})
            continue
        cmd = job.get("cmd")
        try:
            if cmd == "quit":
                _reply({"ok": True})
                return 0
            if cmd == "prepare":
                engine.prepare()
                _reply({"ok": True})
                continue
            if cmd == "generate":
                from pathlib import Path as FilePath

                path = engine.generate(
                    source_path=FilePath(job["source"]),
                    prompt=job.get("prompt") or "",
                    negative_prompt=job.get("negative_prompt") or "",
                    composition_lock=bool(job.get("composition_lock", True)),
                )
                _reply({"ok": True, "path": str(path)})
                continue
            _reply({"ok": False, "error": f"unknown cmd: {cmd}"})
        except Exception as exc:  # noqa: BLE001
            logger.exception("worker job failed: %s", exc)
            _reply({"ok": False, "error": str(exc)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
