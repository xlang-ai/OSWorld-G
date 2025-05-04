<p align="center">
  <img src="https://huggingface.co/datasets/xlangai/assets/resolve/main/github_banner_v2.png" alt="Banner">
</p>

<p align="center">
  <a href="https://os-world.github.io/">Website</a> •
  <a href="https://arxiv.org/abs/2404.07972">Paper</a> •
  <a href="https://timothyxxx.github.io/OSWorld/">Doc</a> •
  <a href="https://github.com/xlang-ai/OSWorld/tree/main/evaluation_examples">Data</a> •
  <a href="https://os-world.github.io/explorer.html">Data Viewer</a> •
  <a href="https://discord.gg/4Gnw7eTEZR">Discord</a> •
  <a href="https://drive.google.com/file/d/1XlEy49otYDyBlA3O9NbR0BpPfr2TXgaD/view?usp=drive_link">Cache</a>
</p>

<p align="center">
    <a href="https://img.shields.io/badge/PRs-Welcome-red">
        <img src="https://img.shields.io/badge/PRs-Welcome-red">
    </a>
    <a href="https://img.shields.io/github/last-commit/xlang-ai/OSWorld?color=green">
        <img src="https://img.shields.io/github/last-commit/xlang-ai/OSWorld?color=green">
    </a>
    <a href="https://opensource.org/licenses/Apache-2.0">
        <img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg">
    </a>
    <a href="https://badge.fury.io/py/desktop-env">
        <img src="https://badge.fury.io/py/desktop-env.svg">
    </a>
    <a href="https://pepy.tech/project/desktop-env">
        <img src="https://static.pepy.tech/badge/desktop-env">
    </a>
    <br/>
</p>
TODO: change this header to OSWorld-G

TODO: add eval bench json?
TODO: requirement for each folder or only one?
TODO: readme for each folder or only one?

## 📢 Updates
- 2025-05-04: This README is online.

## 💾 Environment
First, clone this repository and `cd` into it. Then, install the dependencies listed in `requirements.txt`. It is recommended that you use the latest version of Conda to manage the environment, but you can also choose to manually install the dependencies. Please ensure that the version of Python is >= 3.9.
```bash
# Clone the OSWorld-G(JeDi) repository
git clone https://github.com/xlang-ai/OSWorld-G.git

# Change directory into the cloned repository
cd OSWorld-G

# Optional: Create a Conda environment for OSWorld
# conda create -n osworld-g python=3.9
# conda activate osworld-g

# Install required dependencies
pip install -r requirements.txt
```

## 📊 Benchmark--OSWorld-G

For how to run evaluation, see [Evaluation](#-evaluation) chapter.

## 🗄️ Dataset

### Icon data
TODO: Haoyuan, Tianbao: add instruction on how to run the data preparation.

### Component data

#### Code-and-rendering pipeline
TODO: Junlin: add instruction on how to run the data preparation.

#### Real-world augmentation pipeline
TODO: Tianbao, Xiaochuan, Junlin: add instruction on how to run the data preparation.

### Layout data
TODO: Jiaqi, Tianbao: add instruction on how to run the data preparation.

### Refusal data
TODO: Junlin: add instruction on how to run the data preparation.

## 🔍 Evaluation
TODO: Tianbao, Junlin: add a unified instruction for all evaluations, we have many eval scripts so we may not introduce them one by one.

### Eval OSWorld-G

```bash 
python aguvis_7b_osworld_g.py
```

### Eval ScreenSpot-v2

```bash
export HF_ENDPOINT=https://hf-mirror.com 
huggingface-cli download OS-Copilot/ScreenSpot-v2 --local-dir ./ --repo-type dataset
unzip screenspotv2_image.zip -d ./
python aguvis_7b_screenspot_v2.py
```

## ❓ FAQ
TODO

## 📄 Citation
If you find this environment useful, please consider citing our work:
```
TODO
```