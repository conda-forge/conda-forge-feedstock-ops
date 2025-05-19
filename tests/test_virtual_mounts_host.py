import os
import tarfile
from pathlib import Path, PurePosixPath
from unittest.mock import patch

import pytest
from plumbum import ProcessTimedOut

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR
from conda_forge_feedstock_ops.virtual_mounts_host import (
    VirtualMount,
    _mounts_to_tar,
    _untar_mounts_from_stream,
)


class TestVirtualMount:
    def test_post_init(self):
        with pytest.raises(ValueError, match="must be an absolute path"):
            VirtualMount(
                host_path=Path("/tmp"),
                container_path=PurePosixPath("relative/path"),
            )

        with pytest.raises(
            ValueError, match=f"must be a subdirectory of {CF_FEEDSTOCK_OPS_DIR}"
        ):
            VirtualMount(
                host_path=Path("/tmp"),
                container_path=PurePosixPath("/tmp"),
            )

        # Test that the container_path is not CF_FEEDSTOCK_OPS_DIR itself
        with pytest.raises(
            ValueError, match=f"must not be {CF_FEEDSTOCK_OPS_DIR} itself"
        ):
            VirtualMount(
                host_path=Path("/tmp"),
                container_path=CF_FEEDSTOCK_OPS_DIR,
            )

    def test_relative_container_path(self):
        mount = VirtualMount(
            host_path=Path("/tmp"),
            container_path=CF_FEEDSTOCK_OPS_DIR / "subdir",
        )
        assert mount.relative_container_path == PurePosixPath("subdir")


def test_mounts_to_tar(tmp_path):
    testfile = tmp_path / "test.txt"
    testfile.write_text("Hello, World!")
    mount = VirtualMount(
        host_path=tmp_path,
        container_path=CF_FEEDSTOCK_OPS_DIR / "subdir",
    )
    with _mounts_to_tar([mount]) as test_file:
        testfile.unlink()
        with tarfile.open(fileobj=test_file, mode="r|") as tar:
            tar.extractall(tmp_path)
        assert (tmp_path / "subdir" / "test.txt").exists()
        assert (tmp_path / "subdir" / "test.txt").read_text() == "Hello, World!"


@pytest.fixture()
def example_tar_file(tmp_path) -> Path:
    tar_creation_location = tmp_path

    not_extract_file = tar_creation_location / "not_extract.txt"
    not_extract_file.write_text("This should not be extracted")
    extract_file = tar_creation_location / "extract.txt"
    extract_file.write_text("This should be extracted")
    executable_file = tar_creation_location / "executable_file.txt"
    executable_file.write_text("This should be executable")
    executable_file.chmod(0o755)

    tar_file = tar_creation_location / "test.tar"
    with tarfile.open(tar_file, mode="w") as tar:
        tar.add(not_extract_file, arcname="root.txt")
        tar.add(extract_file, arcname="extract.txt")
        tar.add(not_extract_file, arcname="wrong_subdir/wrong.txt")
        tar.add(not_extract_file, arcname="read_only/subdir/read_only.txt")
        tar.add(not_extract_file, arcname="writable/.git/git_file")
        tar.add(not_extract_file, arcname="writable/subdir/.git/git_file")
        tar.add(not_extract_file, arcname="writable/anywhere/.git/deep/in/git_file")
        tar.add(executable_file, arcname="writable/subdir/executable.txt")
        tar.add(extract_file, arcname="writable/file_overwrite.txt")

    return tar_file


