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
    from conda_forge_feedstock_ops.os_utils import (
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

        prev_commit = _execute_git_cmds_and_report(
            cmds=[["git", "rev-parse", "HEAD"]],
            cwd=fs_dir,
            msg="git rev-parse HEAD failed for rerender prev commit",
            ignore_stderr=True,
        ).strip()

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

        if msg is not None:
            output_permissions = get_user_execute_permissions(fs_dir)

            _execute_git_cmds_and_report(
                cmds=[
                    ["git", "add", "-f", "."],
                    ["git", "commit", "-am", msg],
                ],
                cwd=fs_dir,
                msg="git commit failed for rerender",
            )
            curr_commit = _execute_git_cmds_and_report(
                cmds=[["git", "rev-parse", "HEAD"]],
                cwd=fs_dir,
                msg="git rev-parse HEAD failed for rerender curr commit",
                ignore_stderr=True,
            ).strip()
            patch = _execute_git_cmds_and_report(
                cmds=[["git", "diff", prev_commit + ".." + curr_commit]],
                cwd=fs_dir,
                msg="git diff failed for rerender",
                ignore_stderr=True,
            )
        else:
            patch = None
            output_permissions = input_permissions

        return {
            "commit_message": msg,
            "patch": patch,
            "permissions": output_permissions,
        }


def _parse_package_and_feedstock_names():
    from conda_forge_feedstock_ops.os_utils import sync_dirs
    from conda_forge_feedstock_ops.parse_package_and_feedstock_names import (
        parse_package_and_feedstock_names,
    )

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

        fs_dir = os.path.join(tmpdir, os.path.basename(input_fs_dir))
        sync_dirs(input_fs_dir, fs_dir, ignore_dot_git=True, update_git=False)
        logger.debug(
            "copied container feedstock dir %s: %s", fs_dir, os.listdir(fs_dir)
        )

        fs_name, pkg_names, subdirs = parse_package_and_feedstock_names(
            fs_dir, use_container=False
        )

        return {
            "feedstock_name": fs_name,
            "package_names": pkg_names,
            "subdirs": subdirs,
        }


def _lint():
    from conda_forge_feedstock_ops.lint import lint
    from conda_forge_feedstock_ops.os_utils import sync_dirs

    logger = logging.getLogger("conda_forge_feedstock_ops.container")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_fs_dir = "/cf_feedstock_ops_dir"
        logger.debug(
            "input container feedstock dir %s: %s",
            input_fs_dir,
            os.listdir(input_fs_dir),
        )

        fs_dir = os.path.join(tmpdir, os.path.basename(input_fs_dir))
        sync_dirs(input_fs_dir, fs_dir, ignore_dot_git=True, update_git=False)
        logger.debug(
            "copied container feedstock dir %s: %s", fs_dir, os.listdir(fs_dir)
        )

        lints, hints, errors = lint(fs_dir, use_container=False)

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
        existing_feedstock_node_attrs=None,
        timeout=timeout,
    )


@main_container.command(name="parse-package-and-feedstock-names")
@log_level_option
def main_parse_package_and_feedstock_names(log_level):
    return _run_bot_task(
        _parse_package_and_feedstock_names,
        log_level=log_level,
        existing_feedstock_node_attrs=None,
    )


@main_container.command(name="lint")
@log_level_option
def main_lint(log_level):
    return _run_bot_task(
        _lint,
        log_level=log_level,
        existing_feedstock_node_attrs=None,
    )
