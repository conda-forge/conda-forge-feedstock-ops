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
import glob
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from contextlib import contextmanager, redirect_stdout

import click

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


def _get_existing_feedstock_node_attrs(existing_feedstock_node_attrs):
    from conda_forge_feedstock_ops.json import loads

    if existing_feedstock_node_attrs == "-":
        val = sys.stdin.read()
        attrs = loads(val)
    elif existing_feedstock_node_attrs.startswith("{"):
        attrs = loads(existing_feedstock_node_attrs)
    else:
        raise ValueError("existing-feedstock-node-attrs must be a JSON string or '-'")

    return attrs


def _run_bot_task(func, *, log_level, existing_feedstock_node_attrs, **kwargs):
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
        try:
            with (
                redirect_stdout(sys.stderr),
                tempfile.TemporaryDirectory() as tmpdir,
                pushd(tmpdir),
            ):
                # logger call needs to be here so it gets the changed stdout/stderr
                setup_logging(log_level)
                if existing_feedstock_node_attrs is not None:
                    attrs = _get_existing_feedstock_node_attrs(
                        existing_feedstock_node_attrs
                    )
                    data = func(attrs=attrs, **kwargs)
                else:
                    data = func(**kwargs)

            ret["data"] = data

        except Exception as e:
            ret["data"] = data
            ret["error"] = repr(e)
            ret["traceback"] = traceback.format_exc()

        print(dumps(ret))


def _execute_git_cmds_and_report(*, cmds, cwd, msg):
    logger = logging.getLogger("conda_forge_feedstock_ops.container")

    try:
        _output = ""
        for cmd in cmds:
            gitret = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            logger.debug("git command %r output: %s", cmd, gitret.stdout)
            _output += gitret.stdout
            gitret.check_returncode()
    except Exception as e:
        logger.error("%s\noutput: %s", msg, _output, exc_info=e)
        raise e


def _rerender_feedstock(*, timeout):
    from conda_forge_feedstock_ops.os_utils import (
        chmod_plus_rwX,
        get_user_execute_permissions,
        reset_permissions_with_user_execute,
        sync_dirs,
    )
    from conda_forge_feedstock_ops.rerender import rerender_local

    logger = logging.getLogger("conda_forge_feedstock_ops.container")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_fs_dir = glob.glob("/cf_feedstock_ops_dir/*-feedstock")
        assert len(input_fs_dir) == 1, f"expected one feedstock, got {input_fs_dir}"
        input_fs_dir = input_fs_dir[0]
        logger.debug(
            "input container feedstock dir %s: %s",
            input_fs_dir,
            os.listdir(input_fs_dir),
        )
        input_permissions = os.path.join(
            "/cf_feedstock_ops_dir",
            f"permissions-{os.path.basename(input_fs_dir)}.json",
        )
        with open(input_permissions) as f:
            input_permissions = json.load(f)

        fs_dir = os.path.join(tmpdir, os.path.basename(input_fs_dir))
        sync_dirs(input_fs_dir, fs_dir, ignore_dot_git=True, update_git=False)
        logger.debug(
            "copied container feedstock dir %s: %s", fs_dir, os.listdir(fs_dir)
        )

        reset_permissions_with_user_execute(fs_dir, input_permissions)

        has_gitignore = os.path.exists(os.path.join(fs_dir, ".gitignore"))
        if has_gitignore:
            shutil.move(
                os.path.join(fs_dir, ".gitignore"),
                os.path.join(fs_dir, ".gitignore.bak"),
            )

        cmds = [
            ["git", "init", "-b", "main", "."],
            ["git", "add", "."],
            ["git", "commit", "-am", "initial commit"],
        ]
        if has_gitignore:
            cmds += [
                ["git", "mv", ".gitignore.bak", ".gitignore"],
                ["git", "commit", "-am", "put back gitignore"],
            ]
        _execute_git_cmds_and_report(
            cmds=cmds,
            cwd=fs_dir,
            msg="git init failed for rerender",
        )

        if timeout is not None:
            kwargs = {"timeout": timeout}
        else:
            kwargs = {}
        msg = rerender_local(fs_dir, **kwargs)

        if logger.getEffectiveLevel() <= logging.DEBUG:
            cmds = [
                ["git", "status"],
                ["git", "diff", "--name-only"],
                ["git", "diff", "--name-only", "--staged"],
                ["git", "--no-pager", "diff"],
                ["git", "--no-pager", "diff", "--staged"],
            ]
            _execute_git_cmds_and_report(
                cmds=cmds,
                cwd=fs_dir,
                msg="git status failed for rerender",
            )

        # if something changed, copy back the new feedstock
        if msg is not None:
            output_permissions = get_user_execute_permissions(fs_dir)
            sync_dirs(fs_dir, input_fs_dir, ignore_dot_git=True, update_git=False)
        else:
            output_permissions = input_permissions

        chmod_plus_rwX(input_fs_dir, recursive=True, skip_on_error=True)

        return {"commit_message": msg, "permissions": output_permissions}


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
        existing_feedstock_node_attrs=None,
        timeout=timeout,
    )