def test_untar_mounts_from_stream(tmp_path_factory, example_tar_file):
    assert ".git" in VirtualMount.IGNORE_PATHS, "This test assumes .git is ignored"

    host_location_1 = tmp_path_factory.mktemp("host_location_1")
    host_location_2 = tmp_path_factory.mktemp("host_location_2")
    single_file_location = (
        tmp_path_factory.mktemp("single_file_location") / "extract.txt"
    )

    # we intentionally create a directory that should be overwritten by a file
    single_file_location.mkdir()

    file_intact = host_location_1 / "file_intact.txt"
    file_intact.write_text("This should be intact")
    file_intact_2 = host_location_2 / ".git" / "file_intact.txt"
    file_intact_2.parent.mkdir()
    file_intact_2.write_text("This should be intact too")
    file_deleted = host_location_2 / "file_deleted.txt"
    file_deleted.write_text("This should be deleted")
    file_overwrite = host_location_2 / "file_overwrite.txt"

    mounts = [
        VirtualMount(
            host_path=host_location_1,
            container_path=CF_FEEDSTOCK_OPS_DIR / "readonly",
            read_only=True,
        ),
        VirtualMount(
            host_path=host_location_2,
            container_path=CF_FEEDSTOCK_OPS_DIR / "writable",
            read_only=False,
        ),
        VirtualMount(
            host_path=single_file_location,
            container_path=CF_FEEDSTOCK_OPS_DIR / "extract.txt",
            read_only=False,
        ),
    ]

    with open(example_tar_file, mode="rb") as tar:
        _untar_mounts_from_stream(mounts, tar.read())

    assert file_intact.read_text() == "This should be intact"
    assert file_intact_2.read_text() == "This should be intact too"
    assert not file_deleted.exists()
    assert file_overwrite.read_text() == "This should be extracted"
    # assert non executable file is not executable
    assert not os.access(file_overwrite, os.X_OK)
    assert (
        host_location_2 / "subdir" / "executable.txt"
    ).read_text() == "This should be executable"
    assert os.access(host_location_2 / "subdir" / "executable.txt", os.X_OK)

    file_count_location_1 = len(list(host_location_1.glob("**/*")))
    file_count_location_2 = len(list(host_location_2.glob("**/*")))

    # file_intact
    assert file_count_location_1 == 1
    # file_overwrite, subdir, subdir/executable.txt, .git, .git/file_intact.txt
    assert file_count_location_2 == 5
    assert single_file_location.is_file()


@patch("conda_forge_feedstock_ops.virtual_mounts_host.UNTAR_TIMEOUT", 0.001)
def test_untar_mounts_from_stdin_timeout(tmp_path_factory, example_tar_file):
    host_location_1 = tmp_path_factory.mktemp("host_location_1")
    host_location_2 = tmp_path_factory.mktemp("host_location_2")
    mounts = [
        VirtualMount(
            host_path=host_location_1,
            container_path=CF_FEEDSTOCK_OPS_DIR / "readonly",
            read_only=True,
        ),
        VirtualMount(
            host_path=host_location_2,
            container_path=CF_FEEDSTOCK_OPS_DIR / "writable",
            read_only=False,
        ),
    ]

    with open(example_tar_file, mode="rb") as tar:
        with pytest.raises(ProcessTimedOut):
            _untar_mounts_from_stream(mounts, tar.read())


def test_untar_mounts_from_stream_block_symlinks(tmp_path_factory):
    assert ".git" in VirtualMount.IGNORE_PATHS, "This test assumes .git is ignored"
    host_location_1 = tmp_path_factory.mktemp("host_location_1")
    host_location_2 = tmp_path_factory.mktemp("host_location_2")
    mounts = [
        VirtualMount(
            host_path=host_location_1,
            container_path=CF_FEEDSTOCK_OPS_DIR / "readonly",
            read_only=True,
        ),
        VirtualMount(
            host_path=host_location_2,
            container_path=CF_FEEDSTOCK_OPS_DIR / "writable",
            read_only=False,
        ),
    ]

    tar_creation_dir = tmp_path_factory.mktemp("tar_creation_dir")
    evil_symlink = tar_creation_dir / "evil_symlink"

    evil_target = tmp_path_factory.mktemp("symlink_target") / "evil_symlink_target"
    evil_target.mkdir()
    (evil_target / "evil_file.txt").touch()
    os.symlink(evil_target, evil_symlink)

    # relative symlinks pointing to files within the tar are allowed
    benign_target = tar_creation_dir / "benign_target"
    benign_target.mkdir()
    benign_symlink = tar_creation_dir / "benign_symlink"
    os.symlink("benign_target", benign_symlink)

    symlink_to_ignore_path = tar_creation_dir / "symlink_to_ignore"
    os.symlink(".git", symlink_to_ignore_path)

    tar_file = tar_creation_dir / "test.tar"
    with tarfile.open(tar_file, "w") as tar:
        tar.add(evil_symlink, arcname="writable/evil_symlink")
        tar.add(benign_symlink, arcname="writable/benign_symlink")
        tar.add(benign_target, arcname="writable/benign_target")
        tar.add(symlink_to_ignore_path, arcname="writable/symlink_to_ignore")

    with open(tar_file, mode="rb") as tar:
        _untar_mounts_from_stream(mounts, tar.read())

    assert not (host_location_2 / "evil_symlink").exists()
    assert (host_location_2 / "benign_symlink").exists()
    assert not (host_location_2 / "symlink_to_ignore").is_symlink()
