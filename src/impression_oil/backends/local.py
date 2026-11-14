"""Local Stable Diffusion img2img backend.

Weights must already be on disk. This module never starts a download.
"""

from __future__ import annotations

import atexit
import importlib.util
import json
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from impression_oil.engine import GenerationError, ImageEngine
from impression_oil.paths import outputs_dir, project_root

LOGGER = logging.getLogger("impression_oil.backends.local")

MANIFEST_NAME = "manifest.json"


def models_are_ready(models_dir: Path) -> bool:
    manifest_path = Path(models_dir) / MANIFEST_NAME
    if not manifest_path.is_file():
        return False
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for relative in data.get("required_paths", []):
        if not (Path(models_dir) / relative).exists():
            return False
    return True


def create_engine(models_dir: Path) -> ImageEngine | None:
    """Factory used by impression_oil.engine.get_engine."""
    directory = Path(models_dir)
    if not models_are_ready(directory):
        return None
    if os.environ.get("IMPRESSION_OIL_CUDA_WORKER") == "1":
        return LocalDiffusersEngine(directory)
    # The Qt UI process must not import torch. On this machine, running
    # img2img inside the GUI process crashes Qt6Core.dll.
    if importlib.util.find_spec("torch") is None or importlib.util.find_spec("diffusers") is None:
        return None
    return LocalEngineProxy(directory)


class LocalDiffusersEngine(ImageEngine):
    def __init__(self, models_directory: Path) -> None:
        self.models_directory = Path(models_directory)
        self._pipe = None
        self._manifest = json.loads(
            (self.models_directory / MANIFEST_NAME).read_text(encoding="utf-8")
        )

    def is_available(self) -> bool:
        return models_are_ready(self.models_directory)

    def prepare(self) -> None:
        """Load CUDA weights in this process."""
        self._ensure_pipeline()

    def unavailable_reason(self) -> str:
        if not models_are_ready(self.models_directory):
            return "本机模型不完整。请重新安装模型后再生成。"
        return "本机模型的运行库还没装好，暂时不能出图。"

    def generate(
        self,
        source_path: Path,
        prompt: str,
        negative_prompt: str,
        composition_lock: bool = True,
    ) -> Path:
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover
            raise GenerationError("缺少 Pillow，无法读取照片。") from exc

        try:
            source = Image.open(source_path).convert("RGB")
        except OSError as exc:
            raise GenerationError(f"无法打开照片：{source_path}") from exc

        LOGGER.info("generating from %s", source_path)
        pipe = self._ensure_pipeline()
        LOGGER.info("pipeline ready, starting img2img")
        prompt_text = _with_trigger(prompt, self._manifest.get("lora_trigger", "Monet Style"))
        strength = 0.52 if composition_lock else 0.68
        control_scale = 0.82 if composition_lock else 0.5

        import torch

        seed = int(time.time() * 1000) % (2**31 - 1)
        device = getattr(pipe, "device", torch.device("cuda"))
        gen_device = "cuda" if device.type == "cuda" else "cpu"
        generator = torch.Generator(device=gen_device)
        generator.manual_seed(seed)

        result = None
        last_oom = None
        for max_edge, steps in ((768, 28), (512, 24)):
            working, work_size = _resize_for_model(source, max_edge=max_edge)
            LOGGER.info("img2img at %sx%s, steps=%s", work_size[0], work_size[1], steps)
            try:
                result = pipe(
                    prompt=prompt_text,
                    negative_prompt=negative_prompt or None,
                    image=working,
                    control_image=working,
                    strength=strength,
                    num_inference_steps=steps,
                    guidance_scale=7.0,
                    controlnet_conditioning_scale=control_scale,
                    generator=generator,
                    width=work_size[0],
                    height=work_size[1],
                ).images[0]
                break
            except torch.cuda.OutOfMemoryError as exc:
                last_oom = exc
                torch.cuda.empty_cache()
                LOGGER.warning("CUDA OOM at max_edge=%s, retrying smaller", max_edge)
                continue
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("local generation failed")
                raise GenerationError(f"本机出图失败：{exc}") from exc

        if result is None:
            raise GenerationError("显存不够，这次没能出图。请关掉其它占显卡的程序后再试。") from last_oom

        if result.size != source.size:
            result = result.resize(source.size, Image.Resampling.LANCZOS)

        out_path = outputs_dir() / f"{Path(source_path).stem}-印象油画-{seed}.jpg"
        result.save(out_path, format="JPEG", quality=95, subsampling=0)
        return out_path

    def _ensure_pipeline(self):
        if self._pipe is not None:
            return self._pipe

        import torch
        from diffusers import (
            ControlNetModel,
            StableDiffusionControlNetImg2ImgPipeline,
            UniPCMultistepScheduler,
        )

        if not torch.cuda.is_available():
            raise GenerationError("没有检测到可用的 NVIDIA 显卡，本机模型无法出图。")

        base_dir = self.models_directory / self._manifest["base_dir"]
        control_dir = self.models_directory / self._manifest["controlnet_dir"]
        lora_path = self.models_directory / self._manifest["lora_path"]

        try:
            controlnet = ControlNetModel.from_pretrained(
                control_dir,
                torch_dtype=torch.float16,
                local_files_only=True,
            )
            pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(
                base_dir,
                controlnet=controlnet,
                torch_dtype=torch.float16,
                safety_checker=None,
                requires_safety_checker=False,
                local_files_only=True,
                variant="fp16",
            )
        except Exception as exc:  # noqa: BLE001
            raise GenerationError(f"无法加载本机模型：{exc}") from exc

        pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
        if lora_path.is_file():
            pipe.load_lora_weights(str(lora_path.parent), weight_name=lora_path.name)
            scale = float(self._manifest.get("lora_scale", 0.85))
            try:
                pipe.fuse_lora(lora_scale=scale)
            except TypeError:
                pipe.fuse_lora()
        if hasattr(pipe, "enable_attention_slicing"):
            pipe.enable_attention_slicing()
        if hasattr(pipe, "enable_vae_slicing"):
            pipe.enable_vae_slicing()
        elif hasattr(getattr(pipe, "vae", None), "enable_slicing"):
            pipe.vae.enable_slicing()
        pipe.to("cuda")
        self._pipe = pipe
        return pipe


