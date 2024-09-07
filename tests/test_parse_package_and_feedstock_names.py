import os

import pytest

from conda_forge_feedstock_ops.parse_package_and_feedstock_names import (
    parse_package_and_feedstock_names,
)


@pytest.mark.parametrize("use_container", [False])  # None, False, True])
def test_parse_package_and_feedstock_names_llvmdev(use_container):
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data", "llvmdev-feedstock")
    feedstock_name, package_names, subdirs = parse_package_and_feedstock_names(
        feedstock_dir, use_container=use_container
    )
    assert feedstock_name == "llvmdev"
    assert package_names == {
        "llvmdev",
        "libllvm18",
        "llvm",
        "llvm-tools-18",
        "llvm-tools",
        "libllvm-c18",
        "lit",
    }
    assert subdirs == {'linux-64', 'linux-aarch64', 'linux-ppc64le', 'win-64', 'osx-64', 'osx-arm64'}
