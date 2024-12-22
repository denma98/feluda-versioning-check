#!/bin/bash

## USAGE
## chmod +x cleanup_releases_tags.sh
## ./cleanup_releases_tags.sh aatmanvaidya/feluda-versioning-check

# Exit on error
set -e

# Check if repository name is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <repository-name>"
    echo "Example: $0 username/repository"
    exit 1
fi

REPO=$1

# Function to delete all releases
delete_releases() {
    # Get all release IDs
    echo "Fetching releases..."
    releases=$(gh api repos/$REPO/releases | jq -r '.[].id')

    if [ -z "$releases" ]; then
        echo "No releases found"
        return
    fi

    # Delete each release
    for release_id in $releases; do
        echo "Deleting release $release_id..."
        gh api -X DELETE repos/$REPO/releases/$release_id
    done

    echo "All releases deleted"
}

# Function to delete all tags
delete_tags() {
    # Get all tags
    echo "Fetching tags..."
    tags=$(git tag -l)

    if [ -z "$tags" ]; then
        echo "No tags found"
        return
    fi

    # Delete each tag locally
    echo "Deleting local tags..."
    git tag -d $tags

    # Delete each tag on remote
    echo "Deleting remote tags..."
    git push origin --delete $tags

    echo "All tags deleted"
}

# Main execution
echo "Starting cleanup for $REPO"

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

# Execute cleanup
delete_releases
delete_tags

echo "Cleanup completed successfully"
