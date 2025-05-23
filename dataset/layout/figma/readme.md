## Instructions for Using Figma Extractor

This tool extracts UI elements and images from Figma designs.

**Important**: In order to extract the desired component in each design format. You should mark the needed one as "ready to dev". You will find the feature in the figma interface.

### Required Parameters

Before running the script, you need to set the following parameters in `figma_extract.py`:

1. **access_token**: Your Figma Access Token
   - Get this from your Figma account settings → Personal access tokens
   - Example: `access_token = "figd_X9Xo2-abcdefg-12345"`

2. **file_key**: Your Figma File Key
   - This is the string that appears in your Figma file URL after "file/"
   - Example: `file_key = "abcdefg12345"` (from URL: figma.com/file/abcdefg12345/design)

3. **output_dir**: Your Output Directory
   - The local directory where extracted UI structures and images will be saved
   - Example: `output_dir = "./extracted_designs"`

### Running the Script

After setting these parameters, run the script:

```
python figma_extract.py
```

The script will extract UI structure as JSON files and download associated images to the specified output directory.

## Instructions for Using Systhesis Script