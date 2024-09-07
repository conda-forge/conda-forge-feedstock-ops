import os

from conftest import skipif_no_containers

from conda_forge_feedstock_ops.parse_package_and_feedstock_names import (
    parse_package_and_feedstock_names,
)


@skipif_no_containers
def test_parse_package_and_feedstock_names_llvmdev_local():
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data", "llvmdev-feedstock")
    feedstock_name, package_names, subdirs = parse_package_and_feedstock_names(
        feedstock_dir,
        use_container=False,
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
    assert subdirs == {
        "linux-64",
        "linux-aarch64",
        "linux-ppc64le",
        "win-64",
        "osx-64",
        "osx-arm64",
    }


@skipif_no_containers
def test_parse_package_and_feedstock_names_llvmdev_container():
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data", "llvmdev-feedstock")
    feedstock_name, package_names, subdirs = parse_package_and_feedstock_names(
        feedstock_dir,
        use_container=True,
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
    assert subdirs == {
        "linux-64",
        "linux-aarch64",
        "linux-ppc64le",
        "win-64",
        "osx-64",
        "osx-arm64",
    }
