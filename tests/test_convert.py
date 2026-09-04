import os
import re

import pytest
from conftest import clone_and_checkout_repo, skipif_no_containers

from conda_forge_feedstock_ops.convert import (
    convert_feedstock_to_v1_containerized,
    convert_feedstock_to_v1_local,
)
from conda_forge_feedstock_ops.utils import get_yaml_parser

PYTHON_V1_MIN_SUB_RE = re.compile(
    r"python \$\{\{\s*python_min\s*\}\}(\s|$)",
    flags=re.MULTILINE,
)

FEEDSTOCK_NAME_REF_LIST = [
    ("cf-autotick-bot-test-package", "main"),
    ("ngmix", "main"),
    ("galsim", "main"),
    ("stackvana-core", "main"),
    ("openmpi", "main"),
    ("rustfits", "main"),
    ("conda-index", "ee3e0a3a161857f9d04e9f58ae7ecc05879ea084"),
]


@pytest.mark.parametrize(
    "feedstock_name,ref",
    FEEDSTOCK_NAME_REF_LIST,
)
@skipif_no_containers
def test_convert_convert_to_v1_containerized(tmp_path, feedstock_name, ref):
    feedstock_dir = clone_and_checkout_repo(
        tmp_path,
        f"https://github.com/conda-forge/{feedstock_name}-feedstock",
        ref=ref,
    )
    recipe_yaml_pth = os.path.join(feedstock_dir, "recipe", "recipe.yaml")
    meta_yaml_pth = os.path.join(feedstock_dir, "recipe", "meta.yaml")
    cf_yaml_path = os.path.join(feedstock_dir, "conda-forge.yml")

    convert_feedstock_to_v1_containerized(feedstock_dir)
    assert os.path.exists(recipe_yaml_pth)
    assert not os.path.exists(meta_yaml_pth)
    assert os.path.exists(cf_yaml_path)

    with open(cf_yaml_path) as fp:
        cf_yaml = get_yaml_parser(typ="rt").load(fp.read())
    assert "conda_build_tool" in cf_yaml
    assert cf_yaml["conda_build_tool"] == "rattler-build"

    with open(recipe_yaml_pth) as fp:
        recipe_yaml = fp.read()
    assert not recipe_yaml.endswith("\n\n")
    if feedstock_name == "cf-autotick-bot-test-package":
        assert "number: 1" in recipe_yaml
    assert not PYTHON_V1_MIN_SUB_RE.search(recipe_yaml)


@pytest.mark.parametrize(
    "feedstock_name,ref",
    FEEDSTOCK_NAME_REF_LIST,
)
def test_convert_convert_to_v1_local(tmp_path, feedstock_name, ref):
    feedstock_dir = clone_and_checkout_repo(
        tmp_path,
        f"https://github.com/conda-forge/{feedstock_name}-feedstock",
        ref=ref,
    )
    recipe_yaml_pth = os.path.join(feedstock_dir, "recipe", "recipe.yaml")
    meta_yaml_pth = os.path.join(feedstock_dir, "recipe", "meta.yaml")
    cf_yaml_path = os.path.join(feedstock_dir, "conda-forge.yml")

    convert_feedstock_to_v1_local(feedstock_dir)
    assert os.path.exists(recipe_yaml_pth)
    assert not os.path.exists(meta_yaml_pth)
    assert os.path.exists(cf_yaml_path)

    with open(cf_yaml_path) as fp:
        cf_yaml = get_yaml_parser(typ="rt").load(fp.read())
    assert "conda_build_tool" in cf_yaml
    assert cf_yaml["conda_build_tool"] == "rattler-build"

    with open(recipe_yaml_pth) as fp:
        recipe_yaml = fp.read()
    assert not recipe_yaml.endswith("\n\n")
    if feedstock_name == "cf-autotick-bot-test-package":
        assert "number: 1" in recipe_yaml
    assert not PYTHON_V1_MIN_SUB_RE.search(recipe_yaml)

    print(recipe_yaml)


@pytest.mark.parametrize(
    "feedstock_name",
    ["conda-build", "conda-smithy"],
)
def test_convert_convert_to_v1_local_raises(tmp_path, feedstock_name):
    feedstock_dir = clone_and_checkout_repo(
        tmp_path,
        f"https://github.com/conda-forge/{feedstock_name}-feedstock",
        ref="main",
    )
    recipe_yaml_pth = os.path.join(feedstock_dir, "recipe", "recipe.yaml")
    meta_yaml_pth = os.path.join(feedstock_dir, "recipe", "meta.yaml")
    cf_yaml_path = os.path.join(feedstock_dir, "conda-forge.yml")

    with pytest.raises(RuntimeError) as exc:
        convert_feedstock_to_v1_local(feedstock_dir)

    assert not os.path.exists(recipe_yaml_pth)
    assert os.path.exists(meta_yaml_pth)
    assert os.path.exists(cf_yaml_path)

    with open(cf_yaml_path) as fp:
        cf_yaml = get_yaml_parser(typ="rt").load(fp.read())
    assert (
        "conda_build_tool" not in cf_yaml
        or "rattler-build" not in cf_yaml["conda_build_tool"]
    )

    print(exc.value)


@pytest.mark.parametrize(
    "feedstock_name",
    ["conda-build", "conda-smithy"],
)
@skipif_no_containers
def test_convert_convert_to_v1_containerized_raises(tmp_path, feedstock_name):
    feedstock_dir = clone_and_checkout_repo(
        tmp_path,
        f"https://github.com/conda-forge/{feedstock_name}-feedstock",
        ref="main",
    )
    recipe_yaml_pth = os.path.join(feedstock_dir, "recipe", "recipe.yaml")
    meta_yaml_pth = os.path.join(feedstock_dir, "recipe", "meta.yaml")
    cf_yaml_path = os.path.join(feedstock_dir, "conda-forge.yml")

    with pytest.raises(RuntimeError) as exc:
        convert_feedstock_to_v1_containerized(feedstock_dir)

    assert not os.path.exists(recipe_yaml_pth)
    assert os.path.exists(meta_yaml_pth)
    assert os.path.exists(cf_yaml_path)

    with open(cf_yaml_path) as fp:
        cf_yaml = get_yaml_parser(typ="rt").load(fp.read())
    assert (
        "conda_build_tool" not in cf_yaml
        or "rattler-build" not in cf_yaml["conda_build_tool"]
    )

    print(exc.value)
