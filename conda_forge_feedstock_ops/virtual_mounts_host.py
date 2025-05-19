"""
This module contains functions and classes for the virtual mounts host.
"""

import shutil
import tarfile
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, ClassVar

from plumbum import local

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR

UNTAR_TIMEOUT = 20


@dataclass(frozen=True)
class VirtualMount:
    """
    A virtual mount to be used in a container.
    Since we don't want to use any type of Docker mounts in the container for security
    reasons, nothing is actually mounted.
    Instead, the host path is tarred and passed to the container via stdin.
    For non-read-only mounts, the contents of the container path are tarred and passed
    back to the host via stdout.
    """

    IGNORE_PATHS: ClassVar[set[str]] = {".git"}
    """
    These subdirectories and files are ignored when untarring
    if they appear anywhere in the path.
    """

    host_path: Path
    """
    The path on the host to mount. Files and directories are supported.
    """
    container_path: PurePosixPath
    """
    The path in the container to mount to.
    This must be a subdirectory of CF_FEEDSTOCK_OPS_DIR (or a file inside it).
    (only this directory is writable in the container).
    """
    read_only: bool = True
    """
    If True, no data is passed back to the host. If set to False,
    note that the container (untrusted) can write arbitrary files to host_path!
    """

    def __post_init__(self):
        if not self.container_path.is_absolute():
            raise ValueError("container_path must be an absolute path")
        if not self.container_path.is_relative_to(CF_FEEDSTOCK_OPS_DIR):
            raise ValueError(
                f"container_path must be a subdirectory of {CF_FEEDSTOCK_OPS_DIR}"
            )
        if self.container_path == CF_FEEDSTOCK_OPS_DIR:
            raise ValueError(
                f"container_path must not be {CF_FEEDSTOCK_OPS_DIR} itself"
            )

    @property
    def relative_container_path(self) -> PurePosixPath:
        """
        The relative path in the container.
        """
        # This should never fail because we check in __post_init__
        # that the container_path is a subdirectory of CF_FEEDSTOCK_OPS_DIR
        return self.container_path.relative_to(CF_FEEDSTOCK_OPS_DIR)


@contextmanager
def _mounts_to_tar(mounts: Iterable[VirtualMount]) -> Iterator[IO[bytes]]:
    """
    Yields a temporary file with the host path contents of the mounts tarred.
    """
    with tempfile.TemporaryFile(mode="wb+", suffix=".tar") as target:
        with tarfile.open(fileobj=target, mode="w") as tar:
            for mount in mounts:
                tar.add(mount.host_path, arcname=mount.relative_container_path)
        target.flush()
        target.seek(0)
        yield target


def _delete_non_ignore_paths(target_dir_or_file: Path):
    """
    Delete any files and directories in the target directory or file that are
    NOT in the ignore paths.
    """
    for file_path in target_dir_or_file.rglob("*"):
        relative_path = file_path.relative_to(target_dir_or_file)

        if not VirtualMount.IGNORE_PATHS.intersection(relative_path.parts):
            if file_path.is_dir():
                shutil.rmtree(file_path)
            else:
                file_path.unlink()


def _validate_symlinks_within_dir(directory: Path):
    """
    Validates that all symlinks within the directory point to locations inside the directory.
    Removes any symlinks that point outside.
    """
    for file_path in directory.rglob("*"):
        if not file_path.is_symlink():
            continue
        target = file_path.resolve()
        if directory.resolve() not in target.parents:
            # Remove symlink if it points outside tmpdir
            file_path.unlink()


def _untar_mounts_from_stream(mounts: Iterable[VirtualMount], buffer: bytes) -> None:
    """
    Given the stdout buffer of a container, extract the contents of the mounts.

    Note: This is a security-sensitive operation, as the tar file is untrusted.
    Therefore, we use the GNU tar implementation as it is more robust than Python's tarfile.
    """
    with (
        tempfile.TemporaryDirectory(suffix="untar") as tmpdir_str,
        local.cwd(tmpdir_str),
    ):
        tmpdir = Path(tmpdir_str)
        # extract the entire tar file to a temporary directory
        exclude_args = [
            f"--exclude=**/{path}/**" for path in VirtualMount.IGNORE_PATHS
        ] + [f"--exclude=**/{path}" for path in VirtualMount.IGNORE_PATHS]
        untar = local["tar"][
            "xf", "-", "--no-same-owner", "--no-same-permissions", *exclude_args
        ]
        (untar << buffer)(timeout=UNTAR_TIMEOUT)

        _validate_symlinks_within_dir(tmpdir)

        for mount in mounts:
            if mount.read_only:
                continue
            _delete_non_ignore_paths(mount.host_path)

            if (tmpdir / mount.relative_container_path).is_file():
                # if the mount is a file, copy it to the host path
                shutil.copy2(
                    tmpdir / mount.relative_container_path,
                    mount.host_path,
                )
                continue
            # else, it is a directory
            shutil.copytree(
                tmpdir / mount.relative_container_path,
                mount.host_path,
                symlinks=True,
                dirs_exist_ok=True,
            )
