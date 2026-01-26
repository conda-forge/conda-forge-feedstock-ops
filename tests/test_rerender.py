import glob
import os
import subprocess
import tempfile

import pytest
from conftest import skipif_no_containers

from conda_forge_feedstock_ops.os_utils import (
    get_user_execute_permissions,
    pushd,
)
from conda_forge_feedstock_ops.rerender import rerender_containerized, rerender_local


def test_rerender_local_stderr(capfd):
    with tempfile.TemporaryDirectory() as tmpdir, pushd(tmpdir):
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/conda-forge/conda-forge-feedstock-check-solvable-feedstock.git",
            ]
        )
        # make sure rerender happens
        with pushd("conda-forge-feedstock-check-solvable-feedstock"):
            cmds = [
                ["git", "rm", "-f", ".gitignore"],
                ["git", "rm", "-rf", ".scripts"],
                ["git", "rm", "-f", ".azure-pipelines/azure-pipelines-linux.yml"],
                ["git", "config", "user.email", "conda@conda.conda"],
                ["git", "config", "user.name", "conda c. conda"],
                ["git", "commit", "-m", "test commit"],
            ]
            for cmd in cmds:
                subprocess.run(
                    cmd,
                    check=True,
                )

        try:
            msg = rerender_local(
                os.path.join(tmpdir, "conda-forge-feedstock-check-solvable-feedstock"),
            )
        finally:
            captured = capfd.readouterr()
            print(f"out: {captured.out}\nerr: {captured.err}")

        assert "git commit -m " in captured.err
        assert msg is not None, f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
        assert msg.startswith("MNT:"), (
            f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
        )


