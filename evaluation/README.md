# Evaluation

We provide evaluation scripts for Jedi on Screenspot-v2, Screenspot-pro, and OSWorld-G.

## Jedi on Screenspot-v2
Fetch the benchmark dataset from [here](https://huggingface.co/datasets/OS-Copilot/ScreenSpot-v2/tree/main).
Run the following command to evaluate on Screenspot-v2:
```bash
python qwen25_vllm_screenspot_v2.py --annotation_path <path_to_annotation(json file)> --model_path <path_to_model> --image_dir <path_to_image_dir>
```

## Jedi on Screenspot-pro
Fetch the benchmark dataset from [here](https://huggingface.co/datasets/likaixin/ScreenSpot-Pro).
Run the following command to evaluate on Screenspot-pro:
```bash
python qwen25_vllm_screenspot_pro.py --annotation_path <path_to_annotation(folder containing json files)> --model_path <path_to_model> --image_dir <path_to_image_dir>
```

## Jedi on OSWorld-G
Run the following command to evaluate on OSWorld-G:
```bash
python qwen25_vllm_osworld_g.py --annotation_path <path_to_annotation(json file)> --model_path <path_to_model> --image_dir <path_to_image_dir>
```

## Other open source models on OSWorld-G
You can modify our script to test other open-source models on these benchmark datasets. An example is provided in `qwen2_vllm_osworld_g_aguvis.py`.

Run the following command to evaluate on OSWorld-G using Aguvis:
```bash
python qwen2_vllm_osworld_g_aguvis.py --annotation_path <path_to_annotation> --model_path <path_to_model> --image_dir <path_to_image_dir>
```

## Other closed source models on OSWorld-G
You can also evaluate other closed-source models on OSWorld-G. An example with Operator is provided in `operator_osworld_g.py`.

Run the following command to evaluate on OSWorld-G using Operator:
```bash
python operator_osworld_g.py --annotation_path <path_to_annotation> --model_name <path_to_model> --image_dir <path_to_image_dir>
```