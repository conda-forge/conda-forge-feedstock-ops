import os

from conftest import skipif_no_containers

from conda_forge_feedstock_ops.lint import lint


def test_lint_local():
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data")
    lints, hints, errors = lint(
        feedstock_dir,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0
    all_keys = set(lints.keys()) | set(hints.keys()) | set(errors.keys())
    assert all_keys == {
        "hpp-fcl-feedstock/recipe/meta.yaml",
        "biopython-feedstock/recipe/meta.yaml",
        "pandas-feedstock/recipe/meta.yaml",
        "guiqwt-feedstock/recipe/meta.yaml",
        "r-base-feedstock/recipe/meta.yaml",
        "v1-unsolvable-feedstock/recipe/recipe.yaml",
        "llvmdev-feedstock/recipe/meta.yaml",
        "ngmix-blah/recipe/meta.yaml",
    }
    assert not any(err for err in errors.values())


@skipif_no_containers
def test_lint_container(use_containers):
    feedstock_dir = os.path.join(os.path.dirname(__file__), "data")
    lints, hints, errors = lint(
        feedstock_dir,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0
    all_keys = set(lints.keys()) | set(hints.keys()) | set(errors.keys())
    assert all_keys == {
        "hpp-fcl-feedstock/recipe/meta.yaml",
        "biopython-feedstock/recipe/meta.yaml",
        "pandas-feedstock/recipe/meta.yaml",
        "guiqwt-feedstock/recipe/meta.yaml",
        "r-base-feedstock/recipe/meta.yaml",
        "v1-unsolvable-feedstock/recipe/recipe.yaml",
        "llvmdev-feedstock/recipe/meta.yaml",
        "ngmix-blah/recipe/meta.yaml",
    }
    assert not any(err for err in errors.values())
