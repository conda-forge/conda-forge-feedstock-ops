import os

from conftest import skipif_no_containers, skipif_no_github_token

from conda_forge_feedstock_ops.lint import lint


@skipif_no_github_token
def test_lint_llvmdev_local():
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data", "llvmdev-feedstock")
    lints, hints = lint(
        feedstock_dir,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0


@skipif_no_containers
def test_parse_package_and_feedstock_names_llvmdev_container(use_containers):
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data", "llvmdev-feedstock")
    lints, hints = lint(
        feedstock_dir,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0
