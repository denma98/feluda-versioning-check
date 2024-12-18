## Setup

1. Make sure UV is installed
2. Install packages

```sh
uv pip install .
uv pip install ".[dev]"
```

3. install pre-commit hooks

```sh
pre-commit install --hook-type commit-msg
# verify the install
ls -a .git/hooks
```