def test_rerender_local_git_staged():
    with tempfile.TemporaryDirectory() as tmpdir, pushd(tmpdir):
        subprocess.run(
            [
                "git",
                "clone",
                "https://github.com/conda-forge/conda-forge-feedstock-check-solvable-feedstock.git",
            ]
        )
        # make sure rerender happens
        with pushd("conda-forge-feedstock-check-solvable-feedstock"):
            cmds = [
                ["git", "rm", "-f", ".gitignore"],
                ["git", "rm", "-rf", ".scripts"],
                ["git", "rm", "-f", ".azure-pipelines/azure-pipelines-linux.yml"],
                ["git", "config", "user.email", "conda@conda.conda"],
                ["git", "config", "user.name", "conda c. conda"],
                ["git", "commit", "-m", "test commit"],
            ]
            for cmd in cmds:
                subprocess.run(
                    cmd,
                    check=True,
                )

        msg = rerender_local(
            os.path.join(tmpdir, "conda-forge-feedstock-check-solvable-feedstock"),
        )
        assert msg is not None

        # check that things are staged in git
        with pushd("conda-forge-feedstock-check-solvable-feedstock"):
            ret = subprocess.run(
                ["git", "diff", "--name-only", "--staged"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=True,
            )
        found_it = False
        for line in ret.stdout.split("\n"):
            if ".gitignore" in line:
                found_it = True
                break
        assert found_it, ret.stdout


@pytest.mark.parametrize("use_exclusive_config_file", [False, True])
@skipif_no_containers
def test_rerender_containerized_same_as_local_own_feedstock(
    use_containers, capfd, use_exclusive_config_file
):
    if use_exclusive_config_file:
        cbc_path = os.path.abspath(
            os.path.expandvars("${CONDA_PREFIX}/conda_build_config.yaml")
        )
        assert os.path.exists(cbc_path), (
            "The config file at `{cbc_path}` does not exist!"
        )
        rrnd_kwargs = {"exclusive_config_file": cbc_path}
    else:
        rrnd_kwargs = {}

    with (
        tempfile.TemporaryDirectory() as tmpdir_cont,
        tempfile.TemporaryDirectory() as tmpdir_local,
    ):
        assert tmpdir_cont != tmpdir_local

        with pushd(tmpdir_cont):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/conda-forge/conda-forge-feedstock-check-solvable-feedstock.git",
                ]
            )
            # make sure rerender happens
            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                cmds = [
                    ["git", "rm", "-f", ".gitignore"],
                    ["git", "rm", "-rf", ".scripts"],
                    ["git", "rm", "-f", ".azure-pipelines/azure-pipelines-linux.yml"],
                    ["git", "config", "user.email", "conda@conda.conda"],
                    ["git", "config", "user.name", "conda c. conda"],
                    ["git", "commit", "-m", "test commit"],
                ]
                for cmd in cmds:
                    subprocess.run(
                        cmd,
                        check=True,
                    )

            try:
                msg = rerender_containerized(
                    os.path.join(
                        tmpdir_cont, "conda-forge-feedstock-check-solvable-feedstock"
                    ),
                    **rrnd_kwargs,
                )
            finally:
                captured = capfd.readouterr()
                print(f"out: {captured.out}\nerr: {captured.err}")

            if "git commit -m " in captured.err:
                assert msg is not None, (
                    f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
                )
                assert msg.startswith("MNT:"), (
                    f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
                )
                with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                    assert os.path.exists(".azure-pipelines/azure-pipelines-linux.yml")
            else:
                assert msg is None, (
                    f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
                )

        with pushd(tmpdir_local):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/conda-forge/conda-forge-feedstock-check-solvable-feedstock.git",
                ]
            )
            # make sure rerender happens
            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                cmds = [
                    ["git", "rm", "-f", ".gitignore"],
                    ["git", "rm", "-rf", ".scripts"],
                    ["git", "rm", "-f", ".azure-pipelines/azure-pipelines-linux.yml"],
                    ["git", "config", "user.email", "conda@conda.conda"],
                    ["git", "config", "user.name", "conda c. conda"],
                    ["git", "commit", "-m", "test commit"],
                ]
                for cmd in cmds:
                    subprocess.run(
                        cmd,
                        check=True,
                    )

            try:
                local_msg = rerender_local(
                    os.path.join(
                        tmpdir_local, "conda-forge-feedstock-check-solvable-feedstock"
                    ),
                    **rrnd_kwargs,
                )
            finally:
                local_captured = capfd.readouterr()
                print(f"out: {local_captured.out}\nerr: {local_captured.err}")

            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                assert os.path.exists(".azure-pipelines/azure-pipelines-linux.yml")

        if not use_exclusive_config_file:
            assert (
                msg.split("conda-forge-pinning")[1]
                == local_msg.split("conda-forge-pinning")[1]
            )
        else:
            assert "conda-forge-pinning" not in msg
            assert "conda-forge-pinning" not in local_msg
            assert msg == local_msg

        # now compare files
        cont_fnames = set(
            glob.glob(os.path.join(tmpdir_cont, "**", "*"), recursive=True)
        )
        local_fnames = set(
            glob.glob(os.path.join(tmpdir_local, "**", "*"), recursive=True)
        )

        rel_cont_fnames = {os.path.relpath(fname, tmpdir_cont) for fname in cont_fnames}
        rel_local_fnames = {
            os.path.relpath(fname, tmpdir_local) for fname in local_fnames
        }
        assert rel_cont_fnames == rel_local_fnames, (
            f"{rel_cont_fnames} != {rel_local_fnames}"
        )

        for cfname in cont_fnames:
            lfname = os.path.join(tmpdir_local, os.path.relpath(cfname, tmpdir_cont))
            if not os.path.isdir(cfname):
                with open(cfname, "rb") as f:
                    cdata = f.read()
                with open(lfname, "rb") as f:
                    ldata = f.read()
                assert cdata == ldata, f"{cfname} not equal to local"


