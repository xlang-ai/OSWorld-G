# Component rendering

## install node.js and npm
run
```
node -v
npm -v
```
to check whether node.js and npm is installed

if not, run
```
sudo apt update
sudo apt install nodejs npm
```
and check again whether node.js and npm is installed 

## npm install

run `install_npm.sh` in `training_data/component_render`.
Check your disk space--one react frontend requires approximately 600 MB dick space and running them may cost approximately 900 MB memory.

## secret keys
Add a folder named `secret_keys` under `training_data/component_render`.

If you use openai's api:
Add a file named `secret_key_openai.txt` under `training_data/component_render/secret_keys`

If you use claude's bedrock:
- Export AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
- Try to run `python style.py` to see if claude's key work. If it works, it should output a right code of a UI component. 

## environment

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

## Script Run:

First of all, run `run_ubuntu_trial.sh` in `training_data/component_render` on one of your vms, then check 
1. whether folders named by component type(e.g. "autocomplete", "slider") are created in `OSWorld-G/training_data/component_render/data` 
2. whether grounding files are created in `OSWorld-G/training_data/component_render/data/{component_type}/grounding`.

After that, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will check whether the data is correct and fine.

Then, delete the `done_info` folder.

If everything's fine, run `run_ubuntu_all.sh` in `training_data/component_render` on one of your vms, then check
1. whether folders named by component type(e.g. "autocomplete", "slider") are created in `OSWorld-G/training_data/component_render/data` 
2. whether grounding files are created in `OSWorld-G/training_data/component_render/data/{component_type}/grounding`.

Finally, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will do the final processing.
