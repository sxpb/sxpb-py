# Development

## Setup

Install PDM as described in [README.md](README.md).
Then install with `--dev` dependencies rather than just `--prod`.

```shell
pdm install --dev
```

## Quality checks

This project uses `ruff` and `ty` for Python, and dogfoods `sxpb-tidy` and
`sxpb-lint` on its SxPB fixtures. Run the complete tidy, lint, and test workflow
before committing.

```bash
pdm run tidytest
```