@skipif_no_containers
def test_rerender_containerized_same_as_local_pinnings(use_containers, capfd):
    with (
        tempfile.TemporaryDirectory() as tmpdir_cont,
        tempfile.TemporaryDirectory() as tmpdir_local,
    ):
        assert tmpdir_cont != tmpdir_local

        with pushd(tmpdir_cont):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/conda-forge/conda-forge-pinning-feedstock.git",
                ]
            )
            # make sure rerender happens
            with pushd("conda-forge-pinning-feedstock"):
                cmds = [
                    ["git", "rm", "-f", ".gitignore"],
                    ["git", "rm", "-rf", ".scripts"],
                    ["git", "rm", "-f", ".github/workflows/conda-build.yml"],
                    ["git", "config", "user.email", "conda@conda.conda"],
                    ["git", "config", "user.name", "conda c. conda"],
                    ["git", "commit", "-m", "test commit"],
                ]
                for cmd in cmds:
                    subprocess.run(
                        cmd,
                        check=True,
                    )

            try:
                msg = rerender_containerized(
                    os.path.join(tmpdir_cont, "conda-forge-pinning-feedstock"),
                )
            finally:
                captured = capfd.readouterr()
                print(f"out: {captured.out}\nerr: {captured.err}")

            if "git commit -m " in captured.err:
                assert msg is not None, (
                    f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
                )
                assert msg.startswith("MNT:"), (
                    f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
                )
                with pushd("conda-forge-pinning-feedstock"):
                    assert os.path.exists(".github/workflows/conda-build.yml")
            else:
                assert msg is None, (
                    f"msg: {msg}\nout: {captured.out}\nerr: {captured.err}"
                )

        with pushd(tmpdir_local):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/conda-forge/conda-forge-pinning-feedstock.git",
                ]
            )
            # make sure rerender happens
            with pushd("conda-forge-pinning-feedstock"):
                cmds = [
                    ["git", "rm", "-f", ".gitignore"],
                    ["git", "rm", "-rf", ".scripts"],
                    ["git", "rm", "-f", ".github/workflows/conda-build.yml"],
                    ["git", "config", "user.email", "conda@conda.conda"],
                    ["git", "config", "user.name", "conda c. conda"],
                    ["git", "commit", "-m", "test commit"],
                ]
                for cmd in cmds:
                    subprocess.run(
                        cmd,
                        check=True,
                    )

            try:
                local_msg = rerender_local(
                    os.path.join(tmpdir_local, "conda-forge-pinning-feedstock"),
                )
            finally:
                local_captured = capfd.readouterr()
                print(f"out: {local_captured.out}\nerr: {local_captured.err}")

            with pushd("conda-forge-pinning-feedstock"):
                assert os.path.exists(".github/workflows/conda-build.yml")

        assert (
            msg.split("conda-forge-pinning")[1]
            == local_msg.split("conda-forge-pinning")[1]
        )

        # now compare files
        cont_fnames = set(
            glob.glob(os.path.join(tmpdir_cont, "**", "*"), recursive=True)
        )
        local_fnames = set(
            glob.glob(os.path.join(tmpdir_local, "**", "*"), recursive=True)
        )

        rel_cont_fnames = {os.path.relpath(fname, tmpdir_cont) for fname in cont_fnames}
        rel_local_fnames = {
            os.path.relpath(fname, tmpdir_local) for fname in local_fnames
        }
        assert rel_cont_fnames == rel_local_fnames, (
            f"{rel_cont_fnames} != {rel_local_fnames}"
        )

        for cfname in cont_fnames:
            lfname = os.path.join(tmpdir_local, os.path.relpath(cfname, tmpdir_cont))
            if not os.path.isdir(cfname):
                with open(cfname, "rb") as f:
                    cdata = f.read()
                with open(lfname, "rb") as f:
                    ldata = f.read()
                assert cdata == ldata, f"{cfname} not equal to local"


