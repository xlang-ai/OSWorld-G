# Component rendering

## Component and action description generation
Run `python desc_gen.py` to generate the component and action descriptions. Descriptions are saved in `component_action_list.json`.

## Component code generation
Run `python render.py` to generate the component code and action code. 

You can observe components in `localhost:3000`.

Screenshot of components, components with bbox, components with action annotation can be found in `/screenshot`

Full information of a component-action pair can be found in `data.jsonl`.

## Fonts and Styles:

Go to `training_data/component_render/react-app` and run `npm install` to install the dependencies.

## Possible Types:
slider menus drawers checkboxes rating

bottom-navigation pagination table selectable-text resizable-draggable-text-box

chips lists alert dialogs snackbars app-bar


transfer-list
toggle-buttons
switch
speed-dial
stepper
tabs
