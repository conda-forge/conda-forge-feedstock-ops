import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from threading import Event, Thread

from conda_forge_feedstock_ops.container_utils import (
    get_default_log_level_args,
    run_container_operation,
    should_use_container,
)
from conda_forge_feedstock_ops.os_utils import (
    chmod_plus_rwX,
    get_user_execute_permissions,
    pushd,
    reset_permissions_with_user_execute,
    sync_dirs,
)

logger = logging.getLogger(__name__)


def rerender(feedstock_dir, timeout=None, use_container=None):
    """Rerender a feedstock.

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.
    timeout : int, optional
        The timeout for the rerender in seconds. If None, no timeout is used.
    use_container
        Whether to use a container to run the rerender.
        If None, the function will use a container if the environment
        variable `CF_FEEDSTOCK_OPS_IN_CONTAINER` is 'false'. This feature can be
        used to avoid container in container calls.

    Returns
    -------
    str
        The commit message for the rerender. If None, the rerender didn't change anything.
    """
    if should_use_container(use_container=use_container):
        return rerender_containerized(
            feedstock_dir,
            timeout=timeout,
        )
    else:
        return rerender_local(
            feedstock_dir,
            timeout=timeout,
        )


def rerender_containerized(feedstock_dir, timeout=None):
    """Rerender a feedstock.

    **This function runs the rerender in a container.**

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.
    timeout : int, optional
        The timeout for the rerender in seconds. If None, no timeout is used.

    Returns
    -------
    str
        The commit message for the rerender. If None, the rerender didn't change anything.
    """
    args = [
        "conda-forge-feedstock-ops-container",
        "rerender",
    ] + get_default_log_level_args(logger)

    if timeout is not None:
        args += ["--timeout", str(timeout)]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_feedstock_dir = os.path.join(tmpdir, os.path.basename(feedstock_dir))
        sync_dirs(
            feedstock_dir, tmp_feedstock_dir, ignore_dot_git=True, update_git=False
        )

        perms = get_user_execute_permissions(feedstock_dir)
        with open(
            os.path.join(tmpdir, f"permissions-{os.path.basename(feedstock_dir)}.json"),
            "w",
        ) as f:
            json.dump(perms, f)

        chmod_plus_rwX(tmpdir, recursive=True)

        logger.debug(
            "host feedstock dir %s: %r",
            feedstock_dir,
            os.listdir(feedstock_dir),
        )
        logger.debug(
            "copied host feedstock dir %s: %r",
            tmp_feedstock_dir,
            os.listdir(tmp_feedstock_dir),
        )

        data = run_container_operation(
            args,
            mount_readonly=False,
            mount_dir=tmpdir,
        )

        if data["commit_message"] is not None and data["patch"] is not None:
            patch_file = os.path.join(
                tmpdir, f"rerender-diff-{os.path.basename(feedstock_dir)}.patch"
            )
            with open(patch_file, "w") as fp:
                fp.write(data["patch"])
            subprocess.run(
                ["git", "apply", "--allow-empty", patch_file],
                check=True,
                cwd=feedstock_dir,
            )
            logger.warning("rerender patch:\n%s", data["patch"])  # FIXME
            reset_permissions_with_user_execute(feedstock_dir, data["permissions"])
            subprocess.run(
                ["git", "add", "."],
                check=True,
                cwd=feedstock_dir,
            )

        # When tempfile removes tempdir, it tries to reset permissions on subdirs.
        # This causes a permission error since the subdirs were made by the user
        # in the container. So we remove the subdir we made before cleaning up.
        shutil.rmtree(tmp_feedstock_dir)

    return data["commit_message"]


# code to stream i/o like tee from this SO post
# https://stackoverflow.com/questions/2996887/how-to-replicate-tee-behavior-in-python-when-using-subprocess
# but it is working and changed a bit to handle two streams


class _StreamToStderr(Thread):
    def __init__(self, buffer, stop_event, timeout=None):
        super().__init__()
        self.buffer = buffer
        self.lines = []
        self.timeout = timeout
        self.stop_event = stop_event

    def run(self):
        t0 = time.time()
        while True:
            if self.stop_event.is_set():
                break

            if self.timeout is not None and time.time() - t0 > self.timeout:
                break

            try:
                line = self.buffer.readline()
            except Exception:
                line = ""

            if line:
                self.lines.append(line)
                sys.stderr.write(line)
                sys.stderr.flush()

        self.output = "".join(self.lines)


def _subprocess_run_tee(args, timeout=None):
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    os.set_blocking(proc.stdout.fileno(), False)
    os.set_blocking(proc.stderr.fileno(), False)

    stop_event = Event()
    threads = [
        _StreamToStderr(proc.stdout, stop_event, timeout=timeout),
        _StreamToStderr(proc.stderr, stop_event, timeout=timeout),
    ]
    for out_thread in threads:
        out_thread.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        stop_event.set()
        for out_thread in threads:
            out_thread.join()

        try:
            out, err = proc.communicate(timeout=30)
        except Exception:
            out, err = "", ""

    for line in (err + out).splitlines():
        sys.stderr.write(line + "\n")
        sys.stderr.flush()

    final_out = ""
    for out_thread in threads:
        final_out += out_thread.output
    proc.stdout = final_out + out + err

    return proc


def rerender_local(feedstock_dir, timeout=None):
    """Rerender a feedstock.

    **This function runs the rerender in a container.**

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.
    timeout : int, optional
        The timeout for the rerender in seconds. If None, no timeout is used.

    Returns
    -------
    str
        The commit message for the rerender. If None, the rerender didn't change anything.
    """
    with (
        pushd(feedstock_dir),
        tempfile.TemporaryDirectory() as tmpdir,
    ):
        ret = _subprocess_run_tee(
            [
                "conda",
                "smithy",
                "rerender",
                "--no-check-uptodate",
                "--temporary-directory",
                tmpdir,
            ],
            timeout=timeout,
        )

    if ret.returncode != 0:
        raise RuntimeError(f"Failed to rerender.\noutput: {ret.stdout}\n")

    commit_message = None
    for line in ret.stdout.split("\n"):
        if '    git commit -m "MNT: ' in line:
            commit_message = line.split('git commit -m "')[1].strip()[:-1]

    return commit_message
