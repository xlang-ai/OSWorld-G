import json
import os

from tqdm import tqdm


def convert_jsonl_files(input_paths, output_path):
    """
    Convert multiple JSONL files into a single consolidated JSONL file with the specified format.

    Args:
        input_paths (list): List of paths to input JSONL files
        output_path (str): Path where the output JSONL file will be saved
    """
    processed_count = 0

    # Open the output file in write mode
    with open(output_path, "w", encoding="utf-8") as out_f:
        # Process each input file with progress bar
        for input_path in tqdm(input_paths, desc="Processing files"):
            with open(input_path, "r", encoding="utf-8") as in_f:
                # Count lines in the file for the progress bar
                lines = list(in_f)
                in_f.seek(0)

                # Process each line with progress bar
                for line in tqdm(
                    lines,
                    desc=f"Processing {os.path.basename(input_path)}",
                    leave=False,
                ):
                    try:
                        # Parse each line as JSON
                        data = json.loads(line.strip())

                        # Create the new data structure
                        new_entry = {
                            "image": os.path.join(
                                "component_grounding/doc/",
                                os.path.basename(data["image"]),
                            ),
                            "conversations": [
                                {
                                    "from": "system",
                                    "value": "You are a GUI assistant that helps users interact GUI elements. You should return PyAutoGUI code that satisfies the user's instructions.",
                                },
                                {
                                    "from": "human",
                                    "value": "<image>\n" + data["instruction"],
                                },
                                {
                                    "from": "gpt",
                                    "value": data["code"],
                                    "recipient": "all",
                                    "end_turn": True,
                                },
                            ],
                        }

                        # Write the new entry as a line in the output JSONL file
                        json.dump(new_entry, out_f, ensure_ascii=False)
                        out_f.write("\n")

                        processed_count += 1

                    except json.JSONDecodeError as e:
                        print(f"Error parsing line in {input_path}: {e}")
                    except KeyError as e:
                        print(f"Missing required key in {input_path}: {e}")

    print(f"Successfully processed {processed_count} entries")
    print(f"Output saved to: {output_path}")


# Example usage:
if __name__ == "__main__":
    input_files = [
        "./select_range/select_range_text/data.jsonl",
        "./chars_space/doc_char_spaces/data.jsonl",
        "./chars/doc_chars/data.jsonl",
    ]
    output_file = "./doc_data.jsonl"

    convert_jsonl_files(input_files, output_file)
