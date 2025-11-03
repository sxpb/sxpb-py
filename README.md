# sxpb-py

A small schema-agnostic parser and serializer for `.sxpb` files (S-expression protobuf data).

## Setup

### PDM Prereq

Install `pdm` on your machine via `apt install pdm`.
Then install package dependencies for this project, omitting the ones needed for development (see [CONTRIBUTING.md](CONTRIBUTING.md) for that).

```shell
pdm install --prod
```

If `pdm` is not available directly, then try installing `uv` like `apk add uv` and set up the environment.
You'll have to run `pdm` as `uv tool run pdm`.

```shell
uv venv .venv
uv pip install pdm
uv tool run pdm install --prod
```
