# GitHub Actions Usage Reporter

**Why this exists:**

This tool was created to help users estimate how much they might spend on GitHub Actions, especially in light of the proposed charges for self-hosted runners announced by GitHub in December 2025 ([announcement](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/)).

After a vast public outcry, GitHub has since backed down from this plan (for now at least). See the community discussion and reversal here: [GitHub Community Discussion](https://github.com/orgs/community/discussions/182186).

It remains useful for understanding your usage and potential costs should such changes be reconsidered in the future.

This project provides a script to check all your owned GitHub repositories (excluding forks), aggregate GitHub Actions minutes used by runner type and OS, and calculate costs based on a configurable rate file. It outputs a summary table for easy analysis.

## Features
- Authenticates with the GitHub API using a Personal Access Token
- Lists all your repositories (excluding forks)
- Aggregates Actions usage by runner type (GitHub-hosted, self-hosted) and OS (Linux, Windows, macOS)
- Reads cost rates from a YAML config file
- Outputs a table with minutes used and total cost per runner/OS

## Setup

1. **Clone this repository**
2. **Create a virtual environment and activate it:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a GitHub Personal Access Token** with `repo` and `actions` scopes.
   - Copy `.env.example` to `.env` and add your token:
     ```bash
     cp .env.example .env
     # Edit .env and set your GITHUB_TOKEN
     ```
   - **Never commit your `.env` file!**
5. **Edit `config.yaml`** to set your cost rates per runner/OS.

## Usage

Run the script:
```bash
python github_actions_usage.py
```

Optional command line options:
- `--by-repo` — Break down usage by repository
- `--by-workflow` — Break down usage by workflow within each repository
- `--workers N` — Number of parallel workers for faster processing (default: 10)

Examples:
```bash
python github_actions_usage.py --by-repo
python github_actions_usage.py --by-workflow
python github_actions_usage.py --workers 20  # Use 20 parallel workers for faster execution
```

## Configuration

Edit `config.yaml` to set your cost per minute for each runner type and OS. Example:

```yaml
github_hosted:
  linux: 0.008
  windows: 0.016
  macos: 0.08
self_hosted:
  all: 0.002
```

## Output Example

| Runner Type    | OS      | Minutes | Cost   |
|---------------|---------|---------|--------|
| github_hosted | linux   | 123.45  | $0.99  |
| self_hosted   | all     | 50.00   | $0.10  |

## License
MIT
