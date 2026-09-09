"""
Code from conda-forge-bot

  https://github.com/conda-forge/conda-forge-bot/blob/main/conda_forge_tick/update_recipe/v1_recipe/build_number.py
  https://github.com/conda-forge/conda-forge-bot/blob/main/conda_forge_tick/update_recipe/build_number.py

under BSD-3-Clause

  https://github.com/conda-forge/conda-forge-bot/blob/main/License

with modifications.
"""

from __future__ import annotations

import copy
import os
import re
from collections.abc import Callable
from typing import Any

from conda_forge_feedstock_ops.yaml import get_yaml_parser

RE_PATTERN = re.compile(r"(?:build|build_number|number):\s*(\d+)")
DEFAULT_BUILD_PATTERNS = (
    (re.compile(r"(\s*?)number:\s*([0-9]+)"), "number: {}"),
    (
        re.compile(r'(\s*?){%\s*set build_number\s*=\s*"?([0-9]+)"?\s*%}'),
        "{{% set build_number = {} %}}",
    ),
    (
        re.compile(r'(\s*?){%\s*set build\s*=\s*"?([0-9]+)"?\s*%}'),
        "{{% set build = {} %}}",
    ),
)


def _old_build_number(recipe_text: str) -> int:
    match = re.search(RE_PATTERN, recipe_text)
    if match is not None:
        return int(match.group(1))
    return 0


def _update_build_number_in_context(
    recipe: dict[str, Any], new_build_number: int
) -> bool:
    is_modified = False
    for key in recipe.get("context", {}):
        if key in {"build_number", "build", "number", "build_num"}:
            recipe["context"][key] = new_build_number
            is_modified = True
    return is_modified


def _update_build_number_in_recipe(
    recipe: dict[str, Any], new_build_number: int
) -> bool:
    is_modified = False
    if "build" in recipe and "number" in recipe["build"]:
        try:
            int(recipe["build"]["number"])
        except Exception:
            pass
        else:
            recipe["build"]["number"] = new_build_number
            is_modified = True

    if "outputs" in recipe:
        for output in recipe["outputs"]:
            if "build" in output and "number" in output["build"]:
                try:
                    int(output["build"]["number"])
                except Exception:
                    pass
                else:
                    output["build"]["number"] = new_build_number
                    is_modified = True

    return is_modified


def update_build_number_v1(filename: str, new_build_number: int | Callable = 0) -> bool:
    """
    Update the build number in the recipe file for a v1 recipe.

    Parameters
    ----------
    filename
        The path to the recipe file.
    new_build_number
        The new build number to use. If a function, accepts the old build number
        and should produce a new one.

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


def update_build_number_v0(filename: str, new_build_number: int | Callable = 0) -> bool:
    """Update the build number for a v0 recipe.

    Parameters
    ----------
    filename
        The path to the recipe file.
    new_build_number
        The new build number to use. If a function, accepts the old build number
        and should produce a new one.

    Returns
    -------
    updated
        If `True`, the recipe was updated. `False` otherwise.
    """
    build_patterns = DEFAULT_BUILD_PATTERNS

    with open(filename) as fp:
        raw_meta_yaml = fp.read()

    orig_raw_meta_yaml = copy.copy(raw_meta_yaml)

    for p, n in build_patterns:
        lines = raw_meta_yaml.splitlines()
        for i, line in enumerate(lines):
            m = p.match(line)
            if m is not None:
                old_build_number = int(m.group(2))
                if callable(new_build_number):
                    _new_build_number = new_build_number(old_build_number)
                else:
                    _new_build_number = new_build_number
                lines[i] = m.group(1) + n.format(_new_build_number)
        raw_meta_yaml = "\n".join(lines) + "\n"

    if raw_meta_yaml != orig_raw_meta_yaml:
        update_recipe = True
        with open(filename, "w") as fp:
            fp.write(raw_meta_yaml)
    else:
        update_recipe = False

    return update_recipe


def update_build_number(filename: str, new_build_number: int | Callable = 0) -> bool:
    """Update the build number for a recipe.

    Parameters
    ----------
    filename
        The path to the recipe file.
    new_build_number
        The new build number to use. If a function, accepts the old build number
        and should produce a new one.

    Returns
    -------
    updated
        If `True`, the recipe was updated. `False` otherwise.
    """

    if os.path.basename(filename) == "meta.yaml":
        return update_build_number_v0(filename, new_build_number)
    elif os.path.basename(filename) == "recipe.yaml":
        return update_build_number_v1(filename, new_build_number)
    else:
        raise RuntimeError(
            "Could not determine recipe type for file "
            "`{filename}` when updating build number!"
        )
