# 印象油画 0.0.1

[中文](README.md) | [English](README.en.md) | [Deutsch](README.de.md)

A local, offline desktop tool: open a photo on your computer and turn it into a Monet-style Impressionist oil painting in one click.

The workbench shows the original photo on the left and the painting on the right. Click **生成油画** (Generate oil painting) to run it. If you are not satisfied, the app reviews the result against its painting-quality checklist and regenerates with a patch; if you are satisfied, you can save. You do not need to choose portrait or landscape first — the program judges the photo and applies the matching approach.

This is not a filter, not an “oil-painting shader,” and not Van Gogh Post-Impressionism. The default path is Monet Impressionism: environmental color, optical mixing, soft edges dissolving into the air, complementary-color shadows, with the composition locked to the source photo.

## What kinds of images work

This version is intended only for real photographs taken with a camera, such as portraits, landscapes, and everyday snapshots. Animation stills, illustrations, anime or cartoon images, comics, screenshots, and pictures that are already drawings are not a good fit and will usually come out looking clearly wrong.

## Requirements

For reasonably smooth generation, you should have:

- **GPU**: An NVIDIA discrete GPU with 8 GB of VRAM or more is recommended. It has been verified on an NVIDIA GeForce RTX 4060 laptop GPU (8 GB). Generation defaults to a longest edge of 768 pixels and automatically falls back to 512 if VRAM is insufficient.
- **Not supported in this version**: machines without an NVIDIA GPU, including those with only integrated graphics, AMD GPUs, or Apple silicon (inference uses CUDA).
- **OS and Python**: Windows 10 or 11, Python 3.10 or later (3.12 recommended).
- **Disk**: Reserve about 8–10 GB. The model weights are about 3.4 GB, plus the PyTorch CUDA runtime.
- **Network**: You need a connection for the first-time install of dependencies and models. After that, the app can run offline. The interface will not start a model download on its own.

## Offline promise

- Choosing a photo, generating, self-checking, and saving all happen on this computer. Files are not uploaded.
- The program does not make network requests by default, and it will not download models automatically.
- Once dependencies and the local models are installed, you can use it without a network.

## What 0.0.1 includes — and what it does not

**Ready to use**

- A complete Chinese-language interface (open, drag-and-drop, side-by-side preview, regenerate, return to the start screen, save).
- A **满意 / 不满意** (Satisfied / Not satisfied) flow: Not satisfied runs a checklist for painting-quality gaps and scenery drift, then regenerates with patch prompts.
- A local SD 1.5 + ControlNet Tile + Monet LoRA engine (install dependencies and models first, as below).
- Style prompts, scene detection, the review checklist, and the pipeline state machine (covered by tests).

**Model weights are not in this repository**

- The models are about 3.4 GB and are not included here. Download them into the `models/` folder with the steps below.
- If you click **生成油画** before the models are installed, the interface will explain what is missing, but it **will not start a download automatically**.

## Install dependencies

You need Python 3.10 or later (3.12 recommended) and a working NVIDIA GPU.

```text
cd impression-oil
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
python -m pip install diffusers==0.43.0 transformers accelerate safetensors huggingface_hub peft
```

Install `torch` from the official PyTorch CUDA 12.4 index, not the CPU build. On Linux or macOS, use `python3` instead of `py -3`, and activate the venv with `source .venv/bin/activate`. The generation path has been verified on Windows with an NVIDIA GPU.

You can also install only the interface as an editable package (this alone is not enough to generate images):

```text
python -m pip install -e .
```

## Install the local models

In the activated virtual environment, from the project directory, run:

```text
python scripts/install_local_model.py
```

The models are downloaded into the project’s `models/` directory, about 3.4 GB. If Hugging Face is unreliable, set a mirror first, then run the installer:

```text
set HF_ENDPOINT=https://hf-mirror.com
python scripts/install_local_model.py
```

You only need to do this once. After that, generation works offline. The first time you click **生成油画** in the app, loading the models may take about a minute; later runs are much faster.

## Launch

Double-click `run.bat` in the project folder, or run it from a terminal:

```text
run.bat
```

`run.bat` prefers the project’s `.venv`, then `py -3`, then `python`. It adds `src` to `PYTHONPATH`, so you do not have to install the package first. The repository also includes `launch.vbs`, which you can use to create a desktop shortcut that does not open a console window.

You can also run:

```text
python -m impression_oil
```

(If you are not using `run.bat`, activate the virtual environment first, or set `PYTHONPATH=src` yourself.)

## How “Satisfied” and “Not satisfied” work

1. Open or drop a local JPG / PNG photo (JPEG and WebP are also supported).
2. Click **生成油画** in the middle. If the local models are not installed yet, you will see a non-blocking notice; the rest of the interface still works.
3. After generation, **满意** (Satisfied) and **不满意** (Not satisfied) appear under the result.
4. Click **满意**: the result is marked as accepted, and you can click **保存** (Save) in the top right. If you have not saved yet, Save stays available as a reminder. Nothing is uploaded automatically.
5. Click **不满意**: the app immediately reviews the result against the source (clumpy sky, dead local color, hard-edged distant mountains, stamped flower fields, illustration-like figures, scenery or composition drift). The footer expands to “reviewed with the patch checklist, regenerating,” the center shows “regenerating…,” and the whole image is painted again with patch prompts (keeping improved technique, while locking any lost or shifted scenery back to the source). Choose again when the new result appears, until you are satisfied.
6. After a result is ready, you can also click **回到初始界面** (Return to start) in the top bar to go back to the empty drop-zone. Paintings you have already saved stay on this computer and are not deleted.

The save dialog is titled **保存油画** (Save oil painting). The default file name looks like `original-name-印象油画.jpg`. You can save JPEG or PNG.

## Run tests

```text
python -m pip install -r requirements.txt
python -m pytest
```

These tests do not require the models or a GPU.

## Version

The current version is **0.0.1**. See `VERSION`, `pyproject.toml`, and the window title “印象油画 0.0.1”.
