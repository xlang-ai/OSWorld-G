from huggingface_hub import HfApi, login
import os

def upload_to_dataset(token: str, repo_id: str, local_path: str, repo_path: str = None):
    """
    Upload files to Hugging Face dataset repository
    
    Args:
        token (str): Your Hugging Face API token
        repo_id (str): Repository ID in format "username/repo_name"
        local_path (str): Local file or directory path to upload
        repo_path (str, optional): Target path in repo. Defaults to filename
    
    Returns:
        str: URL of the uploaded file
    """
    try:
        # Login with token
        login(token=token)
        api = HfApi()
        
        # If repo_path not specified, use filename
        if repo_path is None:
            repo_path = os.path.basename(local_path)
            
        # Upload file or directory
        if os.path.isfile(local_path):
            url = api.upload_file(
                path_or_fileobj=local_path,
                path_in_repo=repo_path,
                repo_id=repo_id,
                repo_type="dataset"  # 明确指定为 dataset 类型
            )
            print(f"Successfully uploaded file {local_path} to {url}")
        else:
            url = api.upload_folder(
                folder_path=local_path,
                path_in_repo=repo_path,
                repo_id=repo_id,
                repo_type="dataset"  # 明确指定为 dataset 类型
            )
            print(f"Successfully uploaded folder {local_path} to {url}")
            
        return url
        
    except Exception as e:
        print(f"Error uploading to Hugging Face: {str(e)}")
        raise

# Example usage
if __name__ == "__main__":
    # 替换为你的实际值
    TOKEN = "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"  # 从 https://huggingface.co/settings/tokens 获取
    REPO_ID = "tianbaoxiexxx/layout"  # 你的数据集仓库 ID
    
    # 上传分割后的文件
    files = [
        "./figma500k/figma400k.zip"
    ]
    
    for file_path in files:
        # 可以指定上传后的文件名
        repo_path = os.path.basename(file_path)  # 或者自定义其他名称
        upload_to_dataset(TOKEN, REPO_ID, file_path, repo_path)