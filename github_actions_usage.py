import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
from tabulate import tabulate
import os
from dotenv import load_dotenv
import argparse
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Load .env if present
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"}

# Create a session with retry logic
def create_session():
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Thread-local storage for sessions
thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = create_session()
    return thread_local.session

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
        resp = tracked_request(url, headers=HEADERS)
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
        resp = tracked_request(f"{url}&page={page}", headers=HEADERS)
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
        resp = tracked_request(url, headers=HEADERS)
        data = resp.json()
        if "jobs" not in data or not data["jobs"]:
            break
        jobs += data["jobs"]
        page += 1
    return jobs

# Get timing for a workflow run
def get_run_minutes(run):
    timing_url = run["url"] + "/timing"
    timing = tracked_request(timing_url, headers=HEADERS).json()
    ms = timing.get("run_duration_ms", 0)
    return ms / 60000

api_call_count = 0
api_call_lock = threading.Lock()

def tracked_request(url, **kwargs):
    global api_call_count
    with api_call_lock:
        api_call_count += 1
    
    session = get_session()
    max_attempts = 3
    
    for attempt in range(max_attempts):
        try:
            resp = session.get(url, **kwargs)
            # Handle rate limiting
            if resp.status_code == 403 and 'X-RateLimit-Remaining' in resp.headers:
                if int(resp.headers['X-RateLimit-Remaining']) == 0:
                    reset_time = int(resp.headers['X-RateLimit-Reset'])
                    sleep_time = max(reset_time - time.time(), 0) + 1
                    print(f"\nRate limit reached. Sleeping for {sleep_time:.0f} seconds...")
                    time.sleep(sleep_time)
                    resp = session.get(url, **kwargs)
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_attempts - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"\nNetwork error, retrying in {wait_time}s... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait_time)
            else:
                raise  # Re-raise after final attempt

# Process a single repository
def process_repo(repo, args):
    owner = repo["owner"]["login"]
    name = repo["name"]
    local_summary = {}
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
            local_summary.setdefault(key, 0)
            local_summary[key] += minutes
    return name, local_summary

# Main aggregation logic
def main():
    start_time = time.time()
    parser = argparse.ArgumentParser(description="GitHub Actions Usage Reporter")
    parser.add_argument("--by-repo", action="store_true", help="Break down usage by repository")
    parser.add_argument("--by-workflow", action="store_true", help="Break down usage by workflow within each repository")
    parser.add_argument("--workers", type=int, default=10, help="Number of parallel workers (default: 10)")
    args = parser.parse_args()

    if not GITHUB_TOKEN:
        print("Set GITHUB_TOKEN env variable.")
        return
    costs = load_costs()
    repos = get_repos()
    summary = {}
    
    print(f"Processing {len(repos)} repositories with {args.workers} parallel workers...")
    completed = 0
    
    # Process repositories in parallel
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_repo = {executor.submit(process_repo, repo, args): repo for repo in repos}
        for future in as_completed(future_to_repo):
            repo = future_to_repo[future]
            completed += 1
            try:
                repo_name, local_summary = future.result()
                # Merge local summary into global summary
                for key, minutes in local_summary.items():
                    summary.setdefault(key, 0)
                    summary[key] += minutes
                print(f"[{completed}/{len(repos)}] Completed: {repo_name}")
            except Exception as e:
                print(f"[{completed}/{len(repos)}] Error processing {repo['name']}: {e}")
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
    elapsed = time.time() - start_time
    print(f"\nRun completed in {elapsed:.1f} seconds. API calls made: {api_call_count}")

if __name__ == "__main__":
    main()
