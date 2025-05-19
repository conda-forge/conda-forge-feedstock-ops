from pathlib import Path

import pytest

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR
from conda_forge_feedstock_ops.container_utils import (
    run_container_operation,
    should_use_container,
)
from conda_forge_feedstock_ops.os_utils import override_env
from conda_forge_feedstock_ops.virtual_mounts_host import VirtualMount


def test_should_use_container():
    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "tRue"):
        assert not should_use_container()

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false"):
        assert should_use_container()

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", None):
        assert should_use_container()

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "true"):
        assert not should_use_container(use_container=True)

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false"):
        assert should_use_container(use_container=True)

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "true"):
        assert not should_use_container(use_container=False)

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false"):
        assert not should_use_container(use_container=False)


def test_run_container_operation_overlapping_mounts():
    with pytest.raises(ValueError, match="host paths may not overlap"):
        run_container_operation(
            args=["test"],
            extra_mounts=[
                VirtualMount(Path("/host/path/subdir"), CF_FEEDSTOCK_OPS_DIR / "path1"),
                VirtualMount(Path("/host/path"), CF_FEEDSTOCK_OPS_DIR / "path2"),
            ],
        )

    with pytest.raises(ValueError, match="host paths may not overlap"):
        run_container_operation(
            args=["test"],
            extra_mounts=[
                VirtualMount(Path("/host/path"), CF_FEEDSTOCK_OPS_DIR / "path1"),
                VirtualMount(Path("/host/path"), CF_FEEDSTOCK_OPS_DIR / "path2"),
            ],
        )

    with pytest.raises(ValueError, match="container paths may not overlap"):
        run_container_operation(
            args=["test"],
            extra_mounts=[
                VirtualMount(Path("/host/path1"), CF_FEEDSTOCK_OPS_DIR / "path"),
                VirtualMount(
                    Path("/host/path2"), CF_FEEDSTOCK_OPS_DIR / "path" / "subpath"
                ),
            ],
        )

    with pytest.raises(ValueError, match="container paths may not overlap"):
        run_container_operation(
            args=["test"],
            extra_mounts=[
                VirtualMount(Path("/host/path1"), CF_FEEDSTOCK_OPS_DIR / "path"),
                VirtualMount(Path("/host/path2"), CF_FEEDSTOCK_OPS_DIR / "path"),
            ],
        )

    with pytest.raises(ValueError, match="container paths may not overlap"):
        run_container_operation(
            args=["test"],
            extra_mounts=[
                VirtualMount(
                    Path("/host/path"), CF_FEEDSTOCK_OPS_DIR / "return_info.json"
                ),
            ],
        )

    with pytest.raises(ValueError, match="container paths may not overlap"):
        run_container_operation(
            args=["test"],
            extra_mounts=[
                VirtualMount(
                    Path("/host/path"),
                    CF_FEEDSTOCK_OPS_DIR / "return_info.json" / "subdir",
                ),
            ],
        )