def _with_trigger(prompt: str, trigger: str) -> str:
    text = (prompt or "").strip()
    if trigger and trigger.lower() not in text.lower():
        return f"{trigger}, {text}" if text else trigger
    return text


def _resize_for_model(image, max_edge: int = 768):
    from PIL import Image as PILImage

    width, height = image.size
    longest = max(width, height)
    scale = min(1.0, max_edge / float(longest))
    new_w = max(64, int(round(width * scale / 8.0) * 8))
    new_h = max(64, int(round(height * scale / 8.0) * 8))
    if (new_w, new_h) != (width, height):
        image = image.resize((new_w, new_h), PILImage.Resampling.LANCZOS)
    return image, (new_w, new_h)

class LocalEngineProxy(ImageEngine):
    """Talks to a child process that owns torch / CUDA."""

    def __init__(self, models_directory: Path) -> None:
        self.models_directory = Path(models_directory)
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        atexit.register(self.close)

    def is_available(self) -> bool:
        return models_are_ready(self.models_directory)

    def unavailable_reason(self) -> str:
        if not models_are_ready(self.models_directory):
            return "本机模型不完整。请重新安装模型后再生成。"
        return "本机模型的运行库还没装好，暂时不能出图。"

    def prepare(self) -> None:
        self._rpc({"cmd": "prepare"}, timeout=180)

    def generate(
        self,
        source_path: Path,
        prompt: str,
        negative_prompt: str,
        composition_lock: bool = True,
    ) -> Path:
        data = self._rpc(
            {
                "cmd": "generate",
                "source": str(source_path),
                "prompt": prompt or "",
                "negative_prompt": negative_prompt or "",
                "composition_lock": bool(composition_lock),
            },
            timeout=300,
        )
        path = Path(data.get("path") or "")
        if not path.is_file():
            raise GenerationError("出图进程没有返回结果文件。")
        return path

    def close(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            if proc.stdin:
                proc.stdin.write(json.dumps({"cmd": "quit"}) + "\n")
                proc.stdin.flush()
        except OSError:
            pass
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()

    def _ensure_worker(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        python = Path(sys.executable)
        if python.name.lower() == "pythonw.exe":
            cand = python.with_name("python.exe")
            if cand.is_file():
                python = cand
        env = os.environ.copy()
        src = str(project_root() / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        env["IMPRESSION_OIL_CUDA_WORKER"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        flags = 0
        if sys.platform.startswith("win"):
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        LOGGER.info("starting cuda worker: %s", python)
        self._proc = subprocess.Popen(
            [str(python), "-u", "-m", "impression_oil.backends.cuda_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(project_root()),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        hello = self._read_json(timeout=60)
        if not hello.get("ok"):
            self.close()
            raise GenerationError(hello.get("error") or "出图进程启动失败。")

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        for line in proc.stderr:
            text = line.rstrip()
            if text:
                LOGGER.info("cuda worker: %s", text)

    def _rpc(self, payload: dict, timeout: int) -> dict:
        with self._lock:
            self._ensure_worker()
            proc = self._proc
            if proc is None or proc.stdin is None:
                raise GenerationError("出图进程不可用。")
            try:
                proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                proc.stdin.flush()
            except OSError as exc:
                raise GenerationError("无法与出图进程通信。") from exc
            data = self._read_json(timeout=timeout)
            if not data.get("ok"):
                raise GenerationError(data.get("error") or "出图进程返回失败。")
            return data

    def _read_json(self, timeout: int) -> dict:
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise GenerationError("出图进程不可用。")
        result: dict | None = None
        error: Exception | None = None

        def _reader() -> None:
            nonlocal result, error
            try:
                while True:
                    line = proc.stdout.readline()
                    if line == "":
                        code = proc.poll()
                        raise GenerationError(f"出图进程已退出（代码 {code}）。")
                    text = line.strip()
                    if text.startswith("{") and text.endswith("}"):
                        result = json.loads(text)
                        return
            except Exception as exc:  # noqa: BLE001
                error = exc

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            raise GenerationError("出图进程超时，这次没有完成。")
        if error is not None:
            raise GenerationError(str(error)) from error
        if result is None:
            raise GenerationError("出图进程没有返回结果。")
        return result
