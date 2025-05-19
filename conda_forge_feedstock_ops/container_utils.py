import json
import logging
import os
import pprint
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Callable, Optional

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR, RETURN_INFO_FILE_NAME
from conda_forge_feedstock_ops.settings import FeedstockOpsSettings
from conda_forge_feedstock_ops.virtual_mounts_host import (
    VirtualMount,
    _mounts_to_tar,
    _untar_mounts_from_stream,
)

logger = logging.getLogger(__name__)

DEFAULT_CONTAINER_TMPFS_SIZE_MB = 6000


def get_default_container_name():
    return FeedstockOpsSettings().container_full_name


class ContainerRuntimeError(RuntimeError):
    """An error raised when running a container fails."""

    def __init__(self, *, error, args, cmd, returncode, traceback=None):
        self.args = args
        self.cmd = cmd
        self.returncode = returncode
        self.traceback = traceback
        super().__init__(error)


def get_default_container_run_args(
    tmpfs_size_mb: int = DEFAULT_CONTAINER_TMPFS_SIZE_MB,
):
    """Get the default arguments for running a container.

    Parameters
    ----------
    tmpfs_size_mb : int, optional
        The size of the tmpfs in MB, by default 10.

    Returns
    -------
    list
        The command to run a container.
    """
    extra_env_vars = []

    tmpfs_size_bytes = tmpfs_size_mb * 1000 * 1000
    return (
        [
            "docker",
            "run",
            "-e",
            "CF_FEEDSTOCK_OPS_IN_CONTAINER=true",
        ]
        + extra_env_vars
        + [
            "--security-opt=no-new-privileges",
            "--read-only",
            "--cap-drop=all",
            "--mount",
            f"type=tmpfs,destination=/tmp,tmpfs-mode=1777,tmpfs-size={tmpfs_size_bytes}",
            "--mount",
            f"type=tmpfs,destination={CF_FEEDSTOCK_OPS_DIR},tmpfs-mode=1777,tmpfs-size={tmpfs_size_bytes}",
            "-m",
            "6000m",
            "--cpus",
            "1",
            "--ulimit",
            "nofile=1024:1024",
            "--ulimit",
            "nproc=2048:2048",
            "--rm",
            "-i",
        ]
    )


def get_default_log_level_args(logger):
    log_level_str = str(logging.getLevelName(logger.getEffectiveLevel())).lower()
    logger.debug("computed effective logging level: %s", log_level_str)
    return [
        "--log-level",
        log_level_str,
    ]


def _get_proxy_mode_container_args():
    settings = FeedstockOpsSettings()
    if not settings.container_proxy_mode:
        return []

    assert os.environ["SSL_CERT_FILE"] == os.environ["REQUESTS_CA_BUNDLE"]
    return [
        "-e",
        f"http_proxy={settings.proxy_in_container}",
        "-e",
        f"https_proxy={settings.proxy_in_container}",
        "-e",
        f"no_proxy={os.environ.get('no_proxy', '')}",
        "-e",
        "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt",
        "-e",
        "REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt",
        "--network",
        "host",
        "-v",
        f"{os.environ['SSL_CERT_FILE']}:/etc/ssl/certs/ca-certificates.crt:ro",
    ]


