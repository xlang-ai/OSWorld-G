# Evaluation guidelines

## Eval OSWorld-G

```bash 
python aguvis_7b_osworld_g.py
```

## Eval ScreenSpot-v2

```bash
export HF_ENDPOINT=https://hf-mirror.com 
huggingface-cli download OS-Copilot/ScreenSpot-v2 --local-dir ./ --repo-type dataset
unzip screenspotv2_image.zip -d ./
python aguvis_7b_screenspot_v2.py
```

