# sxpb-py

A small schema-agnostic parser and serializer for `.sxpb` files (S-expression protobuf data).

## Explicit list appends

Array and manyof fields have unique names like other message fields.
Append elements with `((+. path...) (()) elements...)`; the path is relative to the message containing the operation and must resolve through existing message or dict keys to an existing array or manyof. Path segments use the usual bare or quoted field-name spelling.

```sxpb
(m (a (()) 1 2 3))
((+. m a) (()) 4 5 6)
```

The `(())` before the appended elements is always required.
Repeating `(m ...)` or `(a ...)` does not append implicitly and is rejected as a duplicate field.

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

## Lint and Tidy

`sxpb-tidy` formats SxPB source while preserving comments and literal spelling.
Line grouping is mostly preserved, with some opinions on where closing parentheses should be.
`sxpb-lint` reports source that is not tidy without modifying it.
With no paths, both commands process the current directory recursively.
Pass explicit files or directories to narrow the scope, or use `-` for stdin.

Repository traversal has no implicit exclusions.
Pass `--ignore-file` to apply gitignore-style patterns from a specific file; patterns are relative to that file's directory and apply to optional explicit paths too.

```shell
sxpb-tidy --ignore-file .gitignore
sxpb-lint --ignore-file .gitignore
sxpb-tidy --ignore-file .gitignore config.sxpb test/content/
sxpb-tidy - < input.sxpb > output.sxpb
sxpb-lint - < input.sxpb
```

Use `sxpb2sxpb` instead when canonicalizing parsed *data*.
That command performs a semantic parse/serialization roundtrip, so it intentionally rewrites source structure and discards comments; `sxpb-tidy` and `sxpb-lint` do neither.
