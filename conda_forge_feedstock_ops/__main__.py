#!/usr/bin/env python
"""This CLI module runs feedstock operations in a container.

All imports need to be guarded by putting them in the subcommands.
This ensures that we can set important environment variables before any imports,
including `CONDA_BLD_PATH`.

This container is run in a read-only environment except a small tmpfs volume
mounted at `/tmp`. The `TMPDIR` environment variable is set to `/tmp` so that
one can use the `tempfile` module to create temporary files and directories.

These operations return their info by printing a JSON blob to stdout.
"""

import copy
import logging
import os
import subprocess
import sys
import tarfile
import tempfile
import traceback
from contextlib import contextmanager, redirect_stdout
from pathlib import PosixPath

import click

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR as PURE_CF_FEEDSTOCK_OPS_DIR
from conda_forge_feedstock_ops import RETURN_INFO_FILE_NAME
from conda_forge_feedstock_ops.lint import lint
from conda_forge_feedstock_ops.parse_package_and_feedstock_names import (
    parse_package_and_feedstock_names,
)
from conda_forge_feedstock_ops.rerender import rerender_local

LOGGER = logging.getLogger(__name__)

# This file is executed inside the container, so we convert to PosixPath
# to allow filesystem operations (only possible on Linux).
CF_FEEDSTOCK_OPS_DIR = PosixPath(PURE_CF_FEEDSTOCK_OPS_DIR)
RETURN_INFO_FILE_PATH = CF_FEEDSTOCK_OPS_DIR / RETURN_INFO_FILE_NAME

existing_feedstock_node_attrs_option = click.option(
    "--existing-feedstock-node-attrs",
    required=True,
    type=str,
    help=(
        "The existing feedstock node attrs JSON as a string or '-' to read from stdin."
    ),
)
log_level_option = click.option(
    "--log-level",
    default="info",
    type=click.Choice(["debug", "info", "warning", "error", "critical"]),
    help="The log level to use.",
)


@contextmanager
def _setenv(name, value):
    """set an environment variable temporarily"""
    old = os.environ.get(name)
    try:
        os.environ[name] = value
        yield
    finally:
        if old is None:
            del os.environ[name]
        else:
            os.environ[name] = old


def unpack_virtual_mounts_from_stdin():
    CF_FEEDSTOCK_OPS_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=sys.stdin.buffer, mode="r|") as tar:
        tar.extractall(CF_FEEDSTOCK_OPS_DIR, filter="data")


def repack_virtual_mounts_to_stdout():
    # possible improvement: communicate which mounts are read-only and skip them here
    # (now, there are communicated back via stdout, and filtered out in the host)
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|") as tar:
        tar.add(CF_FEEDSTOCK_OPS_DIR, arcname="")


def _run_bot_task(func, *, log_level, **kwargs):
    with (
        tempfile.TemporaryDirectory() as tmpdir_cbld,
        _setenv("CONDA_BLD_PATH", os.path.join(tmpdir_cbld, "conda-bld")),
        tempfile.TemporaryDirectory() as tmpdir_cache,
        _setenv("XDG_CACHE_HOME", tmpdir_cache),
        tempfile.TemporaryDirectory() as tmpdir_conda_pkgs_dirs,
        _setenv("CONDA_PKGS_DIRS", tmpdir_conda_pkgs_dirs),
    ):
        os.makedirs(os.path.join(tmpdir_cbld, "conda-bld"), exist_ok=True)

        from conda_forge_feedstock_ops import setup_logging
        from conda_forge_feedstock_ops.json import dumps
        from conda_forge_feedstock_ops.os_utils import pushd

        data = None
        ret = copy.copy(kwargs)

        with (
            tempfile.TemporaryDirectory() as tmpdir,
            pushd(tmpdir),
        ):
            try:
                with redirect_stdout(sys.stderr):
                    try:
                        # logger call needs to be here so it gets the changed stdout/stderr
                        setup_logging(log_level)
                        unpack_virtual_mounts_from_stdin()
                        data = func(**kwargs)
                        ret["data"] = data
                    except Exception as e:
                        ret["data"] = data
                        ret["error"] = repr(e)
                        ret["traceback"] = traceback.format_exc()
                    finally:
                        with RETURN_INFO_FILE_PATH.open("w") as f:
                            f.write(dumps(ret))

            finally:
                repack_virtual_mounts_to_stdout()


def _execute_git_cmds_and_report(*, cmds, cwd, msg, ignore_stderr=False):
    logger = logging.getLogger("conda_forge_feedstock_ops.container")

    try:
        _output = ""
        _output_stderr = ""
        for cmd in cmds:
            gitret = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE if ignore_stderr else subprocess.STDOUT,
                text=True,
            )
            logger.debug("git command %r output: %s", cmd, gitret.stdout)
            _output += gitret.stdout
            if ignore_stderr:
                _output_stderr += gitret.stderr
            gitret.check_returncode()
    except Exception as e:
        logger.error(
            "%s\noutput: %s\nstderr: %s",
            msg,
            _output,
            _output_stderr if ignore_stderr else "<in output>",
            exc_info=e,
        )
        raise e

    return _output


def _rerender_feedstock(*, timeout):
    input_fs_dirs = list(CF_FEEDSTOCK_OPS_DIR.glob("*-feedstock"))
    assert len(input_fs_dirs) == 1, f"expected one feedstock, got {input_fs_dirs}"
    input_fs_dir = input_fs_dirs[0]
    LOGGER.debug(
        "input container feedstock dir %s: %s",
        input_fs_dir,
        [path.name for path in input_fs_dir.iterdir()],
    )

    if timeout is not None:
        kwargs = {"timeout": timeout}
    else:
        kwargs = {}

    return {"commit_message": rerender_local(str(input_fs_dir), **kwargs)}


def _parse_package_and_feedstock_names():
    input_fs_dirs = list(CF_FEEDSTOCK_OPS_DIR.glob("*-feedstock"))
    assert len(input_fs_dirs) == 1, f"expected one feedstock, got {input_fs_dirs}"
    input_fs_dir = input_fs_dirs[0]
    LOGGER.debug(
        "input container feedstock dir %s: %s",
        input_fs_dir,
        [path.name for path in input_fs_dir.iterdir()],
    )

    fs_name, pkg_names, subdirs = parse_package_and_feedstock_names(
        str(input_fs_dir), use_container=False
    )

    return {
        "feedstock_name": fs_name,
        "package_names": pkg_names,
        "subdirs": subdirs,
    }


def _lint():
    input_fs_dir = CF_FEEDSTOCK_OPS_DIR
    LOGGER.debug(
        "input container feedstock dir %s: %s",
        input_fs_dir,
        [path.name for path in input_fs_dir.iterdir()],
    )

    lints, hints, errors = lint(str(input_fs_dir), use_container=False)

    return {"lints": lints, "hints": hints, "errors": errors}


@click.group()
def main_container():
    pass


@main_container.command(name="rerender")
@log_level_option
@click.option("--timeout", default=None, type=int, help="The timeout for the rerender.")
def main_container_rerender(log_level, timeout):
    return _run_bot_task(
        _rerender_feedstock,
        log_level=log_level,
        timeout=timeout,
    )


@main_container.command(name="parse-package-and-feedstock-names")
@log_level_option
def main_parse_package_and_feedstock_names(log_level):
    return _run_bot_task(
        _parse_package_and_feedstock_names,
        log_level=log_level,
    )


@main_container.command(name="lint")
@log_level_option
def main_lint(log_level):
    return _run_bot_task(
        _lint,
        log_level=log_level,
    )
