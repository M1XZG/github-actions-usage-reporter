# GitHub Actions Usage Reporter

This project provides a script to check all your owned GitHub repositories (excluding forks), aggregate GitHub Actions minutes used by runner type and OS, and calculate costs based on a configurable rate file. It outputs a summary table for easy analysis.

## Features
- Authenticates with the GitHub API using a Personal Access Token
- Lists all your repositories (excluding forks)
- Aggregates Actions usage by runner type (GitHub-hosted, self-hosted) and OS (Linux, Windows, macOS)
- Reads cost rates from a YAML config file
- Outputs a table with minutes used and total cost per runner/OS

## Setup

1. **Clone this repository**
2. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Create a GitHub Personal Access Token** with `repo` and `actions` scopes.
  - Copy `.env.example` to `.env` and add your token:
    ```bash
    cp .env.example .env
    # Edit .env and set your GITHUB_TOKEN
    ```
  - **Never commit your `.env` file!**
4. **Edit `config.yaml`** to set your cost rates per runner/OS.

## Usage

Run the script:
```bash
python github_actions_usage.py
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
