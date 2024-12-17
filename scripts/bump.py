import os
import re
import sys
import subprocess
import tomli
import tomli_w
import glob


class PackageVersionManager:
    def __init__(self, repo_root, prev_commit, current_commit):
        """
        Initialize the version manager for a monorepo.

        Args:
            repo_root (str): Root directory of the monorepo
            prev_commit (str): Previous commit hash
            current_commit (str): Current commit hash
        """
        self.repo_root = repo_root
        self.prev_commit = prev_commit
        self.current_commit = current_commit
        self.packages = self._discover_packages()

    def _discover_packages(self):
        """
        Discover all packages in the monorepo with their pyproject.toml.

        Returns:
            dict: Mapping of package paths to their current configuration
        """
        packages = {}

        # Root package (feluda)
        package_roots = ["feluda"]

        # Discover packages inside 'operators' directory using glob
        operators_path = "operators"
        if os.path.isdir(operators_path):
            for folder in glob.glob(f"{operators_path}/*/pyproject.toml"):
                package_roots.append(os.path.dirname(folder))

        for package_root in package_roots:
            if package_root == "feluda":
                pyproject_path = os.path.join(self.repo_root, "pyproject.toml")
                full_path = os.path.join(self.repo_root, "feluda")
            else:
                full_path = os.path.join(self.repo_root, package_root)
                pyproject_path = os.path.join(full_path, "pyproject.toml")

            if os.path.exists(pyproject_path):
                with open(pyproject_path, "rb") as f:
                    pyproject_data = tomli.load(f)

                packages[package_root] = {
                    "package_path": full_path,
                    "pyproject_path": pyproject_path,
                    "current_version": pyproject_data["project"].get(
                        "version", "0.0.0"
                    ),
                }
        return packages

    def _parse_conventional_commit(self, commit_message):
        """
        Parse a conventional commit message and determine version bump type.
        This is how Semantic Versioning works

        Returns: 'major', 'minor', 'patch', or None
        """
        # Normalize commit message
        message = commit_message.lower().strip()

        # Check for BREAKING CHANGE
        if "breaking change" in message:
            return "major"

        # Parse commit type
        """
        Regex can detect commits of the type
        <type>: <description>
        <type>(<optional scope>): <description>
        <type>[optional scope]: <description>
        """
        match = re.match(r"^(\w+)(?:\(|\[)?[^\)\]]*(?:\)|\])?:", message)
        print(match)
        if not match:
            return None

        commit_type = match.group(1)

        # Mapping of commit types to version bump
        type_bump_map = {
            "feat": "minor",
            "fix": "patch",
            "chore": "patch",
            "docs": "patch",
            "refactor": "patch",
            "test": "patch",
            "perf": "patch",
            "style": "patch",
            "build": "patch",
            "ci": "patch",
            "revert": "patch",
        }
        # print(type_bump_map.get(commit_type))

        return type_bump_map.get(commit_type)

    def _bump_version(self, current_version, bump_type):
        """
        Bump version based on semantic versioning rules.

        Returns:
            str: New version string
        """
        # Parse current version
        major, minor, patch = map(int, current_version.split("."))

        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        elif bump_type == "patch":
            patch += 1
        else:
            return current_version

        return f"{major}.{minor}.{patch}"

    def get_package_commits(self, package_path):
        """
        Get commits specific to a package between two commit ranges.

        Args:
            package_path (str): Relative path to the package

        Returns:
            list: Commit messages affecting this package
        """
        try:
            # Get commits that modified files in this package between two commits
            cmd = [
                "git",
                "log",
                f"{self.prev_commit}..{self.current_commit}",
                "--pretty=format:%s",
                "--",
                package_path,
            ]

            result = subprocess.run(
                cmd, cwd=self.repo_root, capture_output=True, text=True, check=True
            )

            return result.stdout.splitlines()
        except subprocess.CalledProcessError as e:
            print(f"Error getting commits for {package_path}: {e}")
            return []

    def determine_package_bump(self, package_path):
        """
        Determine the version bump type for a specific package.

        Args:
            package_path (str): Relative path to the package

        Returns:
            str or None: Version bump type
        """
        # Get commits for this package
        package_commits = self.get_package_commits(package_path)

        # If no commits, skip this package
        if not package_commits:
            print(f"No changes found for {package_path}. Skipping version bump.")
            return None

        # Determine highest bump type from commits
        bump_priority = {"major": 3, "minor": 2, "patch": 1, None: 0}
        highest_bump = None

        for commit in package_commits:
            commit_bump = self._parse_conventional_commit(commit)
            if commit_bump and bump_priority.get(commit_bump, 0) > bump_priority.get(
                highest_bump, 0
            ):
                highest_bump = commit_bump

        return highest_bump

    def update_package_versions(self):
        """
        Update versions for packages with changes.

        Returns:
            dict: Mapping of package paths to their new versions
        """
        updated_versions = {}

        for package_path, package_info in self.packages.items():
            # Determine bump type for this package
            bump_type = self.determine_package_bump(package_path)

            # Skip packages with no changes (bump_type is None)
            if not bump_type:
                continue

            # Bump version
            current_version = package_info["current_version"]
            new_version = self._bump_version(current_version, bump_type)

            try:
                # Update pyproject.toml
                with open(package_info["pyproject_path"], "rb") as f:
                    pyproject_data = tomli.load(f)

                pyproject_data["project"]["version"] = new_version

                with open(package_info["pyproject_path"], "wb") as f:
                    tomli_w.dump(pyproject_data, f)

                # Store updated version
                updated_versions[package_path] = {
                    "old_version": current_version,
                    "new_version": new_version,
                    "bump_type": bump_type,
                }

                print(
                    f"Updated {package_path}: {current_version} -> {new_version} ({bump_type} bump)"
                )

            except Exception as e:
                print(f"Failed to update version for {package_path}: {e}")

        return updated_versions


# Main script execution
if __name__ == "__main__":
    # Ensure correct number of arguments
    if len(sys.argv) != 3:
        print("Usage: python semantic_release.py <prev_commit> <current_commit>")
        sys.exit(1)

    # Get repository root (assumes script is run from repo root)
    repo_root = os.getcwd()

    # Get commit range from command line arguments
    prev_commit = sys.argv[1]
    current_commit = sys.argv[2]

    print(repo_root)
    print(prev_commit)
    print(current_commit)

    # Create version manager
    version_manager = PackageVersionManager(repo_root, prev_commit, current_commit)

    # Update package versions
    version_manager.update_package_versions()
