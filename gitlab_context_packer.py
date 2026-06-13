#!/usr/bin/env python3
"""
GitLab Claude Context Packer
A utility to extract Merge Request details and code diffs (locally or from GitLab)
and package them into a structured prompt for Claude (claude.ai).
"""

import argparse
import os
import subprocess
import sys
import urllib.request
import urllib.parse
import json
import re

DEFAULT_OUTPUT = "claude_mr_context.md"

def log(msg, level="INFO"):
    colors = {
        "INFO": "\033[94m[INFO]\033[0m",
        "SUCCESS": "\033[92m[SUCCESS]\033[0m",
        "WARNING": "\033[93m[WARNING]\033[0m",
        "ERROR": "\033[91m[ERROR]\033[0m"
    }
    prefix = colors.get(level, f"[{level}]")
    print(f"{prefix} {msg}")

def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Command '{cmd}' failed: {e.stderr.strip()}")

def get_local_context(target_branch):
    log(f"Packing local changes compared to branch: {target_branch}...", "INFO")
    
    # Verify we are in a Git repo
    try:
        run_command("git rev-parse --is-inside-work-tree")
    except Exception:
        log("Not inside a git repository! Run this script from your git project root.", "ERROR")
        sys.exit(1)
        
    current_branch = run_command("git branch --show-current")
    if not current_branch:
        current_branch = "HEAD (detached)"
        
    # Get the diff (using triple-dot to see changes since feature branch diverged from target)
    try:
        diff_output = run_command(f"git diff {target_branch}...{current_branch}")
        changed_files = run_command(f"git diff --name-only {target_branch}...{current_branch}")
    except Exception as e:
        # Fallback to double-dot diff if triple-dot fails
        log(f"Triple-dot diff failed, attempting double-dot: {e}", "WARNING")
        try:
            diff_output = run_command(f"git diff {target_branch}..{current_branch}")
            changed_files = run_command(f"git diff --name-only {target_branch}..{current_branch}")
        except Exception as e2:
            log(f"Failed to calculate git diff: {e2}", "ERROR")
            sys.exit(1)
            
    if not diff_output.strip():
        log("No changes detected between branches.", "WARNING")
        diff_output = "No changes (diff is empty)."

    files_list = changed_files.splitlines() if changed_files else []
    
    # Construct prompt
    prompt = f"""You are an expert software engineer and code reviewer.
Here is the context for my local code changes. Please review the changes, explain what they accomplish, check for any bugs, security vulnerabilities, or performance issues, and suggest concrete improvements or code edits where appropriate.

======================================================================
METADATA
======================================================================
Current Branch: {current_branch}
Comparing Against: {target_branch}
Changed Files ({len(files_list)}):
{chr(10).join(f'- {f}' for f in files_list)}

======================================================================
CHANGES (DIFF)
======================================================================
```diff
{diff_output}
```
"""
    return prompt

def parse_gitlab_url(mr_url):
    # Match patterns like: https://gitlab.com/group/subgroup/project/-/merge_requests/42
    pattern = r"https?://[^/]+/([^#?]+)/-/merge_requests/(\d+)"
    match = re.search(pattern, mr_url)
    if not match:
        raise ValueError("Invalid GitLab Merge Request URL format.")
    
    project_path = match.group(1).strip("/")
    mr_id = match.group(2)
    return project_path, mr_id

def fetch_gitlab_api(url, token=None):
    req = urllib.request.Request(url)
    if token:
        req.add_header("PRIVATE-TOKEN", token)
    req.add_header("User-Agent", "GitLab-Claude-Context-Packer")
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return response.read()
            else:
                raise RuntimeError(f"GitLab API returned status code {response.status}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP Error {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"URL Connection Error: {e.reason}")

def get_gitlab_mr_context(mr_url, token):
    log("Parsing GitLab MR URL...", "INFO")
    try:
        project_path, mr_id = parse_gitlab_url(mr_url)
    except Exception as e:
        log(f"Failed to parse URL: {e}", "ERROR")
        log("Expected format: https://gitlab.com/group/project/-/merge_requests/12", "INFO")
        sys.exit(1)
        
    encoded_project = urllib.parse.quote_plus(project_path)
    base_url = mr_url.split("/-/merge_requests")[0]
    
    # API endpoints
    mr_api_url = f"https://gitlab.com/api/v4/projects/{encoded_project}/merge_requests/{mr_id}"
    diff_raw_url = f"{mr_url.split('?')[0].split('#')[0]}.diff"
    
    log(f"Fetching MR Details from API...", "INFO")
    try:
        details_data = fetch_gitlab_api(mr_api_url, token)
        details = json.loads(details_data.decode("utf-8"))
    except Exception as e:
        log(f"Could not fetch MR details: {e}", "WARNING")
        details = {
            "title": "Merge Request #" + mr_id,
            "description": "Could not retrieve description.",
            "source_branch": "unknown",
            "target_branch": "unknown"
        }
        
    log("Fetching MR Diff...", "INFO")
    try:
        diff_data = fetch_gitlab_api(diff_raw_url, token)
        diff_output = diff_data.decode("utf-8", errors="replace")
    except Exception as e:
        log(f"Could not fetch MR diff: {e}", "ERROR")
        log("If this is a private project, please supply your GitLab personal token via the --token argument or GITLAB_TOKEN environment variable.", "INFO")
        sys.exit(1)
        
    prompt = f"""You are an expert software engineer and code reviewer.
Here is the context for my GitLab Merge Request. Please review the changes, explain what they accomplish, check for any bugs, security vulnerabilities, or performance issues, and suggest concrete improvements or code edits where appropriate.

======================================================================
MERGE REQUEST METADATA
======================================================================
Title: {details.get('title')}
URL: {mr_url}
Branches: {details.get('source_branch')} ➔ {details.get('target_branch')}

======================================================================
DESCRIPTION
======================================================================
{details.get('description')}

======================================================================
CHANGES (DIFF)
======================================================================
{diff_output}
"""
    return prompt

def main():
    parser = argparse.ArgumentParser(description="Pack GitLab MR context or local changes into a Claude prompt.")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local", action="store_true", help="Pack local git branch changes.")
    group.add_argument("--mr", type=str, help="The GitLab Merge Request URL.")
    
    parser.add_argument("--target", type=str, default="main", help="Target branch to compare against in --local mode (default: main).")
    parser.add_argument("--token", type=str, help="GitLab Personal Access Token (can also be set via GITLAB_TOKEN env var).")
    parser.add_argument("--output", type=str, default=DEFAULT_OUTPUT, help=f"Output markdown filename (default: {DEFAULT_OUTPUT}).")
    
    args = parser.parse_args()
    
    token = args.token or os.environ.get("GITLAB_TOKEN")
    
    try:
        if args.local:
            prompt_content = get_local_context(args.target)
        else:
            prompt_content = get_gitlab_mr_context(args.mr, token)
            
        # Write to file
        output_path = os.path.abspath(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(prompt_content)
            
        log(f"Successfully packaged context to: {output_path}", "SUCCESS")
        log("You can now upload or copy-paste this file into the Claude Web UI (claude.ai)!", "SUCCESS")
        
    except Exception as e:
        log(f"An unexpected error occurred: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
