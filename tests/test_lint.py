import os
from pathlib import Path

from conftest import skipif_no_containers

from conda_forge_feedstock_ops.lint import lint

FEEDSTOCK_DIR = os.path.join(os.path.dirname(__file__), "data")


def _expected_recipes():
    """Every recipe under tests/data, keyed the way lint() keys its results.

    Globbed here rather than listed literally so that adding a fixture does
    not also mean editing this file. The glob is deliberately a
    reimplementation rather than a call to lint's own _find_recipes, so the
    tests still catch lint() losing track of a recipe it should have found.
    """
    root = Path(FEEDSTOCK_DIR)
    recipes = list(root.rglob("meta.yaml")) + list(root.rglob("recipe.yaml"))
    assert recipes, f"no recipe fixtures found under {root}"
    return {str(recipe.relative_to(root)) for recipe in recipes}


def test_lint_local():
    lints, hints, errors = lint(
        FEEDSTOCK_DIR,
        use_container=False,
    )
    assert len(hints) + len(lints) > 0
    all_keys = set(lints.keys()) | set(hints.keys()) | set(errors.keys())
    assert all_keys == _expected_recipes()
    assert not any(err for err in errors.values())


@skipif_no_containers
def test_lint_container(use_containers):
    lints, hints, errors = lint(
        FEEDSTOCK_DIR,
        use_container=True,
    )
    assert len(hints) + len(lints) > 0
    all_keys = set(lints.keys()) | set(hints.keys()) | set(errors.keys())
    assert all_keys == _expected_recipes()
    assert not any(err for err in errors.values())
