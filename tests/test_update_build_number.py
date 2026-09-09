"""
Code from conda-forge-bot under BSD-3-Clause

  https://github.com/conda-forge/conda-forge-bot/blob/main/License

with modifications.
"""

import pytest

from conda_forge_feedstock_ops.update_build_number import update_build_number


@pytest.mark.parametrize(
    "meta_yaml,new_meta_yaml",
    [
        ("  number: 2", "  number: 0\n"),
        ("    number: 2", "    number: 0\n"),
        ("{% set build_number = 2 %}", "{% set build_number = 0 %}\n"),
        ("{% set build = 2 %}", "{% set build = 0 %}\n"),
    ],
)
def test_update_build_number_v0(meta_yaml, new_meta_yaml, tmp_path):
    filename = tmp_path / "meta.yaml"
    filename.write_text(meta_yaml)
    did_update = update_build_number(filename, 0)
    assert did_update
    out_meta_yaml = filename.read_text()
    assert out_meta_yaml == new_meta_yaml


@pytest.mark.parametrize(
    "meta_yaml,new_meta_yaml",
    [
        ("  number: 2", "  number: 3\n"),
        ("    number: 2", "    number: 3\n"),
        ("{% set build_number = 2 %}", "{% set build_number = 3 %}\n"),
        ("{% set build = 2 %}", "{% set build = 3 %}\n"),
    ],
)
def test_update_build_number_v0_function(meta_yaml, new_meta_yaml, tmp_path):
    filename = tmp_path / "meta.yaml"
    filename.write_text(meta_yaml)
    did_update = update_build_number(filename, lambda x: x + 1)
    assert did_update
    out_meta_yaml = filename.read_text()
    assert out_meta_yaml == new_meta_yaml


@pytest.mark.parametrize(
    "meta_yaml,new_meta_yaml,did_update",
    [
        ("build:\n  number: 2", "build:\n  number: 0\n", True),
        (
            "outputs:\n  - build:\n      number: 2\n",
            "outputs:\n  - build:\n      number: 0\n",
            True,
        ),
        ("context:\n  build_number: 2\n", "context:\n  build_number: 0\n", True),
        ("context:\n  build: 2\n", "context:\n  build: 0\n", True),
        (
            "context:\n  build_num: 2\nbuild:\n  number: ${{ build_num }}\n",
            "context:\n  build_num: 0\nbuild:\n  number: ${{ build_num }}\n",
            True,
        ),
        (
            "context:\n  build_nu: 2\nbuild:\n  number: ${{ build_num }}\n",
            "context:\n  build_nu: 2\nbuild:\n  number: ${{ build_num }}\n",
            False,
        ),
    ],
)
def test_update_build_number_v1(meta_yaml, new_meta_yaml, did_update, tmp_path):
    filename = tmp_path / "recipe.yaml"
    filename.write_text(meta_yaml)
    actual_did_update = update_build_number(filename, 0)
    assert did_update is actual_did_update
    out_meta_yaml = filename.read_text()
    assert out_meta_yaml == new_meta_yaml


@pytest.mark.parametrize(
    "meta_yaml,new_meta_yaml",
    [
        ("build:\n  number: 2", "build:\n  number: 3\n"),
        (
            "outputs:\n  - build:\n      number: 2\n",
            "outputs:\n  - build:\n      number: 3\n",
        ),
        ("context:\n  build_number: 2\n", "context:\n  build_number: 3\n"),
        ("context:\n  build: 2\n", "context:\n  build: 3\n"),
    ],
)
def test_update_build_number_v1_function(meta_yaml, new_meta_yaml, tmp_path):
    filename = tmp_path / "recipe.yaml"
    filename.write_text(meta_yaml)
    did_update = update_build_number(filename, lambda x: x + 1)
    assert did_update
    out_meta_yaml = filename.read_text()
    assert out_meta_yaml == new_meta_yaml
