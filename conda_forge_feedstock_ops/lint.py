import logging
from collections import defaultdict
from pathlib import Path

import conda_smithy.lint_recipe

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR
from conda_forge_feedstock_ops.container_utils import (
    get_default_log_level_args,
    run_container_operation,
    should_use_container,
)
from conda_forge_feedstock_ops.json import loads
from conda_forge_feedstock_ops.virtual_mounts_host import VirtualMount

logger = logging.getLogger(__name__)


def lint(feedstock_dir, use_container=None):
    """Lint all of the recipes in a feedstock.

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.
    use_container
        Whether to use a container to run the parse.
        If None, the function will use a container if the environment
        variable `CF_FEEDSTOCK_OPS_IN_CONTAINER` is 'false'. This feature can be
        used to avoid container in container calls.

    Returns
    -------
    lints : dict
        Dictionary mapping relative recipe path to its lints.
    hints : dict
        Dictionary mapping relative recipe path to its hints.
    errors : dict
        Dictionary mapping relative recipe path to whether an error occurred
        while linting the recipe.
    """
    if should_use_container(use_container=use_container):
        return _lint_containerized(feedstock_dir)
    else:
        return _lint_local(feedstock_dir)


def _lint_containerized(feedstock_dir: str):
    feedstock_dir = Path(feedstock_dir)
    args = [
        "conda-forge-feedstock-ops-container",
        "lint",
    ] + get_default_log_level_args(logger)

    data = run_container_operation(
        args=args,
        extra_mounts=[
            VirtualMount(
                host_path=feedstock_dir,
                container_path=CF_FEEDSTOCK_OPS_DIR / feedstock_dir.name,
                read_only=False,
            )
        ],
        json_loads=loads,
    )

    return data["lints"], data["hints"], data["errors"]


#############################################################
# This code is from conda-forge-webservices w/ modifications


def _find_recipes(path: Path) -> list[Path]:
    """Returns all `meta.yaml` and `recipe.yaml` files in the given path."""
    meta_yamls = path.rglob("meta.yaml")
    recipe_yamls = path.rglob("recipe.yaml")

    return sorted(set([x for x in (list(meta_yamls) + list(recipe_yamls))]))


def _lint_local(feedstock_dir):
    recipes = _find_recipes(Path(feedstock_dir))

    lints = defaultdict(list)
    hints = defaultdict(list)
    errors = {}

    for recipe in recipes:
        recipe_dir = recipe.parent
        rel_path = str(recipe.relative_to(feedstock_dir))

        try:
            _lints, _hints = conda_smithy.lint_recipe.main(
                str(recipe_dir), conda_forge=True, return_hints=True
            )
            _error = False
        except Exception as e:
            logger.error("Error linting recipe %s", recipe, exc_info=e)
            _lints = []
            _hints = []
            _error = True

        lints[rel_path] = _lints
        hints[rel_path] = _hints
        errors[rel_path] = _error

    return dict(lints), dict(hints), errors


# end of code from conda-forge-webservices w/ modifications
#############################################################
