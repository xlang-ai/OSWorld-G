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
TODO: test port init



##### install node.js and npm
run
```
node -v
npm -v
```
to check whether node.js and npm is installed

if not, run
<!-- ```
sudo apt update
sudo apt install nodejs npm
``` -->
```
(sudo) apt update
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
source ~/.bashrc
nvm --version
nvm install --lts
```

Make sure the glibc version(if you use ubuntu) is above or equal to 2.28. Otherwise it may be difficult to run node.js and npm well.

and check again whether node.js and npm is installed 

##### npm install

run `install_npm.sh` in `training_data/component_render`.
Check your disk space--one react frontend requires approximately 600 MB dick space and running them may cost approximately 900 MB memory.

##### secret keys
Add a folder named `secret_keys` under `training_data/component_render`.

If you use openai's api:
Add a file named `secret_key_openai.txt` under `training_data/component_render/secret_keys`

If you use claude's bedrock:
- Export AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
- Change `credentials.sh`'s content to your script's content

##### environment

run
```
conda create -n component python=3.9
conda activate component
pip install -r requirements.txt
```
in `training_data/component_render`.

Then run
```
playwright install
```

If you encounter messages like:
...
Host system is missing dependencies to run browsers. ║
║ Please install them with the following command:      ║
║                                                      ║
║     sudo playwright install-deps
...

you can run
```
npm install playwright
npx playwright install-deps
```

Then run
```
xvfb-run --help
```
to check whether xvfb is installed. If not, run
```
sudo apt update
sudo apt install xvfb
```

##### Script Run:

STEP 0: First of all, try to run python style.py to see if claude bedrock works well. If it works, you will see output contains codes of UI component.

###### For Ubuntu

STEP 1: First of all, run `run_ubuntu_trial_claude.sh` in `training_data/component_render` on your computer. After 10mins, run the first python code in `check.ipynb`(#Count). The output will include these two lines:
Total PNG files across all grounding_screenshot folders: ...
Total false PNG files across all grounding_false_screenshot folders: ...

If the Total PNG files across all grounding_screenshot folders is around **4000**, then it is fine. If the number of Total PNG files across all grounding_screenshot is too small, connect Junlin and he'll fix it.

To end all tmux session, you can use:
```bash
tmux kill-server
```

STEP 2: After that, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will check whether the data is correct and fine.

STEP 3: Then, delete the `done_info` folder.[MUST DONE]

STEP 4: If everything's fine, run `run_ubuntu_claude.sh` in `training_data/component_render` on your computer. It takes around 20hrs, so the network of your computer should be stable. You can run the second python code in `check.ipynb`(ProcessCheck) to the the process of the data synthesis. The output should be in this format:
```
Port 3001, 4 out of 529 elements
Port 3002, 3 out of 529 elements
Port 3003, 2 out of 529 elements
Port 3004, 4 out of 529 elements
......
```
529 out of 529 elements means the process is finished. You can also run `ps aux | grep main_bbox.py` to check if the processes are running.

STEP 5: Some base code is problematic, so the process may not be 100% finished. When it's 90-95% finished, you can stop the process, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will do the final processing.

STEP 6: Then, delete the `done_info` folder.[MUST DONE]

STEP 7: Repeat STEP 4, 5, 6.

###### For Mac
STEP 1: First of all, run `run_mac_trial_claude.sh` in `training_data/component_render` on your computer. After 10mins, run the first python code in `check.ipynb`(#Count). The output will include these two lines:
Total PNG files across all grounding_screenshot folders: ...
Total false PNG files across all grounding_false_screenshot folders: ...

If the Total PNG files across all grounding_screenshot folders is around **4000**, then it is fine. If the number of Total PNG files across all grounding_screenshot is too small, connect Junlin and he'll fix it.

STEP 2: After that, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will check whether the data is correct and fine.

STEP 3: Then, delete the `done_info` folder.[MUST DONE]

STEP 4: If everything's fine, run `run_mac_claude.sh` in `training_data/component_render` on your computer. It takes around 20hrs, so the network of your computer should be stable. You can run the second python code in `check.ipynb`(ProcessCheck) to the the process of the data synthesis. The output should be in this format:
```
Port 3001, 4 out of 529 elements
Port 3002, 3 out of 529 elements
Port 3003, 2 out of 529 elements
Port 3004, 4 out of 529 elements
......
```
529 out of 529 elements means the process is finished. You can also run `ps aux | grep main_bbox.py` to check if the processes are running.

STEP 5: Some base code is problematic, so the process may not be 100% finished. When it's 90-95% finished, you can stop the process, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will do the final processing.

STEP 6: Then, delete the `done_info` folder.[MUST DONE]

STEP 7: Repeat STEP 4, 5, 6.

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