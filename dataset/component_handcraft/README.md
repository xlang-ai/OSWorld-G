# Component handcraft

This folder contains the code for the real-world augmentation pipeline, including doc, sheet, and slide data.

## Doc data
TODO

## Sheet data
TODO

## Slide data
First of all, create a pptx file in OneDrive and sync it to the local folder.
Then set the `ppt_path` and `url` in `slide_control.py` to the local path and OneDrive url of the pptx file.
``` python
if __name__ == "__main__":
    automation = PPTWebAutomation(
        ppt_path="<path to your pptx file>",
        url="<url of the pptx file>",
        screensize_name=args.screensize_name,
    )
    automation.process_slides()

```
After that, run `slide_control.py` to get the screenshot and bbox data for each slide.
``` bash
python slide_control.py
```

Then, set your OpenAI API key in `action_template.py` and run `action_template.py` to get the action for each slide.
``` bash
python action_template.py
```
