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
- test pypi gives some package error's while installing, so we should keep the uv.tool commented when we don't want to use it
- when we want to use it, we install the packages like this

```sh
uv pip install ".[dev]" --index-strategy unsafe-best-match
```

5. build and publish commands

```sh
# for feluda
uv build --index-strategy unsafe-best-match
ls dist
rm -rf dist

# for image vec
cd operators/image_vec_rep_resnet/
uv build --index-strategy unsafe-best-match
```

then we publish

- default folder for uv publish is `dist/*`
- add `UV_PUBLISH_TOKEN` to `.env`

```sh
# do a source this way we don't have to manually, uv publish picks it up from the env
source .env
uv publish --publish-url https://test.pypi.org/legacy/ --token $UV_PUBLISH_TOKEN
```

#### now to run the published packages use this

```sh
uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/
```

The demo notebook where the pacakges from test pypi are installed and used can be found - [here](https://colab.research.google.com/drive/1DRKILpyqYwe_dOtklM5g4B4czf2aty7l?usp=sharing)
