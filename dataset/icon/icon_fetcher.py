import json
import os
import requests
from typing import Dict, List
import base64
from pathlib import Path
import git
import shutil
import glob

class IconFetcher:
    def __init__(self, github_token: str, output_dir: str):
        """
        Initialize the IconFetcher with GitHub API token
        
        Args:
            github_token (str): GitHub personal access token
            output_dir (str): Base directory for downloaded icons
        """
        self.github_token = github_token
        self.output_dir = Path(output_dir)
        self.icons_data_file = self.output_dir / "icons_data.json"
        self.icons_data = self._load_icons_data()
        self.repos_dir = Path("repos")  # Now at the same level as downloaded_icons
        self.repos_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_icons_data(self) -> Dict:
        """Load the icons data from file if it exists"""
        if self.icons_data_file.exists():
            with open(self.icons_data_file, 'r') as f:
                return json.load(f)
        return {"repositories": {}}
    
    def _save_icons_data(self):
        """Save the icons data to file"""
        with open(self.icons_data_file, 'w') as f:
            json.dump(self.icons_data, f, indent=2)

    def is_image_file(self, filename: str) -> bool:
        """Check if a file is an image based on extension"""
        image_extensions = {'.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico'}
        return any(filename.lower().endswith(ext) for ext in image_extensions)

    def clone_or_pull_repo(self, repo_name: str) -> Path:
        """
        Clone a repository or pull latest changes if already cloned
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            
        Returns:
            Path: Path to the cloned repository
        """
        repo_dir = self.repos_dir / repo_name.replace('/', '_')
        repo_url = f"https://{self.github_token}@github.com/{repo_name}.git"
        
        try:
            if repo_dir.exists():
                # Pull latest changes if repo exists
                repo = git.Repo(repo_dir)
                origin = repo.remotes.origin
                origin.pull()
                print(f"Pulled latest changes for {repo_name}")
            else:
                # Clone new repository
                git.Repo.clone_from(repo_url, repo_dir)
                print(f"Cloned {repo_name}")
            return repo_dir
        except Exception as e:
            print(f"Error with repository {repo_name}: {str(e)}")
            return None

    def get_repo_hash(self, repo_dir: Path) -> str:
        """Get the current commit hash of the repository"""
        repo = git.Repo(repo_dir)
        return repo.head.commit.hexsha

    def fetch_icons_from_repo(self, repo_name: str) -> List[str]:
        """
        Fetch all icon files from a repository
        
        Args:
            repo_name (str): Repository name in format 'owner/repo'
            
        Returns:
            List[str]: List of successfully copied icon paths
        """
        downloaded_paths = []
        
        # Clone or update repository
        repo_dir = self.clone_or_pull_repo(repo_name)
        if not repo_dir:
            return downloaded_paths

        # Get repository hash
        repo_hash = self.get_repo_hash(repo_dir)
        
        # Initialize repository data if not exists
        if repo_name not in self.icons_data["repositories"]:
            self.icons_data["repositories"][repo_name] = {
                "icons": {},
                "last_hash": None
            }
        
        repo_data = self.icons_data["repositories"][repo_name]
        
        # If repo hasn't changed and all files exist, return cached paths
        if repo_data["last_hash"] == repo_hash:
            all_files_exist = True
            for icon_info in repo_data["icons"].values():
                if not Path(icon_info["local_path"]).exists():
                    all_files_exist = False
                    break
            if all_files_exist:
                print(f"Using cached icons for {repo_name}")
                return [info["local_path"] for info in repo_data["icons"].values()]
        
        # Find all image files in the repository
        for img_path in repo_dir.rglob("*"):
            if img_path.is_file() and self.is_image_file(img_path.name):
                relative_path = str(img_path.relative_to(repo_dir))
                save_path = self.output_dir / repo_name / relative_path
                
                # Create directory if it doesn't exist
                save_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file to output directory
                shutil.copy2(img_path, save_path)
                downloaded_paths.append(str(save_path))
                
                # Update icons data
                repo_data["icons"][relative_path] = {
                    "local_path": str(save_path),
                    "last_updated": str(save_path.stat().st_mtime)
                }
                print(f"Copied: {relative_path}")
        
        # Update repository hash
        repo_data["last_hash"] = repo_hash
        self._save_icons_data()
        
        return downloaded_paths

def main():
    # Load GitHub token from environment variable
    github_token = os.getenv('GITHUB_TOKEN')
    if not github_token:
        raise ValueError("Please set GITHUB_TOKEN environment variable")

    # Load repositories from JSON file
    with open('all_repos.json', 'r') as f:
        repos_data = json.load(f)

    # Create output directory for icons (separate from repos)
    output_dir = "downloaded_icons"
    os.makedirs(output_dir, exist_ok=True)

    # Create icon fetcher instance
    fetcher = IconFetcher(github_token, output_dir)

    # Process each repository
    for repo_info in repos_data['repos'].values():
        repo_name = repo_info['name']
        print(f"\nProcessing repository: {repo_name}")
        fetcher.fetch_icons_from_repo(repo_name)

    print(f"\nIcons data saved to: {fetcher.icons_data_file}")

if __name__ == "__main__":
    main()