def run_container_operation(
    args: Iterable[str],
    json_loads: Callable = json.loads,
    tmpfs_size_mb: int = DEFAULT_CONTAINER_TMPFS_SIZE_MB,
    extra_mounts: Iterable[VirtualMount] = (),
    extra_container_args: Optional[Iterable[str]] = None,
):
    """Run a feedstock operation in a container.

    Parameters
    ----------
    args
        The arguments to pass to the container.
    json_loads
        The function to use to load JSON to a string, by default `json.loads`.
    tmpfs_size_mb
        The size of the tmpfs in MB, by default 10.
    extra_mounts
        The virtual mounts passed to the container, by default none.
        The contents of the host paths are passed to the container via stdin,
        in tarred format.
        By default, only the return info file is mounted.
    extra_container_args
        Extra arguments to pass to the container, by default None.

    Returns
    -------
    data : dict-like
        The result of the operation.
    """
    extra_container_args = extra_container_args or []

    cmd = [
        *get_default_container_run_args(tmpfs_size_mb=tmpfs_size_mb),
        *_get_proxy_mode_container_args(),
        *extra_container_args,
        get_default_container_name(),
        *args,
    ]

    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)

        # the return_info_file returns the result of the operation
        return_info_file = tmpdir / RETURN_INFO_FILE_NAME
        return_info_file.touch()

        # the return info file must be present
        mounts = [
            VirtualMount(
                return_info_file,
                CF_FEEDSTOCK_OPS_DIR / RETURN_INFO_FILE_NAME,
                read_only=False,
            )
        ]
        mounts.extend(extra_mounts)

        with _mounts_to_tar(mounts) as stdin_tar_input:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stdin=stdin_tar_input,
            )

        # we handle this ourselves to customize the error message
        if res.returncode != 0:
            try:
                stdout_str = res.stdout.decode("utf-8")
            except UnicodeDecodeError:
                stdout_str = "(cannot decode)"
            raise ContainerRuntimeError(
                error=f"Error running '{' '.join(args)}' in container - return code {res.returncode}:"
                f"\ncmd: {pprint.pformat(cmd)}\nstdout: {stdout_str}",
                args=args,
                cmd=pprint.pformat(cmd),
                returncode=res.returncode,
            )
        try:
            # possible improvement: pipe stdout directly to _untar_mounts_from_stream
            _untar_mounts_from_stream(mounts, res.stdout)
        except Exception as e:
            try:
                stdout_str = res.stdout.decode("utf-8")
            except UnicodeDecodeError:
                stdout_str = "(cannot decode)"
            raise ContainerRuntimeError(
                error=f"Error running '{' '.join(args)}' in container - error while extracting virtual mounts:"
                f"\ncmd: {pprint.pformat(cmd)}\nstdout: {stdout_str}",
                args=args,
                cmd=pprint.pformat(cmd),
                returncode=res.returncode,
            ) from e

        with return_info_file.open("r") as f:
            ret_str = f.read()

        try:
            ret = json_loads(ret_str)
        except json.JSONDecodeError:
            raise ContainerRuntimeError(
                error=f"Error running '{' '.join(args)}' in container - JSON could not be parsed from return info file:"
                f"\ncmd: {pprint.pformat(cmd)}\nstring: {ret_str}",
                args=args,
                cmd=pprint.pformat(cmd),
                returncode=res.returncode,
            )

    if "error" in ret:
        if (
            "(" in ret["error"]
            and ")" in ret["error"]
            and len(ret["error"].split("(", maxsplit=1)) > 1
        ):
            ret_str = (
                ret["error"]
                .split("(", maxsplit=1)[1]
                .rsplit(")", maxsplit=1)[0]
                .encode("raw_unicode_escape")
                .decode("unicode_escape")
            )
            ename = (
                ret["error"]
                .split("(")[0]
                .strip()
                .encode("raw_unicode_escape")
                .decode("unicode_escape")
            )
        elif ":" in ret["error"] and len(ret["error"].split(":", maxsplit=1)) > 1:
            ret_str = (
                ret["error"]
                .split(":", maxsplit=1)[1]
                .strip()
                .encode("raw_unicode_escape")
                .decode("unicode_escape")
            )
            ename = (
                ret["error"]
                .split(":")[0]
                .strip()
                .encode("raw_unicode_escape")
                .decode("unicode_escape")
            )
        else:
            ret_str = ret["error"]
            ename = "<could not be parsed"

        raise ContainerRuntimeError(
            error=f"Error running '{' '.join(args)}' in container - error {ename} raised:\n{ret_str}",
            args=args,
            cmd=pprint.pformat(cmd),
            returncode=res.returncode,
            traceback=ret["traceback"]
            .encode("raw_unicode_escape")
            .decode("unicode_escape"),
        )

    return ret["data"]


def should_use_container(use_container: Optional[bool] = None):
    """Determine if we should use a container.

    Parameters
    ----------
    use_container
        Whether to use a container to run the rerender.
        If None, the function will use a container if the environment
        variable `CF_FEEDSTOCK_OPS_IN_CONTAINER` is 'false'. This feature can be
        used to avoid container in container calls.

    Returns
    -------
    bool
        Whether to use a container.
    """
    in_container = FeedstockOpsSettings().in_container
    if use_container is None:
        use_container = not in_container

    if use_container and not in_container:
        return True
    else:
        return False
