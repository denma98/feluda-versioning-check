import glob
import os
import re
import subprocess
import sys
import tomlkit
# import tomli
# import tomli_w


class PackageVersionManager:
    def __init__(self, repo_root, prev_commit, current_commit):
        """
        Initialize the version manager for a monorepo.

        Args:
            repo_root (str): Root directory of the monorepo
            prev_commit (str): Previous commit hash
            current_commit (str): Current commit hash

        Raises:
            FileNotFoundError: If the repo_root is invalid or inaccessible.
        """
        if not os.path.exists(repo_root):
            raise FileNotFoundError(f"Repository root '{repo_root}' does not exist.")

        self.repo_root = repo_root
        self.prev_commit = prev_commit
        self.current_commit = current_commit
        self.packages = self._discover_packages()

    def _discover_packages(self):
        """
        Discover all packages in the monorepo, including the root package (feluda).
        """
        packages = {}
        for pyproject_path in glob.glob(f"{self.repo_root}/**/pyproject.toml", recursive=True):
            try:
                package_root = os.path.dirname(pyproject_path)

                # Skip subpackages that are not direct children of the root
                # (Adjust this based on your monorepo structure)
                if "operators/" in pyproject_path and package_root != self.repo_root:
                    continue

                with open(pyproject_path, "r") as f:
                    pyproject_data = tomlkit.parse(f.read())

                # Validate required fields
                name = pyproject_data["project"]["name"]
                version = pyproject_data["project"]["version"]
                tag_format = (
                    pyproject_data.get("tool", {})
                    .get("semantic_release", {})
                    .get("branches", {})
                    .get("main", {})
                    .get("tag_format")
                )
                if not all([name, version, tag_format]):
                    raise ValueError(f"Invalid pyproject.toml at {pyproject_path}")

                packages[name] = {
                    "package_path": package_root,
                    "pyproject_path": pyproject_path,
                    "current_version": version,
                    "pyproject_data": pyproject_data,
                }
            except Exception as e:
                print(f"Skipping invalid package: {e}")
                continue

        if not packages:
            raise FileNotFoundError("No valid packages found")
        return packages

    def _parse_conventional_commit(self, commit_message):
        """
        Parse a conventional commit message and determine version bump type.
        """
        try:
            message = commit_message.strip().lower()

            # Check for breaking changes anywhere in the message
            if "breaking change" in message:
                return "major"

            # Extract commit type from the first line
            first_line = message.split("\n")[0]
            match = re.match(r"^(\w+)(?:\(|\[)?[^\)\]]*(?:\)|\])?:", first_line)
            if not match:
                return "patch" if message else None

            commit_type = match.group(1).lower()
            type_bump_map = {
                "feat": "minor",
                "fix": "patch",
                # Default other types to patch
            }
            return type_bump_map.get(commit_type, "patch")
        except Exception as e:
            print(f"Error parsing commit message: {e}")
            return None

    def _bump_version(self, current_version, bump_type):
        """
        Bump version based on semantic versioning rules.

        Args:
            current_version (str): Current version string in the format 'x.y.z'.
            bump_type (str): Type of version bump ('major', 'minor', 'patch').

        Returns:
            str: New version string.

        Raises:
            ValueError: If the current_version format is invalid.

        Happy Path:
            Current version is valid, and a valid bump type is provided.
        Failure Path:
            Current version is not in 'x.y.z' format or bump_type is invalid.
        """
        try:
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
        except ValueError:
            print(f"Invalid version format: {current_version}")
            raise

    def get_package_commits(self, package_path):
        """
        Get commits specific to a package between two commit ranges.
        """
        try:
            # Handle initial commit (no parent)
            try:
                subprocess.run(
                    ["git", "rev-parse", f"{self.prev_commit}^"],
                    check=True,
                    capture_output=True
                )
                commit_range = f"{self.prev_commit}^..{self.current_commit}"
            except subprocess.CalledProcessError:
                commit_range = f"{self.prev_commit}..{self.current_commit}"

            cmd = [
                "git",
                "log",
                commit_range,
                "--pretty=format:%B",  # Capture full commit message (subject + body)
                "--",
                package_path
            ]

            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().split("\n\n")  # Split by commit
        except subprocess.CalledProcessError as e:
            print(f"Error getting commits for {package_path}: {e}")
            return []

    def determine_package_bump(self, package_path):
        """
        Determine the version bump type for a specific package.

        Args:
            package_path (str): Relative path to the package.

        Returns:
            str or None: Version bump type.

        Happy Path:
            Commit messages for the package result in a clear version bump type.
        Failure Path:
            No relevant commits or errors occur during commit parsing.
        """
        try:
            # Get commits for this package
            package_commits = self.get_package_commits(package_path)

            # If no commits, skip this package
            if not package_commits:
                print(f"No changes found for {package_path}. Skipping version bump.")
                return None

            bump_priority = {"major": 3, "minor": 2, "patch": 1, None: 0}
            highest_bump = None

            for commit in package_commits:
                commit_bump = self._parse_conventional_commit(commit)
                if commit_bump and bump_priority.get(
                    commit_bump, 0
                ) > bump_priority.get(highest_bump, 0):
                    highest_bump = commit_bump

            return highest_bump
        except Exception as e:
            print(f"Error determining version bump for {package_path}: {e}")
            return None

    def _get_tag_format(self, package_info):
        """
    Get the tag format for a package from its pyproject.toml.

    Args:
        package_info (dict): A dictionary containing the package's pyproject data.
                            Expected format: {"pyproject_data": <parsed_toml_data>}.

    Returns:
        str: The tag format string (e.g., "v{version}").

    Raises:
        ValueError: If the tag format is not found in pyproject.toml.
        KeyError: If required keys are missing in pyproject.toml.
    """
        try:
            pyproject_data = package_info["pyproject_data"]
            tool = pyproject_data.get("tool", {})
            tag_format = (
                tool.get("semantic_release", {})
                .get("branches", {})
                .get("main", {})
                .get("tag_format")
            )
            if not tag_format:
                raise ValueError("tag_format not found in pyproject.toml")
            return tag_format
        except KeyError as e:
            raise ValueError(f"Missing key in pyproject.toml: {e}")

    def tag_exists(self, package_info, new_version):
        """
        Check if a Git tag exists for the package version based on tag format.

        Args:
            package_info (dict): A dictionary containing tag format details from pyproject.toml.
                                Expected format: {"package_path": "<path>", "pyproject_path": "<path_to_pyproject>"}
            new_version (str): The new version to check for in Git tags.

        Returns:
            bool: True if the tag exists, otherwise False.
        """
        try:
            pyproject_data = package_info["pyproject_data"]
            project_name = pyproject_data["project"]["name"]
            tag_format = self._get_tag_format(package_info)

            # Generate the tag name using the tag format
            tag_name = tag_format.format(name=project_name, version=new_version)

            # Run the git command to check if the tag exists
            cmd = ["git", "tag", "--list", tag_name]
            result = subprocess.run(
                cmd, cwd=self.repo_root, capture_output=True, text=True, check=True
            )

            # Check if the tag exists in the output
            return tag_name in result.stdout.splitlines()
        except subprocess.CalledProcessError as e:
            print(f"Error: Failed to run git tag command to check tag for {package_info['package_path']}: {e}")
            raise
        except ValueError as e:
            print(f"Error: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error in tag_exists: {e}")
            raise

    def create_tag(self, package_info, new_version):
        """
        Create a Git tag for the updated package version using the tag format from pyproject.toml.

        Args:
            package_info (dict): A dictionary containing tag format details from pyproject.toml.
                                Expected format: {"package_path": "<path>", "pyproject_path": "<path_to_pyproject>"}
            new_version (str): The new version to tag.

        Returns:
            None

        Raises:
            subprocess.CalledProcessError: If the git command fails to create the tag.
            ValueError: If the tag format cannot be generated from pyproject.toml.

        Happy Path:
            - If the tag format is found in `pyproject.toml` and the git tag command succeeds,
            a new tag is created in the repository.

        Failure Path:
            - If the `tag_format` is not found in `pyproject.toml`.
            - If the git command to create the tag fails.
        """
        try:
            with open(package_info["pyproject_path"], "rb") as f:
                pyproject_data =tomlkit.parse(f.read())

            # Retrieve project name
            project_name = pyproject_data.get("project", {}).get("name")
            if not project_name:
                raise ValueError(
                    f"Project name not found in {package_info['pyproject_path']}. Please specify it in the pyproject.toml."
                )

            tag_format = self._get_tag_format(package_info)

            tag_name = tag_format.format(name=project_name, version=new_version)

            cmd = ["git", "tag", tag_name]
            subprocess.run(cmd, cwd=self.repo_root, check=True)

            print(f"Created tag {tag_name}")
        except subprocess.CalledProcessError as e:
            print(
                f"Error: Failed to create tag for {package_info['package_path']}: {e}"
            )
            raise
        except ValueError as e:
            print(f"Error: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error in create_tag: {e}")
            raise

    def update_package_versions(self):
        """
    Update versions for packages with changes and create Git tags.

    Returns:
        dict: A dictionary mapping package names to their updated version information.
              Format: {
                  "package_name": {
                      "old_version": str,
                      "new_version": str,
                      "bump_type": str
                  }
              }

    Raises:
        Exception: If an error occurs during version bumping or tag creation.
    """
        updated_versions = {}
        for package_name, package_info in self.packages.items():
            try:
                bump_type = self.determine_package_bump(package_info["package_path"])
                if not bump_type:
                    continue

                current_version = package_info["current_version"]
                new_version = self._bump_version(current_version, bump_type)

                # Check if the tag for the new_version exists
                if self.tag_exists(package_info, new_version):
                    print(f"Tag for {new_version} already exists. Skipping bump.")
                    continue

                # Update version and create tag
                package_info["pyproject_data"]["project"]["version"] = new_version
                with open(package_info["pyproject_path"], "w") as f:
                    tomlkit.dump(package_info["pyproject_data"], f)

                self.create_tag(package_info, new_version)
                updated_versions[package_name] = {
                    "old_version": current_version,
                    "new_version": new_version,
                    "bump_type": bump_type
                }
            except Exception as e:
                print(f"Error updating {package_name}: {e}")
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

    # Initialize version manager
    try:
        version_manager = PackageVersionManager(repo_root, prev_commit, current_commit)

        # Analyze changes and update package versions
        updated_versions = version_manager.update_package_versions()

        if updated_versions:
            print("\nVersion updates completed successfully:")
            for package, info in updated_versions.items():
                print(
                    f"{package}: {info['old_version']} -> {info['new_version']} ({info['bump_type']} bump)"
                )
        else:
            print("\nNo packages required version updates.")

    except Exception as e:
        print(f"An error occurred during the version update process: {e}")
        sys.exit(1)
