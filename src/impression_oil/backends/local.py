"""Local Stable Diffusion img2img backend.

Weights must already be on disk. This module never starts a download.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from impression_oil.engine import GenerationError, ImageEngine
from impression_oil.paths import outputs_dir

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
    try:
        import torch  # noqa: F401
        from diffusers import ControlNetModel  # noqa: F401
    except ImportError:
        return None
    return LocalDiffusersEngine(directory)


class LocalDiffusersEngine(ImageEngine):
    def __init__(self, models_directory: Path) -> None:
        self.models_directory = Path(models_directory)
        self._pipe = None
        self._manifest = json.loads(
            (self.models_directory / MANIFEST_NAME).read_text(encoding="utf-8")
        )

    def is_available(self) -> bool:
        return models_are_ready(self.models_directory)

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

        pipe = self._ensure_pipeline()
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
    width, height = image.size
    longest = max(width, height)
    scale = min(1.0, max_edge / float(longest))
    new_w = max(64, int(round(width * scale / 8.0) * 8))
    new_h = max(64, int(round(height * scale / 8.0) * 8))
    if (new_w, new_h) != (width, height):
        image = image.resize((new_w, new_h), image.Resampling.LANCZOS)
    return image, (new_w, new_h)
