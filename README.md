# 印象油画 0.0.1

[中文](README.md) | [English](README.en.md) | [Deutsch](README.de.md)

本机离线的桌面小工具：打开一张本地照片，一键转成莫奈式印象派油画。

左右对照工作台：左边是原照，右边是油画结果。点「生成油画」出图；不满意就按补丁方案自查并重画，满意后再保存。不需要先选手像或风景，程序会按照片自行判断并套用相应画法。

这不是滤镜或「油画着色器」工具，也不是梵高后期印象派。默认路径是莫奈印象派：环境色、光学混合、柔边溶入空气、补色阴影，构图锁在原照上。

## 适合什么样的图

这个版本只适合用相机拍下的真实照片，比如人像、风景、生活快照。动画、插画、二次元、漫画、截图，或已经画过的图片都不适合，出图往往会明显走样。

## 配置要求

要比较顺畅地出图，建议满足下面这些条件：

- **显卡**：NVIDIA 独立显卡，显存建议 8GB 或以上。已在 NVIDIA GeForce RTX 4060 笔记本显卡（8GB 显存）上验证可运行。默认按照片长边 768 出图；显存不足时会自动降到 512。
- **目前不支持**：没有 NVIDIA 显卡，或只有核显、AMD 显卡、Apple 芯片的机器，这个版本还不能出图（推理走 CUDA）。
- **系统与 Python**：Windows 10 或 11，Python 3.10 或更高版本（推荐 3.12）。
- **硬盘**：请预留大约 8 到 10GB 空间。模型权重约 3.4GB，再加上 PyTorch CUDA 运行环境。
- **网络**：第一次安装依赖和下载模型需要联网；装好之后可以离线使用。程序界面不会自动下载模型。

## 离线承诺

- 选照片、出图、自查、保存都在本机完成，文件不会上传到网络。
- 程序默认不会发起任何网络请求，也不会自动下载模型。
- 安装好依赖，并完成一次本机模型安装之后，没有网络也能使用。

## 0.0.1 里有什么、没有什么

**已经可以用**

- 完整中文界面（打开、拖入、左右对照、再生成、回到初始界面、保存）。
- 「满意 / 不满意」流程：点不满意会按画法差距和景色走样逐项自查，再带着补丁提示重画。
- 本机 SD 1.5 + ControlNet Tile + 莫奈 LoRA 出图引擎（需先按下文安装依赖和模型）。
- 画法提示词、场景判断、自查清单和流水线状态机（可用测试验证）。

**仓库不附带模型权重**

- 模型文件大约 3.4GB，不包含在本仓库中，需要按下面的步骤自行下载到 `models/` 目录。
- 点「生成油画」时，如果还没装模型，界面会给出说明，但**不会自动开始下载**。

## 安装依赖

需要 Python 3.10 或更高版本（推荐 3.12），以及一块可用的 NVIDIA 显卡。

```text
cd impression-oil
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
python -m pip install diffusers==0.43.0 transformers accelerate safetensors huggingface_hub peft
```

请从 PyTorch 官方 CUDA 12.4 索引安装 `torch`，不要安装 CPU 版本。Linux / macOS 把 `py -3` 换成 `python3`，激活脚本则是 `source .venv/bin/activate`。当前出图路径按 Windows + NVIDIA GPU 验证。

也可以只安装界面运行时并按可编辑包安装（这样还不能出图）：

```text
python -m pip install -e .
```

## 安装本机模型

在已激活的虚拟环境中，于项目目录执行：

```text
python scripts/install_local_model.py
```

模型会下载到项目里的 `models/` 目录，约 3.4GB。如果访问 Hugging Face 不稳定，可先设置镜像后再运行：

```text
set HF_ENDPOINT=https://hf-mirror.com
python scripts/install_local_model.py
```

只需要安装一次。装好后即可离线出图。第一次在软件里点「生成油画」时，加载模型大约需要一分钟，之后会快很多。

## 启动

在项目目录双击 `run.bat`，或在命令行执行：

```text
run.bat
```

`run.bat` 会优先使用项目里的 `.venv`，找不到再用 `py -3`，最后才用 `python`。它会把 `src` 加入 `PYTHONPATH`，因此不必先安装包。仓库里还有 `launch.vbs`，可用它创建不弹出命令行窗口的桌面快捷方式。

也可以：

```text
python -m impression_oil
```

（若未使用 `run.bat`，请先激活虚拟环境，或自行设置 `PYTHONPATH=src`。）

## 「满意」和「不满意」怎么用

1. 打开或拖入一张本地 JPG / PNG（也支持 JPEG、WebP）照片。
2. 点中间的「生成油画」。若本机模型尚未安装，会看到一条不打断操作的说明，界面其余部分仍可继续使用。
3. 出图后，结果下方出现「满意」和「不满意」。
4. 点「满意」：将结果标为接受，可以点右上角「保存」。若尚未保存，「保存」会保持可用来提醒你。不会自动上传到任何地方。
5. 点「不满意」：立即按补丁方案对照原照自查（天空结块、死固有色、远山硬边、花田印章、人物插画切图、景色/构图走样）。底部展开「已按补丁自查，正在重画」，中间显示「正在重画…」，然后带着补丁提示整张重画（保住已改善的画法，同时把丢失或错位的景色按原照锁回去）。新结果出来后再次选择，直到满意为止。
6. 出图完成后，也可以点顶栏「回到初始界面」，回到拖入照片的起始画面。已经保存的油画还在本机，不会被删掉。

保存对话框标题为「保存油画」，默认文件名形如 `原文件名-印象油画.jpg`，可选 JPEG 或 PNG。

## 运行测试

```text
python -m pip install -r requirements.txt
python -m pytest
```

这些测试不需要安装模型，也不需要 GPU。

## 版本

当前版本为 **0.0.1**，见 `VERSION`、`pyproject.toml` 和窗口标题「印象油画 0.0.1」。
