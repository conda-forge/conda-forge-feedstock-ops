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

Data can be input into the container via one of two mechanisms

1. Passing data as arguments over the command line.
2. Mounting a directory on the host to `/cf_feedstock_ops_dir`
   in the container. This mount is read-only by default. Internally, the mount is
   not translated to a Docker bind mount, but rather to logic passing tar files
   to and from the container via stdin and stdout. This is for security hardening.

**IMPORTANT: Passing data via stdin is not supported, as this line of
communication is used for inputting tarfiles to the container.**

### Output

Data is returned to the calling process via one of two ways:

1. The container MUST write a json file to `cf_feedstock_ops_dir/return_info.json`.
   This json blob must have only two top-level keys, `error` and `data`.
   Any output data should be put in the `data` key. The `error` key is discussed below.
2. The container can put other data in the `/cf_feedstock_ops_dir` if it is not mounted
   as read-only.

**IMPORTANT: The container cannot write anything to `stdout` because this will break
the tarfile output mechanism for the virtual mounts.**
You can send output to `stderr`.

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
