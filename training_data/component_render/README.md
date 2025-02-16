# Component rendering

We plan to use 6 virtual machines.

## Script Initialize:

We initialize our script in port_init.py.

For vm1-vm3:

Set port_dict as below:

```python
    port_dict = {
        "3000": "alert",
        "3001": "bottom-navigation",
        "3002": "checkboxes",
        "3003": "drawers",
        "3004": "menus",
        "3005": "slider",
        "3006": "table",
        "3007": "tabs",
    }
```

and run port_init.py. You'll get the newest `run_{port}.sh` where port is 3000-3007.

For vm4-vm6:

Set port_dict as below:

```python
    port_dict = {
        "3000": "app-bar",
        "3001": "chips",
        "3002": "dialogs",
        "3003": "lists",
        "3004": "rating",
        "3005": "snackbars speed-dial",
        "3006": "steppers switches",
        "3007": "toggle-button transfer-list",
    }
```

and run port_init.py. You'll get the newest `run_{port}.sh` where port is 3000-3007.

## Script Run:

Run `run_3000.sh` ~ `run_3007.sh` in `training_data/component_render` on each virtual machine. You may need to open 8 tmux sessions to run them in a parrallel way.(Maybe there is other ways that are more efficient?)

Check 
1. whether folders named by component type(e.g. "autocomplete", "slider") are created in `OSWorld-G/training_data/component_render/data` 
2. whether grounding files are created in `OSWorld-G/training_data/component_render/data/{component_type}/grounding`.

They indicate that the grounding data is being generated.

## Data reformat:

Run `final_format.py` in `training_data/component_render` to reformat the data. You'll see a folder named `final_{time}`, this is the desired folder. Send the folder in each vm to Junlin, he will do the final processing.
