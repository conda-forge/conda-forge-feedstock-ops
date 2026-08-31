"""
Code from conda-forge-bot

  https://github.com/conda-forge/conda-forge-bot/blob/main/conda_forge_tick/update_recipe/v1_recipe/build_number.py

under BSD-3-Clause

  https://github.com/conda-forge/conda-forge-bot/blob/main/License

with modifications.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from conda_forge_feedstock_ops.utils import get_yaml_parser

RE_PATTERN = re.compile(r"(?:build|build_number|number):\s*(\d+)")


def _old_build_number(recipe_text: str) -> int:
    match = re.search(RE_PATTERN, recipe_text)
    if match is not None:
        return int(match.group(1))
    return 0


def _update_build_number_in_context(
    recipe: dict[str, Any], new_build_number: int
) -> bool:
    for key in recipe.get("context", {}):
        if key in {"build_number", "build", "number"}:
            recipe["context"][key] = new_build_number
            return True
    return False


def _update_build_number_in_recipe(
    recipe: dict[str, Any], new_build_number: int
) -> bool:
    is_modified = False
    if "build" in recipe and "number" in recipe["build"]:
        recipe["build"]["number"] = new_build_number
        is_modified = True

    if "outputs" in recipe:
        for output in recipe["outputs"]:
            if "build" in output and "number" in output["build"]:
                output["build"]["number"] = new_build_number
                is_modified = True

    return is_modified


def update_build_number_v1(filename: str, new_build_number: int | Callable = 0) -> bool:
    """
    Update the build number in the recipe file for a v1 recipe.

    Parameters
    ----------
    file : str
        The path to the recipe file.
    new_build_number
        The new build number to use. If a function, accepts the old build number and should produce a new one.

    Returns
    -------
    updated
        If `True`, the recipe was updated. `False` otherwise.
    """
    yaml = get_yaml_parser(typ="rt")
    with open(filename) as fp:
        recipe_text = fp.read()
    data = yaml.load(recipe_text)

    if callable(new_build_number):
        detected_build_number = _old_build_number(recipe_text)
        new_build_number = new_build_number(detected_build_number)

    build_number_modified = _update_build_number_in_context(data, new_build_number)

    if not build_number_modified:
        build_number_modified |= _update_build_number_in_recipe(data, new_build_number)

    with open(filename, "w") as fp:
        yaml.dump(data, fp)

    return build_number_modified
