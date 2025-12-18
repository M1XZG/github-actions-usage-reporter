import requests
import yaml
from tabulate import tabulate
import os
from dotenv import load_dotenv


# Load .env if present
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Load config
def load_costs():
    with open("config.yaml") as f:
        return yaml.safe_load(f)

# Get all owned repos (not forks)
def get_repos():
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/user/repos?per_page=100&page={page}&type=owner"
        resp = requests.get(url, headers=HEADERS)
        data = resp.json()
        if not data:
            break
        repos += [r for r in data if not r["fork"]]
        page += 1
    return repos

# Get workflow usage for a repo
def get_usage(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=100"
    runs = []
    page = 1
    while True:
        resp = requests.get(f"{url}&page={page}", headers=HEADERS)
        data = resp.json()
        if "workflow_runs" not in data or not data["workflow_runs"]:
            break
        runs += data["workflow_runs"]
        page += 1
    return runs

# Get timing for a workflow run
def get_run_minutes(run):
    timing_url = run["url"] + "/timing"
    timing = requests.get(timing_url, headers=HEADERS).json()
    ms = timing.get("run_duration_ms", 0)
    return ms / 60000

# Main aggregation logic
def main():
    if not GITHUB_TOKEN:
        print("Set GITHUB_TOKEN env variable.")
        return
    costs = load_costs()
    repos = get_repos()
    summary = {}
    for repo in repos:
        owner = repo["owner"]["login"]
        name = repo["name"]
        runs = get_usage(owner, name)
        for run in runs:
            # Default to github_hosted/linux if unknown
            runner_type = "github_hosted"
            os_key = "linux"
            labels = run.get("labels", [])
            if any("self-hosted" in l for l in labels):
                runner_type = "self_hosted"
                os_key = "all"
            elif labels:
                for l in labels:
                    if l in ("linux", "windows", "macos"):
                        os_key = l
            minutes = get_run_minutes(run)
            key = (runner_type, os_key)
            summary.setdefault(key, 0)
            summary[key] += minutes
    table = []
    for (runner_type, os_key), minutes in summary.items():
        cost_per_min = costs.get(runner_type, {}).get(os_key, 0)
        total_cost = minutes * cost_per_min
        table.append([runner_type, os_key, round(minutes, 2), f"${total_cost:.2f}"])
    print(tabulate(table, headers=["Runner Type", "OS", "Minutes", "Cost"]))

if __name__ == "__main__":
    main()
