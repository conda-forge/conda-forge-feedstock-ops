# conda-forge-feedstock-ops
[![tests](https://github.com/conda-forge/conda-forge-feedstock-ops/actions/workflows/tests.yml/badge.svg)](https://github.com/conda-forge/conda-forge-feedstock-ops/actions/workflows/tests.yml) [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/conda-forge/conda-forge-feedstock-ops/main.svg)](https://results.pre-commit.ci/latest/github/conda-forge/conda-forge-feedstock-ops/main)

A package of containerized feedstock maintenance operations

## Getting Started & Usage

To use this package, you should run it through the corresponding Python package.

First, install the package:

```bash
conda install -c conda-forge conda-forge-feedstock-ops
```

Then for your feedstock, you can call commands like this:

```python
from conda_forge_feedstock_ops.rerender import rerender

commit_msg = rerender(path_to_feedstock)
```

## Settings

You can customize the behavior of the package by setting environment variables as described in [settings.py](conda_forge_feedstock_ops/settings.py).

## Container Setup

This package works by running commands inside of a container on-the-fly in order to
perform operations on feedstocks in the presence of sensitive data.

### Input

Data can be input into the container via one of three mechanisms

1. Passing data as arguments over the command line.
2. Passing data via `stdin`.
3. Mounting a directory on the host to `/cf_feedstock_ops_dir`
   in the container. This mount is read-only by default.

### Output

Data is returned to the calling process via one of two ways

1. The container can print a json blob to `stdout`. This json blob must
   have only two top-level keys, `error` and `data`. Any output data should
   be put in the `data` key. The `error` key is discussed below.
2. The container can put data in the `/cf_feedstock_ops_dir` if it is not mounted
   as read-only.

**IMPORTANT: The container can only print a valid json blob to `stdout`.
All other output should be sent to `stderr`.**

### Error Handling

Errors can be handled via

1. Exiting the container process with a non-zero exit code.
2. Setting the `error` key in the json blob sent to `stdout`.

Errors in running the container raise a `ContainerRuntimeError` error.

## Building Your Own Container

In order to make your own container that uses this package, you should copy and edit
the `Dockerfile` in this repo.

There are a few important points to keep in mind when doing this.

- The container runs using a non-root user. This is an important security measure and should be kept.
- The container uses an entrypoint to activate an internal conda environment and then run a command via `exec`.
- The `/cf_feedstock_ops_dir` should be declared to `git` as safe in order to allow git operations.

## Notes on the Version Update Algorithm

The version update algorithm for v0 recipes ses a custom `YAML` parsing class for
`conda` recipes in order to parse the recipe into a form that can be
algorithmically migrated without extensively using regex to change the recipe text
directly. This approach allows us to migrate more complicated recipes.

### `YAML` Parsing with Jinja2

We use `ruamel.yaml` and `ruamel.yaml.jinja2` to parse the recipe. These
packages ensure that comments (which can contain conda selectors) are kept. They
also ensure that any `jinja2` syntax is parsed correctly. Further, for
duplicate keys in the `YAML`, but with different conda selectors, we collapse
the selector into the key. Finally, we use the `jinja2` AST to find all
simple `jinja2` `set` statements. These are parsed into a dictionary for later
use.

You can access the parser and parsed recipe via

```python
from conda_forge_feedstock_ops.recipe_parser import CondaMetaYAML

cmeta = CondaMetaYAML(meta_yaml_as_string)

# get the jinja2 vars
for key, v in cmeta.jinja2_vars.items():
    print(key, v)

# print a section of the recipe
print(cmeta.meta["extra"])
```

Note that due to conda selectors and our need to deduplicate keys, any keys
with selectors will look like `"source__###conda-selector###__win or osx"`.
You can access the middle token for selectors at `conda_forge_tick.recipe_parser.CONDA_SELECTOR`.

It is useful to write generators if you want all keys possibly with selectors

```python
def _gen_key_selector(dct: MutableMapping, key: str):
    for k in dct:
        if k == key or (CONDA_SELECTOR in k and k.split(CONDA_SELECTOR)[0] == key):
            yield k


for key in _gen_key_selector(cmeta.meta, "source"):
    print(cmeta.meta[key])
```

### Version Migration Algorithm

Given the parser above, we update versions of v0 recipes via the following algorithm.

1. We compile all selectors in the recipe by recursively traversing
   the `meta.yaml`. We also insert `None` into this set to represent no
   selector.
2. For each selector, we pull out all `url`, hash-type key, and all `jinja2`
   variables with the selector. If none with the selector are found, we default to
   any ones without a selector.
3. For each of the sets of items in step 2 above, we then try and update the
   version and get a new hash for the `url`. We also try common variations
   in the `url` at this stage.
4. Finally, if we can find new hashes for all of the `urls` for each selector,
   we call the migration successful and submit a PR. Otherwise, no PR is submitted.
