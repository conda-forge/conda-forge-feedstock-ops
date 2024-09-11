import os

from conftest import skipif_no_containers, skipif_no_github_token

from conda_forge_feedstock_ops.lint import lint


@skipif_no_github_token
def test_lint_local():
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data")
    lints, hints = lint(
        feedstock_dir,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0
    all_keys = set(lints.keys()) | set(hints.keys())
    assert all_keys == {"llvmdev-feedstock/recipe/meta.yaml", "ngmix-blah/recipe/meta.yaml"}


@skipif_no_containers
def test_lint_container(use_containers):
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data")
    lints, hints = lint(
        feedstock_dir,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0
    all_keys = set(lints.keys()) | set(hints.keys())
    assert all_keys == {"llvmdev-feedstock/recipe/meta.yaml", "ngmix-blah/recipe/meta.yaml"}
