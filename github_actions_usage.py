import requests
import yaml
from tabulate import tabulate
import os
from dotenv import load_dotenv
import argparse
import math

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
    print("Fetching repositories...")
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
    print(f"Found {len(repos)} repositories.")
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

# Get jobs for a workflow run
def get_jobs(owner, repo, run_id):
    jobs = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs?per_page=100&page={page}"
        resp = requests.get(url, headers=HEADERS)
        data = resp.json()
        if "jobs" not in data or not data["jobs"]:
            break
        jobs += data["jobs"]
        page += 1
    return jobs

# Get timing for a workflow run
def get_run_minutes(run):
    timing_url = run["url"] + "/timing"
    timing = requests.get(timing_url, headers=HEADERS).json()
    ms = timing.get("run_duration_ms", 0)
    return ms / 60000

# Main aggregation logic
def main():
    parser = argparse.ArgumentParser(description="GitHub Actions Usage Reporter")
    parser.add_argument("--by-repo", action="store_true", help="Break down usage by repository")
    parser.add_argument("--by-workflow", action="store_true", help="Break down usage by workflow within each repository")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("Set GITHUB_TOKEN env variable.")
        return
    costs = load_costs()
    repos = get_repos()
    summary = {}
    for idx, repo in enumerate(repos, 1):
        owner = repo["owner"]["login"]
        name = repo["name"]
        print(f"[{idx}/{len(repos)}] Processing repo: {owner}/{name} ...")
        runs = get_usage(owner, name)
        for run in runs:
            run_id = run["id"]
            workflow_name = run.get("name", "(unknown workflow)")
            jobs = get_jobs(owner, name, run_id)
            for job in jobs:
                # Detect runner type and OS from job labels
                labels = job.get("labels", [])
                runner_type = "github_hosted"
                os_key = "linux"
                if any("self-hosted" in l for l in labels):
                    runner_type = "self_hosted"
                    os_key = "all"
                elif labels:
                    for l in labels:
                        if l in ("linux", "windows", "macos"):
                            os_key = l
                # Use job duration in minutes, always round up to next minute
                ms = job.get("run_duration_ms")
                if ms is None:
                    # fallback to run duration if job duration is missing
                    minutes = get_run_minutes(run)
                else:
                    minutes = ms / 60000
                minutes = math.ceil(minutes)  # Always round up to next minute
                if args.by_workflow:
                    key = (name, workflow_name, runner_type, os_key)
                elif args.by_repo:
                    key = (name, runner_type, os_key)
                else:
                    key = (runner_type, os_key)
                summary.setdefault(key, 0)
                summary[key] += minutes
    print("\nSummary of GitHub Actions usage:")
    print("Note: GitHub-hosted runner costs reflect actual pricing. Self-hosted runner costs are hypothetical (what you would pay if billed).\n")
    table = []
    if args.by_workflow:
        for (repo, workflow, runner_type, os_key), minutes in summary.items():
            cost_per_min = costs.get(runner_type, {}).get(os_key, 0)
            total_cost = minutes * cost_per_min
            table.append([repo, workflow, runner_type, os_key, round(minutes, 2), f"${total_cost:.2f}"])
        print(tabulate(table, headers=["Repository", "Workflow", "Runner Type", "OS", "Minutes", "Cost"]))
    elif args.by_repo:
        for (repo, runner_type, os_key), minutes in summary.items():
            cost_per_min = costs.get(runner_type, {}).get(os_key, 0)
            total_cost = minutes * cost_per_min
            table.append([repo, runner_type, os_key, round(minutes, 2), f"${total_cost:.2f}"])
        print(tabulate(table, headers=["Repository", "Runner Type", "OS", "Minutes", "Cost"]))
    else:
        for (runner_type, os_key), minutes in summary.items():
            cost_per_min = costs.get(runner_type, {}).get(os_key, 0)
            total_cost = minutes * cost_per_min
            table.append([runner_type, os_key, round(minutes, 2), f"${total_cost:.2f}"])
        print(tabulate(table, headers=["Runner Type", "OS", "Minutes", "Cost"]))

if __name__ == "__main__":
    main()
