## Setup

1. Make sure UV is installed
2. Install packages

```sh
uv pip install .
uv pip install ".[dev]"
```

3. install pre-commit hooks

```sh
pre-commit install
pre-commit install --hook-type commit-msg
# verify the install
ls -a .git/hooks
```

4. notes about Test PyPi
- https://stackoverflow.com/questions/47915527/how-to-do-i-delete-edit-a-package-and-its-release-file-list-in-test-pypi-org
- if we delete a package once, we cannot re-register it in the same name on our account
