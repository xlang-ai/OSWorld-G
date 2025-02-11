import os
import shutil

# List of filenames
filenames = [
    "3x9KMOC3hE",
    "3x9KMOC3hE",
    "bC5RG16JsK",
    "bC5RG16JsK",
    "l8sf22rM6n",
    "l8sf22rM6n",
    "hBrUZN5ZUo",
    "nqrmff6e0l",
    "5KLFDjQGy6",
    "5KLFDjQGy6",
    "5KLFDjQGy6",
    "2r2EGLJKi7",
    "2r2EGLJKi7",
    "wFt6OJ7KZU",
    "J7nmwdoXTR",
    "J7nmwdoXTR",
    "NpfPa5jbae",
    "TmPFYxFR9u",
    "l5uw8UNl5Z",
    "624cPrSpKe",
    "aw9QQgeLgs",
    "35h7FwTKtF",
    "eWUE7CwT9p",
    "eWUE7CwT9p",
    "Et7qwxZ9Fq",
    "Cf4yF5Buvk",
    "Cf4yF5Buvk",
    "rf4N7456AI",
    "JAjmL17PpY",
    "JAjmL17PpY"
]

# Create target directory if it doesn't exist
target_dir = "copied_files"
if not os.path.exists(target_dir):
    os.makedirs(target_dir)

# Copy files with .png extension
for filename in filenames:
    source_path = os.path.join('.', filename + '.png')
    target_path = os.path.join(target_dir, filename + '.png')
    
    try:
        if os.path.exists(source_path):
            shutil.copy2(source_path, target_path)
            print(f"Copied: {filename}.png")
        else:
            print(f"Source file not found: {filename}.png")
    except Exception as e:
        print(f"Error copying {filename}.png: {e}")