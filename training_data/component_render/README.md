# Component rendering

We plan to use 6 virtual machines.

## npm install

run `install_npm.sh` in `training_data/component_render`.

## environment

run
```
pip install -r requirements.txt
```
in `training_data/component_render`.

Then run
```
playwright install
```

## Script Run:

First of all, run `run_ubuntu_trial.sh` in `training_data/component_render` on one of your vms, then check 
1. whether folders named by component type(e.g. "autocomplete", "slider") are created in `OSWorld-G/training_data/component_render/data` 
2. whether grounding files are created in `OSWorld-G/training_data/component_render/data/{component_type}/grounding`.

After that, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will check whether the data is correct and fine.

If everything's fine, run `run_ubuntu_all.sh` in `training_data/component_render` on one of your vms, then check
1. whether folders named by component type(e.g. "autocomplete", "slider") are created in `OSWorld-G/training_data/component_render/data` 
2. whether grounding files are created in `OSWorld-G/training_data/component_render/data/{component_type}/grounding`.

Finally, run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will do the final processing.
