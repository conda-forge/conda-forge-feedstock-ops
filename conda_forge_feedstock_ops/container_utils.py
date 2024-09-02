import json
import logging
import os
import pprint
import subprocess
from typing import Callable, Iterable, Optional

from ._version import __version__

logger = logging.getLogger(__name__)

DEFAULT_CONTAINER_TMPFS_SIZE_MB = 6000


def get_default_container_name():
    """Get the default container name for feedstock ops.

    The image is stored at `ghcr.io/regro/conda-forge-feedstock-ops`.

    If the environment variable `CF_FEEDSTOCK_OPS_CONTAINER_NAME` is set, then that name is used.

    If the environment variable `CF_FEEDSTOCK_OPS_CONTAINER_TAG` is set, then that tag is pulled.
    Otherwise, we pull the tag `__version__`.
    """
    cname = (
        f"{os.environ.get('CF_FEEDSTOCK_OPS_CONTAINER_NAME', 'ghcr.io/regro/conda-forge-feedstock-ops')}"
        + f":{os.environ.get('CF_FEEDSTOCK_OPS_CONTAINER_TAG', __version__)}"
    )

    return cname


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


def run_container_operation(
    args: Iterable[str],
    json_loads: Callable = json.loads,
    tmpfs_size_mb: int = DEFAULT_CONTAINER_TMPFS_SIZE_MB,
    input: Optional[str] = None,
    mount_dir: Optional[str] = None,
    mount_readonly: bool = True,
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
    input
        The input to pass to the container, by default None.
    mount_dir
        The directory to mount to the container at `/cf_feedstock_ops_dir`, by default None.
    mount_readonly
        Whether to mount the directory as read-only, by default True.

    Returns
    -------
    data : dict-like
        The result of the operation.
    """
    if mount_dir is not None:
        mount_dir = os.path.abspath(mount_dir)
        mnt_args = [
            "--mount",
            f"type=bind,source={mount_dir},destination=/cf_feedstock_ops_dir",
        ]
        if mount_readonly:
            mnt_args[-1] += ",readonly"
    else:
        mnt_args = []

    cmd = [
        *get_default_container_run_args(tmpfs_size_mb=tmpfs_size_mb),
        *mnt_args,
        get_default_container_name(),
        *args,
    ]
    res = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        text=True,
        input=input,
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
        ret_str = (
            ret["error"]
            .split("(", maxsplit=1)[1]
            .rsplit(")", maxsplit=1)[0]
            .encode("raw_unicode_escape")
            .decode("unicode_escape")
        )
        raise ContainerRuntimeError(
            error=f"Error running '{' '.join(args)}' in container - error {ret['error'].split('(')[0]} raised:\n{ret_str}",
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
    in_container = (
        os.environ.get("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false").lower() == "true"
    )
    if use_container is None:
        use_container = not in_container

    if use_container and not in_container:
        return True
    else:
        return False
