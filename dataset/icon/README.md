# Icon Data Processing

Follow the following steps to generate training data for icons.

## Fetch icon data

### From GitHub repositories

1. Prepare the `all_repos.json` file in the format below. You may refer to the `all_repos.json` file as an example.
```
{
  "repos": {
    "identifier": {
      "name": "author/repo"
    },
    ...
  }
}
```

2. Run `icon_fetcher.py` to save the repos in a local folder.

### From a local folder

Run `icon_fetcher_local.py`. Replace `input_dir` and `output_dir` with appropriate values.

### From the Snap Store

Run `fetch_snap_icons.py`.

## Generate training data

1. (Recommended) Run `cleanup_fetched_icons.py` to remove duplicate icons and libraries that don't contain many icons.
2. Run `generate_appearance_functionality.py` to generate the appearance and functionality description of the icons with GPT-4o. Refer to the first few lines of this script for the appropriate prompt. Remember to set your API key.
3. Run `generate_wallpapers.py` to generate the backgrounds used in the next two steps. We use pure (grayscale) color backgrounds for description data and colored backgrounds for grounding data. There are also frequently used wallpapers manually added to the backgrounds of grounding data.
3. Run `generate_description_data.py` to generate the description data. The response in this type of data is the visual appearance and the functionality of the icon put on a pure color background.
4. Run `generate_grounding_data.py` to generate the grounding data. The response is a PyAutoGUI action to click on the icon put on a colored background among other distractions.

You now have the data files `description_conversations.jsonl` and `grounding_conversations.jsonl` for downstream training.