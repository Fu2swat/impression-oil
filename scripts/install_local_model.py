"""One-time local model installer for 印象油画.

Downloads SD 1.5 (fp16), ControlNet Tile, and a Monet LoRA into models/.
Never called by the app itself; run this script once on the user's computer.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BASE_REPO = "stable-diffusion-v1-5/stable-diffusion-v1-5"
CONTROLNET_REPO = "lllyasviel/control_v11f1e_sd15_tile"
LORA_REPO = "neonforestmist/sd15-monet-lora"
LORA_WEIGHT = "monet_style_lora.safetensors"

# Skip the large fp32 / ckpt / safety-checker files. fp16 weights are enough.
BASE_ALLOW = [
    "model_index.json",
    "scheduler/**",
    "tokenizer/**",
    "feature_extractor/**",
    "text_encoder/config.json",
    "text_encoder/model.fp16.safetensors",
    "unet/config.json",
    "unet/diffusion_pytorch_model.fp16.safetensors",
    "vae/config.json",
    "vae/diffusion_pytorch_model.fp16.safetensors",
]
CONTROL_ALLOW = [
    "config.json",
    "diffusion_pytorch_model.fp16.safetensors",
    "diffusion_pytorch_model.safetensors",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def models_root() -> Path:
    override = os.environ.get("IMPRESSION_OIL_MODELS")
    if override:
        return Path(override).expanduser()
    return project_root() / "models"


def _endpoint() -> str:
    return os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")


def snapshot(repo_id: str, local_dir: Path, allow_patterns=None, extra=None) -> None:
    from huggingface_hub import snapshot_download

    local_dir.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "repo_id": repo_id,
        "local_dir": str(local_dir),
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    if allow_patterns:
        kwargs["allow_patterns"] = allow_patterns
    if extra:
        kwargs.update(extra)
    print(f"Downloading {repo_id} -> {local_dir}", flush=True)
    snapshot_download(**kwargs)


def write_manifest(root: Path) -> Path:
    required = [
        "manifest.json",
        "sd15/model_index.json",
        "sd15/unet/diffusion_pytorch_model.fp16.safetensors",
        "sd15/vae/diffusion_pytorch_model.fp16.safetensors",
        "sd15/text_encoder/model.fp16.safetensors",
        "controlnet-tile/config.json",
        "lora/monet_style_lora.safetensors",
    ]
    # ControlNet weight may be fp16 or full name depending on the repo.
    control_fp16 = root / "controlnet-tile" / "diffusion_pytorch_model.fp16.safetensors"
    control_full = root / "controlnet-tile" / "diffusion_pytorch_model.safetensors"
    if control_fp16.is_file():
        required.append("controlnet-tile/diffusion_pytorch_model.fp16.safetensors")
    elif control_full.is_file():
        required.append("controlnet-tile/diffusion_pytorch_model.safetensors")
    else:
        raise FileNotFoundError("ControlNet weight missing after download")

    manifest = {
        "name": "impression-oil-local-sd15",
        "base_repo": BASE_REPO,
        "base_dir": "sd15",
        "controlnet_repo": CONTROLNET_REPO,
        "controlnet_dir": "controlnet-tile",
        "lora_repo": LORA_REPO,
        "lora_path": "lora/monet_style_lora.safetensors",
        "lora_trigger": "Monet Style",
        "lora_scale": 0.85,
        "required_paths": required,
    }
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    root = models_root()
    root.mkdir(parents=True, exist_ok=True)
    print(f"Models directory: {root}", flush=True)
    print(f"Hub endpoint: {_endpoint()}", flush=True)

    snapshot(BASE_REPO, root / "sd15", allow_patterns=BASE_ALLOW)
    snapshot(CONTROLNET_REPO, root / "controlnet-tile", allow_patterns=CONTROL_ALLOW)
    snapshot(LORA_REPO, root / "lora", allow_patterns=[LORA_WEIGHT, "README.md"])
    write_manifest(root)
    print("MODEL_INSTALL_OK", flush=True)
    print(f"Installed to {root}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"MODEL_INSTALL_FAILED: {exc}", file=sys.stderr)
        raise
