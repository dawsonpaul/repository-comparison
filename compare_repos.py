import os
import json
import difflib
from datetime import datetime
from github import Github, GithubException, UnknownObjectException
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

# --- Configuration ---
CONFIG_FILE = 'config.json'
TEMPLATE_FILE = 'template.html'
OUTPUT_FILE = 'repo_comparison_report.html'
ENV_FILE = '.env'  # Optional: For storing GITHUB_TOKEN

# --- Load Environment Variables (Optional but Recommended) ---
load_dotenv(dotenv_path=ENV_FILE)
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
# Replace with your default or get from env
GITHUB_ENTERPRISE_URL = os.getenv(
    'GITHUB_ENTERPRISE_URL', 'https://github.yourcompany.com')

# --- Helper Functions ---


def get_github_instance():
    """Authenticates and returns a PyGithub instance."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN environment variable not set.")
    if GITHUB_ENTERPRISE_URL and GITHUB_ENTERPRISE_URL != 'https://api.github.com':
        print(f"Connecting to GitHub Enterprise: {GITHUB_ENTERPRISE_URL}")
        return Github(base_url=f"{GITHUB_ENTERPRISE_URL}/api/v3", login_or_token=GITHUB_TOKEN)
    else:
        print("Connecting to GitHub.com")
        return Github(GITHUB_TOKEN)


def get_org_repos(g, org_name):
    """Fetches all repository names for a given organization."""
    print(f"Fetching repositories for organization: {org_name}...")
    try:
        org = g.get_organization(org_name)
        repos = {repo.name for repo in org.get_repos()}
        print(f"Found {len(repos)} repositories in {org_name}.")
        return repos, org  # Return org object as well
    except UnknownObjectException:
        print(
            f"Error: Organization '{org_name}' not found or token lacks permissions.")
        return set(), None
    except Exception as e:
        print(f"An error occurred fetching repos for {org_name}: {e}")
        return set(), None


def derive_repo_names(repo_name, is_dev):
    """Derives corresponding prod/dev repo names based on convention."""
    if is_dev:
        # Assuming dev repo is 'dev-repo-name', prod is 'repo-name'
        if repo_name.startswith('dev-'):
            return repo_name[4:]
        else:
            return None  # Cannot derive prod name
    else:
        # Assuming prod repo is 'repo-name', dev is 'dev-repo-name'
        return f"dev-{repo_name}"


def compare_main_branches(dev_repo, prod_repo):
    """Compares the main branches of two repositories."""
    comparison_result = {
        "status": "Comparison Error",
        "dev_main_sha": None,
        "prod_main_sha": None,
        "added_files": [],
        "deleted_files": [],
        "modified_files": [],  # List of {"path": path, "diff": diff_output}
        "error_message": None
    }
    try:
        # --- Get default branch names (often 'main' or 'master') ---
        dev_default_branch_name = dev_repo.default_branch
        prod_default_branch_name = prod_repo.default_branch
        print(
            f"  Comparing branches: {dev_repo.name}/{dev_default_branch_name} vs {prod_repo.name}/{prod_default_branch_name}")

        # --- Get latest commit SHAs ---
        dev_main_commit = dev_repo.get_branch(dev_default_branch_name).commit
        prod_main_commit = prod_repo.get_branch(
            prod_default_branch_name).commit
        comparison_result["dev_main_sha"] = dev_main_commit.sha
        comparison_result["prod_main_sha"] = prod_main_commit.sha

        if dev_main_commit.sha == prod_main_commit.sha:
            comparison_result["status"] = "In Sync"
            print(f"  Branches are in sync (SHA: {dev_main_commit.sha[:7]}).")
            return comparison_result

        comparison_result["status"] = "Differences Found"
        print(
            f"  Branches differ (Dev SHA: {dev_main_commit.sha[:7]}, Prod SHA: {prod_main_commit.sha[:7]}). Fetching file trees for content comparison...")

        # --- Get file trees ---
        dev_tree = {item.path: item for item in dev_repo.get_git_tree(
            dev_main_commit.sha, recursive=True).tree if item.type == 'blob'}
        prod_tree = {item.path: item for item in prod_repo.get_git_tree(
            prod_main_commit.sha, recursive=True).tree if item.type == 'blob'}

        dev_files = set(dev_tree.keys())
        prod_files = set(prod_tree.keys())

        # --- Identify added, deleted, modified files ---
        comparison_result["added_files"] = sorted(list(dev_files - prod_files))
        comparison_result["deleted_files"] = sorted(
            list(prod_files - dev_files))
        common_files = dev_files.intersection(prod_files)

        # --- Compare content of common files ---
        for path in sorted(list(common_files)):
            dev_item = dev_tree[path]
            prod_item = prod_tree[path]

            # Compare SHAs first for efficiency
            if dev_item.sha == prod_item.sha:
                continue  # Files are identical

            try:
                # Fetch content only if SHAs differ
                dev_content_blob = dev_repo.get_git_blob(dev_item.sha)
                prod_content_blob = prod_repo.get_git_blob(prod_item.sha)

                # Decode content (handle potential encoding issues)
                dev_content, prod_content = None, None
                diff_error = None

                # --- Decode Dev Content ---
                dev_content_bytes = None # Initialize
                try:
                    dev_content_raw = dev_content_blob.content
                    if dev_content_blob.encoding == 'base64':
                        dev_content_bytes = dev_content_raw.decode('base64')
                    elif isinstance(dev_content_raw, str): # Already decoded?
                         # If it was already a string, maybe it's okay? Let's try decoding directly first.
                         dev_content = dev_content_raw # Assume it's already decoded string
                    else: # Assume bytes
                        dev_content_bytes = dev_content_raw

                    # If we ended up with bytes, try decoding as UTF-8
                    if isinstance(dev_content_bytes, bytes):
                        dev_content = dev_content_bytes.decode('utf-8')

                except UnicodeDecodeError:
                    diff_error = "Cannot decode dev content as UTF-8 (likely binary)."
                except Exception as e:
                    diff_error = f"Error decoding dev content: {e}"

                # --- Decode Prod Content ---
                prod_content_bytes = None # Initialize to handle potential UnboundLocalError
                try:
                    prod_content_raw = prod_content_blob.content
                    if prod_content_blob.encoding == 'base64':
                        prod_content_bytes = prod_content_raw.decode('base64')
                    elif isinstance(prod_content_raw, str):
                         prod_content = prod_content_raw # Assume it's already decoded string
                    else: # Assume bytes
                        prod_content_bytes = prod_content_raw

                    # If we ended up with bytes, try decoding as UTF-8
                    if isinstance(prod_content_bytes, bytes):
                         prod_content = prod_content_bytes.decode('utf-8')

                except UnicodeDecodeError:
                    error_msg = "Cannot decode prod content as UTF-8 (likely binary)."
                    diff_error = (diff_error + " " + error_msg) if diff_error else error_msg
                except Exception as e:
                    error_msg = f"Error decoding prod content: {e}"
                    diff_error = (diff_error + " " + error_msg) if diff_error else error_msg


                # --- Compare and Generate Diff ---
                diff_output = ""
                # Only proceed if both were successfully decoded to strings
                if isinstance(dev_content, str) and isinstance(prod_content, str):
                    # Explicitly compare decoded content
                    if dev_content == prod_content:
                         continue # Content is identical after decoding, skip

                    # Generate diff if content differs
                    diff = list(difflib.unified_diff(
                        prod_content.splitlines(keepends=True), # Use keepends for accurate diff
                        dev_content.splitlines(keepends=True),
                        fromfile=f"a/{path} (Prod: {prod_item.sha[:7]})",
                        tofile=f"b/{path} (Dev: {dev_item.sha[:7]})",
                        lineterm='' # difflib adds its own newlines
                    ))
                    if diff: # Only join if there are actual diff lines
                        diff_output = "".join(diff)
                    # If no diff generated but content wasn't identical earlier, it implies only metadata/SHA changed
                    # We already continued if content was identical, so if we reach here and diff is empty,
                    # it means something subtle changed (like line endings normalized by git). We'll still report it.
                    # If diff is empty, the template handles it.

                # Add to modified list if diff was generated OR if there was a decoding error
                if diff_output or diff_error:
                    comparison_result["modified_files"].append({
                        "path": path,
                        "diff": diff_output,
                        "error": diff_error
                    })

            except Exception as file_diff_e:
                print(f"    Error comparing file '{path}': {file_diff_e}")
                comparison_result["modified_files"].append({
                    "path": path,
                    "diff": "",
                    "error": f"Error generating diff: {file_diff_e}"
                })

        print(
            f"  Comparison complete: {len(comparison_result['added_files'])} added, {len(comparison_result['deleted_files'])} deleted, {len(comparison_result['modified_files'])} modified.")

    except UnknownObjectException as branch_e:
        error_msg = f"Error accessing default branch: {branch_e}. Does it exist in both repos?"
        print(f"  {error_msg}")
        comparison_result["status"] = "Branch Error"
        comparison_result["error_message"] = error_msg
    except GithubException as gh_e:
        error_msg = f"GitHub API error during comparison: {gh_e}"
        print(f"  {error_msg}")
        comparison_result["status"] = "API Error"
        comparison_result["error_message"] = error_msg
    except Exception as e:
        error_msg = f"Unexpected error during comparison: {e}"
        print(f"  {error_msg}")
        comparison_result["status"] = "Comparison Error"
        comparison_result["error_message"] = error_msg

    return comparison_result

# --- Main Execution ---


def main():
    print("Starting repository comparison script...")
    g = get_github_instance()

    # --- Load Org Pairs from Config ---
    try:
        with open(CONFIG_FILE, 'r') as f:
            org_pairs = json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        return
    except json.JSONDecodeError:
        print(
            f"Error: Configuration file '{CONFIG_FILE}' contains invalid JSON.")
        return
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        return

    all_results = []

    # --- Process Each Org Pair ---
    for pair in org_pairs:
        dev_org_name = pair.get('dev_org')
        prod_org_name = pair.get('prod_org')

        if not dev_org_name or not prod_org_name:
            print(f"Skipping invalid pair in config: {pair}")
            continue

        print(
            f"\n--- Comparing Organizations: {dev_org_name} (Dev) vs {prod_org_name} (Prod) ---")

        pair_result = {
            "dev_org": dev_org_name,
            "prod_org": prod_org_name,
            "dev_only_repos": [],
            "prod_only_repos": [],
            # List of {"dev_repo": name, "prod_repo": name, "comparison": comparison_result}
            "common_repos": [],
            "fetch_error": None
        }

        dev_repos, dev_org_obj = get_org_repos(g, dev_org_name)
        prod_repos, prod_org_obj = get_org_repos(g, prod_org_name)

        if dev_org_obj is None or prod_org_obj is None:
            pair_result[
                "fetch_error"] = f"Could not fetch repositories for one or both organizations ({dev_org_name}, {prod_org_name}). Check names and token permissions."
            all_results.append(pair_result)
            continue  # Skip comparison if we can't get repos

        # --- Identify Dev-Only and Prod-Only Repos ---
        dev_repo_map = {derive_repo_names(
            name, is_dev=True): name for name in dev_repos if derive_repo_names(name, is_dev=True)}
        prod_repo_map = {name: derive_repo_names(
            name, is_dev=False) for name in prod_repos}

        prod_repo_names_in_dev_map = set(dev_repo_map.keys())
        dev_repo_names_in_prod_map = set(prod_repo_map.values())

        pair_result["dev_only_repos"] = sorted(
            [dev_repo_map[prod_name] for prod_name in prod_repo_names_in_dev_map if prod_name not in prod_repos])
        pair_result["prod_only_repos"] = sorted(
            [prod_name for prod_name in prod_repos if prod_name not in prod_repo_names_in_dev_map])

        # --- Compare Common Repos ---
        common_prod_names = prod_repo_names_in_dev_map.intersection(prod_repos)
        print(
            f"Found {len(common_prod_names)} potential common repository pairs.")

        for prod_name in sorted(list(common_prod_names)):
            dev_name = dev_repo_map[prod_name]
            print(
                f"Processing common pair: {dev_name} (Dev) vs {prod_name} (Prod)")
            common_repo_info = {
                "dev_repo_name": dev_name,
                "prod_repo_name": prod_name,
                "comparison": None
            }
            try:
                dev_repo_obj = dev_org_obj.get_repo(dev_name)
                prod_repo_obj = prod_org_obj.get_repo(prod_name)
                common_repo_info["comparison"] = compare_main_branches(
                    dev_repo_obj, prod_repo_obj)
            except UnknownObjectException as repo_e:
                error_msg = f"Error getting repo object: {repo_e}"
                print(f"  {error_msg}")
                common_repo_info["comparison"] = {
                    "status": "Repo Access Error", "error_message": error_msg}
            except Exception as e:
                error_msg = f"Unexpected error processing pair ({dev_name}, {prod_name}): {e}"
                print(f"  {error_msg}")
                common_repo_info["comparison"] = {
                    "status": "Processing Error", "error_message": error_msg}

            pair_result["common_repos"].append(common_repo_info)

        all_results.append(pair_result)
        print(
            f"--- Finished comparison for {dev_org_name} vs {prod_org_name} ---")

    # --- Generate HTML Report ---
    print("\nGenerating HTML report...")
    try:
        jinja_env = Environment(loader=FileSystemLoader(
            '.'), autoescape=True)  # Load templates from current dir
        template = jinja_env.get_template(TEMPLATE_FILE)

        report_data = {
            "generation_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "results": all_results
        }

        html_output = template.render(report_data)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(html_output)
        print(f"Report successfully generated: {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error generating HTML report: {e}")

    print("\nScript finished.")


if __name__ == "__main__":
    # --- Pre-run Checks ---
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        print("Please set it or create a .env file with GITHUB_TOKEN='your_pat_here'.")
        exit(1)
    if GITHUB_ENTERPRISE_URL == 'https://github.yourcompany.com':
        print("Warning: GITHUB_ENTERPRISE_URL is set to the placeholder.")
        print("Ensure it's correctly set in your environment or .env file if using GitHub Enterprise.")

    main()
