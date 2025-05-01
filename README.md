# GitHub Enterprise Repository Comparison Tool

This tool compares repositories between specified pairs of "development" and "production" organizations within a GitHub Enterprise instance (or GitHub.com). It identifies differences in repository existence and compares the content of the default branches (e.g., `main`) for common repositories.

## Features

- Compares multiple pairs of organizations defined in a configuration file.
- Identifies repositories present only in the dev org or only in the prod org based on a `dev-repo-name` / `repo-name` naming convention.
- Compares the latest commit SHAs of the default branch for common repositories.
- If default branches differ, performs a file-level comparison:
  - Lists files added in the dev repository.
  - Lists files deleted from the dev repository (present in prod).
  - Shows content differences (diffs) for modified files.
- Generates a static HTML report (`repo_comparison_report.html`) summarizing the findings.

## Setup

1.  **Clone/Download:** Obtain the tool's files and place them in a directory (e.g., `repository-comparison`).

2.  **Navigate to Directory:** Open your terminal or command prompt and change into the tool's directory:

    ```bash
    cd path/to/repository-comparison
    ```

3.  **Create Virtual Environment (Recommended):** Using a virtual environment prevents conflicts with other Python projects.

    ```bash
    # Create the environment (use python3 or python depending on your system)
    python3 -m venv venv

    # Activate the environment
    # On macOS/Linux:
    source venv/bin/activate
    # On Windows (Command Prompt):
    # venv\Scripts\activate.bat
    # On Windows (PowerShell):
    # venv\Scripts\Activate.ps1
    ```

    You should see `(venv)` prefixed on your terminal prompt.

4.  **Install Dependencies:** Install the required Python libraries.

    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment Variables:** Create a file named `.env` in the `repository-comparison` directory. This file will securely store your GitHub token and Enterprise URL. Add the following lines, replacing the placeholder values:

    ```dotenv
    # .env file content

    # Your GitHub Personal Access Token (PAT)
    # Needs 'repo' scope to read repository data.
    GITHUB_TOKEN='your_personal_access_token_here'

    # Your GitHub Enterprise base URL (e.g., https://github.yourcompany.com)
    # If using GitHub.com, you can omit this line or leave it commented out.
    GITHUB_ENTERPRISE_URL='https://github.yourcompany.com'
    ```

    - **Security:** Ensure the `.env` file is _not_ committed to version control (it's included in the `.gitignore` provided).
    - **PAT Permissions:** Your PAT must have sufficient permissions (typically the `repo` scope) to access the organizations and repositories you intend to compare.

6.  **Configure Organization Pairs:** Edit the `config.json` file. Replace the example pairs with the actual `dev_org` and `prod_org` names you want to compare. Add or remove pairs as needed.
    ```json
    [
      {
        "dev_org": "your-dev-org-1",
        "prod_org": "your-prod-org-1"
      },
      {
        "dev_org": "your-dev-org-2",
        "prod_org": "your-prod-org-2"
      }
      // Add more pairs if needed
    ]
    ```

## Usage

1.  **Ensure Environment is Active:** If you haven't already, activate the virtual environment (`source venv/bin/activate` or equivalent).

2.  **Run the Script:** Execute the Python script from the `repository-comparison` directory:

    ```bash
    python compare_repos.py
    ```

3.  **View Report:** The script will print progress messages to the terminal. Upon completion, it will generate an HTML file named `repo_comparison_report.html` in the same directory. Open this file in your web browser to view the comparison results.

## Updating Your Local Copy

If changes are made to the repository on GitHub after you have cloned it (e.g., updates to the script or template), you can update your local copy by running the following commands from within the `repository-comparison` directory:

```bash
# Ensure you are on the main branch (if you created other branches)
# git checkout main

# Fetch and merge changes from the main branch on GitHub
git pull origin main
```

## How Comparison Works

- **Repository Naming Convention:** The tool assumes a naming convention where a development repository named `dev-some-repo` corresponds to a production repository named `some-repo`. It uses this to match repositories between the dev and prod organizations.
- **Default Branch:** Comparison is performed on the _default branch_ configured for each repository in GitHub (commonly `main` or `master`).
- **Content Diff:** When differences are found between the default branches of common repositories, the script fetches the file trees and compares file content using Python's `difflib` to generate a standard unified diff format.

## Files

- `compare_repos.py`: The main Python script.
- `config.json`: Configuration file for organization pairs.
- `requirements.txt`: Python dependencies.
- `template.html`: Jinja2 template for the HTML report.
- `style.css`: Basic CSS for the report.
- `.env`: (You create this) Stores sensitive credentials (GITHUB_TOKEN, GITHUB_ENTERPRISE_URL).
- `.gitignore`: Specifies files/directories to ignore for Git.
- `README.md`: This file.
- `repo_comparison_report.html`: (Generated by the script) The output report.
- `venv/`: (Created during setup) The Python virtual environment directory.