@skipif_no_containers
def test_rerender_containerized_empty(use_containers):
    with tempfile.TemporaryDirectory() as tmpdir_local:
        # first run the rerender locally
        with pushd(tmpdir_local):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/conda-forge/conda-forge-feedstock-check-solvable-feedstock.git",
                ]
            )
            # make sure rerender happens
            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                cmds = [
                    ["git", "rm", "-f", ".gitignore"],
                    ["git", "rm", "-rf", ".scripts"],
                    ["git", "rm", "-f", ".azure-pipelines/azure-pipelines-linux.yml"],
                    ["git", "config", "user.email", "conda@conda.conda"],
                    ["git", "config", "user.name", "conda c. conda"],
                    ["git", "commit", "-m", "test commit"],
                ]
                for cmd in cmds:
                    subprocess.run(
                        cmd,
                        check=True,
                    )

            local_msg = rerender_local(
                os.path.join(
                    tmpdir_local, "conda-forge-feedstock-check-solvable-feedstock"
                ),
            )

            assert local_msg is not None
            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                subprocess.run(
                    ["git", "commit", "-am", local_msg],
                    check=True,
                )

        # now run in container and make sure commit message is None
        msg = rerender_containerized(
            os.path.join(
                tmpdir_local, "conda-forge-feedstock-check-solvable-feedstock"
            ),
        )

        assert msg is None


@skipif_no_containers
def test_rerender_containerized_permissions(use_containers):
    with tempfile.TemporaryDirectory() as tmpdir:
        with pushd(tmpdir):
            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/conda-forge/conda-forge-feedstock-check-solvable-feedstock.git",
                ]
            )

            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                orig_perms_bl = os.stat("build-locally.py").st_mode
                print(
                    f"\n\ncloned permissions for build-locally.py: {orig_perms_bl:#o}\n\n"
                )
                orig_perms_bs = os.stat(".scripts/build_steps.sh").st_mode
                print(
                    f"\n\ncloned permissions for .scripts/build_steps.sh: {orig_perms_bs:#o}\n\n"
                )
                orig_exec = get_user_execute_permissions(".")

            local_msg = rerender_local(
                os.path.join(tmpdir, "conda-forge-feedstock-check-solvable-feedstock"),
            )

            if local_msg is not None:
                with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                    cmds = [
                        ["git", "config", "user.email", "conda@conda.conda"],
                        ["git", "config", "user.name", "conda c. conda"],
                        ["git", "commit", "-am", local_msg],
                    ]
                    for cmd in cmds:
                        subprocess.run(cmd, check=True)

            # now change permissions
            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                orig_perms_bl = os.stat("build-locally.py").st_mode
                print(
                    f"\n\ninput permissions for build-locally.py: {orig_perms_bl:#o}\n\n"
                )
                orig_perms_bs = os.stat(".scripts/build_steps.sh").st_mode
                print(
                    f"\n\ninput permissions for .scripts/build_steps.sh: {orig_perms_bs:#o}\n\n"
                )
                local_rerend_exec = get_user_execute_permissions(".")

                cmds = [
                    ["chmod", "600", "build-locally.py"],
                    ["git", "rm", "-f", ".scripts/build_steps.sh"],
                    ["git", "add", "build-locally.py"],
                    ["git", "config", "user.email", "conda@conda.conda"],
                    ["git", "config", "user.name", "conda c. conda"],
                    ["git", "commit", "-m", "test commit for rerender"],
                ]
                for cmd in cmds:
                    subprocess.run(
                        cmd,
                        check=True,
                    )

            msg = rerender_containerized(
                os.path.join(tmpdir, "conda-forge-feedstock-check-solvable-feedstock"),
            )
            assert msg is not None

            with pushd("conda-forge-feedstock-check-solvable-feedstock"):
                perms_bl = os.stat("build-locally.py").st_mode
                print(f"\n\nfinal permissions for build-locally.py: {perms_bl:#o}\n\n")
                perms_bs = os.stat(".scripts/build_steps.sh").st_mode
                print(
                    f"\n\nfinal permissions for .scripts/build_steps.sh: {perms_bs:#o}\n\n"
                )
                cont_rerend_exec = get_user_execute_permissions(".")

            assert orig_exec == local_rerend_exec
            assert orig_exec == cont_rerend_exec
