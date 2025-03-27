import glob
import os
import re
import subprocess
import sys
import tomlkit
import semver
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

        print("🚀 Initializing PackageVersionManager...")  # Debug print

        try:
            print("🔍 Calling _discover_packages()...")  # Debug
            self.packages = self._discover_packages()  # This line is failing!
            # print(f"✅ Discovered packages: {self.packages}")  # Debug print
        except Exception as e:
            print(f"❌ Error in package discovery: {e}")  # Show full error
            self.packages = {}  # Ensure it is always initialized

    def _discover_packages(self):
        """
        Discover all packages in the monorepo with their pyproject.toml.
        """
        print("🔍 Running _discover_packages()...")  # Debug print

        packages = {}

        operators_path = os.path.join(self.repo_root, "operators")
        if not os.path.exists(operators_path):
            print(f"⚠️ Warning: Operators directory not found at {operators_path}")

        package_roots = ["feluda"]

        if os.path.isdir(operators_path):
            for folder in glob.glob(f"{operators_path}/*/pyproject.toml"):
                package_roots.append(os.path.dirname(folder))

        # print(f"📂 Packages to check: {package_roots}")  # Debug print

        for package_root in package_roots:
            try:
                print(f"🔎 Checking package: {package_root}")  # Debug print
                if package_root == "feluda":
                    pyproject_path = os.path.join(self.repo_root, "pyproject.toml")
                    full_path = os.path.join(self.repo_root, "feluda")
                else:
                    full_path = os.path.join(self.repo_root, package_root)
                    pyproject_path = os.path.join(full_path, "pyproject.toml")

                if not os.path.exists(pyproject_path):
                    raise FileNotFoundError(f"❌ pyproject.toml not found in {package_root}")

                print(f"📄 Found pyproject.toml: {pyproject_path}")  # Debug print

                with open(pyproject_path, "r", encoding="utf-8") as f:
                    pyproject_data = tomlkit.parse(f.read())

                print(f"✅ Validated pyproject.toml for {package_root}")  # Debug print

                self._validate_pyproject(pyproject_data, pyproject_path)

                packages[package_root] = {
                    "package_path": full_path,
                    "pyproject_path": pyproject_path,
                    "pyproject_data": pyproject_data,
                    "current_version": pyproject_data["project"].get("version", "0.0.0"),
                }

            except (FileNotFoundError, tomlkit.exceptions.ParseError, ValueError) as e:
                print(f"❌ Error discovering package at {package_root}: {e}")

        # print(f"✅ Final package list: {packages}")  # Debug print

        if not packages:
            raise ValueError("❌ No valid packages discovered in the repository")

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

    def _validate_pyproject(self, pyproject_data, pyproject_path):
        required_fields = [
            pyproject_data.get("project", {}).get("name"),
            pyproject_data.get("project", {}).get("version"),
            pyproject_data.get("tool", {})
                .get("semantic_release", {})
                .get("branches", {})
                .get("main", {})
                .get("tag_format"),
        ]
        if not all(required_fields):
            raise ValueError(f"Missing required fields in {pyproject_path}")
        return True

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
        try:
            cmd = [
                "git",
                "log",
                f"{self.prev_commit}^..{self.current_commit}",
                "--pretty=format:%s",
                "--",
                package_path,
            ]

            print(f"📝 Running Git command: {' '.join(cmd)}")  # Debug
            result = subprocess.run(
                cmd, cwd=self.repo_root, capture_output=True, text=True, check=True
            )

            package_commits = result.stdout.splitlines()
            print(f"📜 Commits affecting {package_path}: {package_commits}")  # Debug

            return package_commits
        except subprocess.CalledProcessError as e:
            print(f"❌ Error getting commits for {package_path}: {e}")
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
        Check if a Git tag exists for the package version. If it does,
        automatically find the next available version.
        """
        project_name = package_info["pyproject_data"]["project"]["name"]
        tag_format = self._get_tag_format(package_info)

        current_version = semver.Version.parse(new_version)  # Convert to semver object
        tag_name = tag_format.format(name=project_name, version=str(current_version))

        print(f"🔍 Checking if tag exists: {tag_name}")  # Debug

        cmd = ["git", "tag", "--list"]
        result = subprocess.run(cmd, cwd=self.repo_root, capture_output=True, text=True, check=True)

        existing_tags = result.stdout.splitlines()
        print(f"📌 Existing tags: {existing_tags}")  # Debug

        if tag_name in existing_tags:
            print(f"⚠️ Tag {tag_name} already exists.")  # Debug
            return True  # Return True if the tag exists

        print(f"✅ Tag {tag_name} does not exist.")  # Debug
        return False  # Return False if the tag does not exist


    def create_tag(self, package_info, new_version):
        """
        Create a Git tag for the updated package version using the final incremented version.
        """
        project_name = package_info["pyproject_data"]["project"]["name"]
        tag_format = self._get_tag_format(package_info)

        # Ensure we're using the properly incremented version
        tag_name = tag_format.format(name=project_name, version=new_version)
        print(f"🔍 Attempting to create tag: {tag_name}")  # Debug print

        # Fetch existing tags to prevent duplicate creation
        existing_tags = subprocess.run(
            ["git", "tag", "--list"], cwd=self.repo_root, capture_output=True, text=True, check=True
        ).stdout.splitlines()

        if tag_name in existing_tags:
            print(f"⚠️ Tag {tag_name} already exists, skipping tag creation.")
            return  # Exit early to avoid errors

        cmd = ["git", "tag", tag_name]
        try:
            subprocess.run(cmd, cwd=self.repo_root, check=True)
            print(f"✅ Created tag {tag_name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating tag {tag_name}: {e}")



    def update_package_versions(self):
        """
        Update versions for packages with changes and create Git tags.

        Returns:
            dict: A dictionary mapping package names to their updated version information.
        """
        updated_versions = {}

        for package_name, package_info in self.packages.items():
            try:
                bump_type = self.determine_package_bump(package_info["package_path"])
                if not bump_type:
                    print(f"⏩ Skipping {package_name}, no changes detected.")
                    continue

                # Ensure we always fetch the latest version
                current_version = package_info.get("current_version", "0.0.0")
                print(f"🔍 Current version for {package_name}: {current_version}")

                new_version = self._bump_version(current_version, bump_type)

                # ✅ Ensure we find the final available version
                while self.tag_exists(package_info, new_version):
                    print(f"⚠️ Tag {new_version} already exists. Incrementing version...")
                    new_version = self._bump_version(new_version, "patch")  # Increment patch instead
                    print(f"🔄 New version after increment: {new_version}")  # Debug

                print(f"✅ Using new tag: {new_version}")

                # 🔥 Debug before assignment
                print(f"📝 Before updating package_info: {package_info['pyproject_data']['project']['version']}")

                # 🛠 Explicitly update current_version to avoid resetting issue
                package_info["current_version"] = new_version

                # 🛠 Force update pyproject.toml version
                package_info["pyproject_data"]["project"]["version"] = new_version

                # 🔥 Debug after assignment
                print(f"✅ After updating package_info: {package_info['pyproject_data']['project']['version']}")

                # ✅ Now update pyproject.toml with the final version
                print(f"📝 Writing final version {new_version} to {package_info['pyproject_path']}")

                with open(package_info["pyproject_path"], "w", encoding="utf-8") as f:
                    tomlkit.dump(package_info["pyproject_data"], f)

                print(f"✅ Successfully wrote version {new_version} to {package_info['pyproject_path']}")

                # ✅ Now create the tag
                self.create_tag(package_info, new_version)

                updated_versions[package_name] = {
                    "old_version": current_version,
                    "new_version": new_version,
                    "bump_type": bump_type
                }

            except Exception as e:
                print(f"❌ Error updating {package_name}: {e}")

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
