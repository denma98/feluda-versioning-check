# import os
import pytest
from semantic_release_workflow import PackageVersionManager

# Test setup: Create a temporary test repo
@pytest.fixture
def test_repo(tmp_path):
    repo_root = tmp_path / "monorepo"
    repo_root.mkdir()
    (repo_root / "operators").mkdir()

    # Create feluda package
    feluda = repo_root / "feluda"
    feluda.mkdir()
    (feluda / "pyproject.toml").write_text("""
    [project]
    name = "feluda"
    version = "0.1.0"

    [tool.semantic_release.branches.main]
    tag_format = "v{version}"
    """)

    # Create an operator package
    package1 = repo_root / "operators" / "package1"
    package1.mkdir()
    (package1 / "pyproject.toml").write_text("""
    [project]
    name = "package1"
    version = "1.0.0"

    [tool.semantic_release.branches.main]
    tag_format = "v{version}"
    """)

    return repo_root



def test_discover_packages(test_repo):
    version_manager = PackageVersionManager(str(test_repo), "prev_commit", "new_commit")
    assert "package1" in version_manager.packages
    assert version_manager.packages["package1"]["current_version"] == "1.0.0"

def test_version_bump(test_repo):
    manager = PackageVersionManager(str(test_repo), "prev_commit", "new_commit")
    assert manager._bump_version("1.2.3", "patch") == "1.2.4"
    assert manager._bump_version("1.2.3", "minor") == "1.3.0"
    assert manager._bump_version("1.2.3", "major") == "2.0.0"
