#!/bin/bash

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "GitHub CLI (gh) is not installed. Please install it first:"
    echo "https://cli.github.com/"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    echo "Please login to GitHub CLI first:"
    echo "gh auth login"
    exit 1
fi

# Check if a commit message was provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 \"Your commit message\""
    exit 1
fi

COMMIT_MESSAGE="$1"
CURRENT_DATE=$(date +%Y%m%d_%H%M%S)
BRANCH_NAME="feluda_pyproject_${CURRENT_DATE}"
MAIN_BRANCH="main"

# Function to check command status
check_status() {
    if [ $? -ne 0 ]; then
        echo "Error: $1"
        exit 1
    fi
}

# Ensure clean working directory
if [[ -n $(git status --porcelain) ]]; then
    echo "Error: Uncommitted changes in the working directory. Commit or stash them before running this script."
    exit 1
fi

# Ensure we're on the main branch and it's up to date
echo "Updating main branch..."
git checkout "$MAIN_BRANCH"
check_status "Failed to checkout main branch"

git pull origin "$MAIN_BRANCH"
check_status "Failed to pull latest changes"

# Create and checkout new branch
echo "Creating new branch: $BRANCH_NAME"
git checkout -b "$BRANCH_NAME"
check_status "Failed to create new branch"

# Append comment to pyproject.toml
echo "Appending comment to pyproject.toml..."
PYPROJECT_FILE="pyproject.toml"
if [[ ! -f $PYPROJECT_FILE ]]; then
    echo "Error: $PYPROJECT_FILE does not exist in the root of the codebase."
    exit 1
fi

UTC_TIME=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
echo -e "\n# Automated comment added at: $UTC_TIME" >> "$PYPROJECT_FILE"

# Stage all changes
echo "Staging changes..."
git add "$PYPROJECT_FILE"
check_status "Failed to stage changes"

# Commit changes
echo "Committing changes..."
git commit -m "$COMMIT_MESSAGE"
check_status "Failed to commit changes"

# Push branch to remote
echo "Pushing branch to remote..."
git push origin "$BRANCH_NAME"
check_status "Failed to push branch"

# Create PR using gh cli
echo "Creating Pull Request..."
PR_URL=$(gh pr create --base "$MAIN_BRANCH" --head "$BRANCH_NAME" --title "$COMMIT_MESSAGE" --body "Automated PR created by script")
check_status "Failed to create PR"

echo "Pull Request created: $PR_URL"

echo "Waiting a few seconds to ensure GitHub processes the PR"
sleep 5

# Merge the PR
echo "Merging Pull Request..."
gh pr merge "$PR_URL" --merge --delete-branch
check_status "Failed to merge PR"

echo "Waiting for the MERGE MAIN action to RUN (35secs)"
sleep 35

# Checkout main branch
echo "Checking out main branch..."
git checkout "$MAIN_BRANCH"
check_status "Failed to checkout main branch"

# Pull latest changes including the merge
echo "Pulling latest changes..."
git fetch --all
git pull origin "$MAIN_BRANCH"
git pull --all

echo "Workflow completed successfully!"
