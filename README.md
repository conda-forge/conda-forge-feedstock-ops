# conda-forge-feedstock-ops
[![tests](https://github.com/regro/conda-forge-feedstock-ops/actions/workflows/tests.yml/badge.svg)](https://github.com/regro/conda-forge-feedstock-ops/actions/workflows/tests.yml) [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/regro/conda-forge-feedstock-ops/main.svg)](https://results.pre-commit.ci/latest/github/regro/conda-forge-feedstock-ops/main)

A package of containerized feedstock maintenance operations

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
4. The container can put data in the `/cf_feedstock_ops_dir` if it is not mounted
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
