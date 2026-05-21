import os
import json
import requests
from datetime import datetime

# Setup GitHub headers using system secret token
TOKEN = os.getenv("NAZR_GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}"} if TOKEN else {}

def fetch_workflow_runs(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("workflow_runs", [])
    print(f"⚠️ Error fetching {repo}: {response.status_code}")
    return []

def main():
    # Load monitored ecosystem list
    with open("registry.json", "r") as f:
        registry = json.load(f)
        
    updated_projects = []

    for repo_url in registry.get("repositories", []):
        # Extract owner and repo name from URL
        parts = repo_url.strip("/").split("/")
        owner, repo_name = parts[-2], parts[-1]
        
        print(f"🚀 Processing telemetry for {repo_name}...")
        runs = fetch_workflow_runs(owner, repo_name)
        if not runs:
            continue
            
        # Parse metrics out of the API response
        fresh_data = []
        for run in runs:
            start = datetime.strptime(run["run_started_at"], "%Y-%m-%dT%H:%M:%SZ")
            end = datetime.strptime(run["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
            duration = int((end - start).total_seconds())
            
            fresh_data.append({
                "run_id": run["id"],
                "status": run["status"],
                "conclusion": run["conclusion"],
                "started_at": run["run_started_at"],
                "updated_at": run["updated_at"],
                "duration_seconds": duration,
                "trigger_event": run["event"],
                "html_url": run["html_url"]
            })
            
        # Ensure targeted storage paths exist
        project_dir = f"REPOS/{repo_name}"
        os.makedirs(project_dir, exist_ok=True)
        file_path = f"{project_dir}/actions.json"
        
        # Merge with existing history to maintain continuous database tracking
        existing_data = []
        if os.path.exists(file_path):
            with open(file_path, "r") as hf:
                try:
                    existing_data = json.load(hf)
                except json.JSONDecodeError:
                    pass
                    
        # Deduplicate using run_id
        known_ids = {entry["run_id"] for entry in existing_data}
        new_entries = [d for d in fresh_data if d["run_id"] not in known_ids]
        
        if new_entries:
            combined_data = new_entries + existing_data
            # Keep records clean, sorted from latest to oldest
            combined_data.sort(key=lambda x: x["updated_at"], reverse=True)
            
            with open(file_path, "w") as wf:
                json.dump(combined_data, wf, indent=2)
                
            updated_projects.append(repo_name)
            print(f"✅ Saved {len(new_entries)} new metrics for {repo_name}.")
        else:
            print(f"💤 No new runs discovered for {repo_name}.")

    # Output modified elements for shell tracking inside workflow
    with open("updates.txt", "w") as uf:
        uf.write(",".join(updated_projects))

if __name__ == "__main__":
    main()
