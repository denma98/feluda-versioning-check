import os
import subprocess
import shutil
import stat
import pytest
import tomlkit
from semantic_release_workflow import PackageVersionManager

# Constants
TEST_REPO = "test_repo"
PYPROJECT_TOML = """
[project]
name = "test_package"
version = "1.0.0"

[tool.semantic_release.branches.main]
tag_format = "v{version}"
"""


def remove_readonly(func, path, _):
    """
    Remove readonly attribute from a file and retry the operation.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


@pytest.fixture(scope="function")
def setup_test_repo():
    """
    Fixture to set up a test Git repository with a dummy package.
    """
    # Store the original working directory
    original_dir = os.getcwd()

    # Create a test repository
    test_repo_path = os.path.abspath(TEST_REPO)  # Use absolute path
    if os.path.exists(test_repo_path):
        shutil.rmtree(test_repo_path, onerror=remove_readonly)
    os.makedirs(test_repo_path)
    os.chdir(test_repo_path)

    # Initialize Git repository
    subprocess.run(["git", "init"], check=True)

    # Create a dummy package with pyproject.toml
    os.makedirs("test_package")
    with open("test_package/pyproject.toml", "w") as f:
        f.write(PYPROJECT_TOML)

    # Add and commit the initial version
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], check=True)

    yield test_repo_path  # Return absolute path

    # Clean up after tests
    os.chdir(original_dir)
    shutil.rmtree(test_repo_path, onerror=remove_readonly)


def test_no_changes(setup_test_repo):
    """
    Test that no version bump occurs when there are no changes.
    """
    # Get the current commit hash
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    current_commit = result.stdout.strip()

    # Initialize PackageVersionManager
    version_manager = PackageVersionManager(setup_test_repo, current_commit, current_commit)

    # Check for version updates
    updated_versions = version_manager.update_package_versions()

    # Assert no version updates
    assert not updated_versions, "No version updates should occur when there are no changes."


def test_patch_bump(setup_test_repo):
    """
    Test that a patch bump occurs for a fix commit.
    """
    # Make a fix commit
    fix_file_path = os.path.join(setup_test_repo, "test_package", "fix.txt")  # Use absolute path
    with open(fix_file_path, "w") as f:
        f.write("Fix a bug")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "fix: fix a bug"], check=True)

    # Get the previous and current commit hashes
    result = subprocess.run(["git", "rev-parse", "HEAD^"], capture_output=True, text=True, check=True)
    prev_commit = result.stdout.strip()
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    current_commit = result.stdout.strip()

    # Initialize PackageVersionManager
    version_manager = PackageVersionManager(setup_test_repo, prev_commit, current_commit)

    # Check for version updates
    updated_versions = version_manager.update_package_versions()

    # Assert patch bump
    assert updated_versions, "A patch bump should occur for a fix commit."
    assert updated_versions["test_package"]["new_version"] == "1.0.1", "Version should be bumped to 1.0.1."


def test_minor_bump(setup_test_repo):
    """
    Test that a minor bump occurs for a feat commit.
    """
    # Make a feat commit
    feat_file_path = os.path.join(setup_test_repo, "test_package", "feat.txt")  # Use absolute path
    with open(feat_file_path, "w") as f:
        f.write("Add a new feature")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "feat: add a new feature"], check=True)

    # Get the previous and current commit hashes
    result = subprocess.run(["git", "rev-parse", "HEAD^"], capture_output=True, text=True, check=True)
    prev_commit = result.stdout.strip()
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    current_commit = result.stdout.strip()

    # Initialize PackageVersionManager
    version_manager = PackageVersionManager(setup_test_repo, prev_commit, current_commit)

    # Check for version updates
    updated_versions = version_manager.update_package_versions()

    # Assert minor bump
    assert updated_versions, "A minor bump should occur for a feat commit."
    assert updated_versions["test_package"]["new_version"] == "1.1.0", "Version should be bumped to 1.1.0."


def test_major_bump(setup_test_repo):
    """
    Test that a major bump occurs for a breaking change.
    """
    # Make a breaking change commit
    breaking_file_path = os.path.join(setup_test_repo, "test_package", "breaking.txt")  # Use absolute path
    with open(breaking_file_path, "w") as f:
        f.write("BREAKING CHANGE: major change")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "feat: major change\n\nBREAKING CHANGE: major change"], check=True)

    # Get the previous and current commit hashes
    result = subprocess.run(["git", "rev-parse", "HEAD^"], capture_output=True, text=True, check=True)
    prev_commit = result.stdout.strip()
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    current_commit = result.stdout.strip()

    # Initialize PackageVersionManager
    version_manager = PackageVersionManager(setup_test_repo, prev_commit, current_commit)

    # Check for version updates
    updated_versions = version_manager.update_package_versions()

    # Assert major bump
    assert updated_versions, "A major bump should occur for a breaking change."
    assert updated_versions["test_package"]["new_version"] == "2.0.0", "Version should be bumped to 2.0.0."


def test_tag_already_exists(setup_test_repo):
    """
    Test that version bumping is skipped if the tag already exists.
    """
    # Get initial version from pyproject.toml
    with open(os.path.join(setup_test_repo, "test_package", "pyproject.toml"), "r") as f:
        pyproject_data = tomlkit.parse(f.read())
    initial_version = pyproject_data["project"]["version"]

    # Make a fix commit to trigger patch bump
    fix_file_path = os.path.join(setup_test_repo, "test_package", "fix.txt")
    with open(fix_file_path, "w") as f:
        f.write("Fix a bug")
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "fix: fix a bug"], check=True)

    # Get commit hashes
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    current_commit = result.stdout.strip()
    result = subprocess.run(["git", "rev-parse", "HEAD^"], capture_output=True, text=True, check=True)
    prev_commit = result.stdout.strip()

    # Calculate expected version
    major, minor, patch = map(int, initial_version.split("."))
    expected_version = f"{major}.{minor}.{patch + 1}"

    # Create tag for expected version
    subprocess.run(["git", "tag", f"v{expected_version}"], check=True)

    # Run version manager
    version_manager = PackageVersionManager(setup_test_repo, prev_commit, current_commit)
    updated_versions = version_manager.update_package_versions()

    # Verify no version bump occurred
    assert not updated_versions, "Version bump should be skipped when tag exists"

if __name__ == "__main__":
    pytest.main()
