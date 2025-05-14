import json
import logging
import os
import pprint
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Optional

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR
from conda_forge_feedstock_ops.settings import FeedstockOpsSettings

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


@dataclass
class Mount:
    host_path: Path
    """
    The path on the host to mount.
    """
    container_path: PurePosixPath
    """
    The path in the container to mount to.
    """
    read_only: bool = True
    """
    Whether to mount the path as read-only.
    """

    @classmethod
    def to_cf_feedstock_ops_dir(cls, host_path: Path, read_only: bool = True):
        """
        Creates a new mount to the default CF_FEEDSTOCK_OPS_DIR.
        """
        return cls(
            host_path=host_path,
            container_path=CF_FEEDSTOCK_OPS_DIR,
            read_only=read_only,
        )

    def to_mount_args(self) -> list[str]:
        """
        Get the corresponding mount arguments for the Docker CLI.
        """
        args = [
            "--mount",
            f"type=bind,source={self.host_path},destination={self.container_path}",
        ]
        if self.read_only:
            args[-1] += ",readonly"
        return args


def run_container_operation(
    args: Iterable[str],
    json_loads: Callable = json.loads,
    tmpfs_size_mb: int = DEFAULT_CONTAINER_TMPFS_SIZE_MB,
    stdin_input: Optional[str] = None,
    mounts: Iterable[Mount] = (),
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
    stdin_input
        The input to pass to the container, by default None.
    mounts
        Bind mounts that should be added to the container, by default none.
    extra_container_args
        Extra arguments to pass to the container, by default None.

    Returns
    -------
    data : dict-like
        The result of the operation.
    """
    mount_args = sum((mount.to_mount_args() for mount in mounts), [])
    extra_container_args = extra_container_args or []

    cmd = [
        *get_default_container_run_args(tmpfs_size_mb=tmpfs_size_mb),
        *mount_args,
        *_get_proxy_mode_container_args(),
        *extra_container_args,
        get_default_container_name(),
        *args,
    ]
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        text=True,
        input=stdin_input,
    )
    # we handle this ourselves to customize the error message
    if res.returncode != 0:
        raise ContainerRuntimeError(
            error=f"Error running '{' '.join(args)}' in container - return code {res.returncode}:"
            f"\ncmd: {pprint.pformat(cmd)}"
            f"\noutput: {pprint.pformat(res.stdout)}",
            args=args,
            cmd=pprint.pformat(cmd),
            returncode=res.returncode,
        )

    try:
        ret = json_loads(res.stdout)
    except json.JSONDecodeError:
        raise ContainerRuntimeError(
            error=f"Error running '{' '.join(args)}' in container - JSON could not parse stdout:"
            f"\ncmd: {pprint.pformat(cmd)}"
            f"\noutput: {pprint.pformat(res.stdout)}",
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
