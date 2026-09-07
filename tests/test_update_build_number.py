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
    "meta_yaml,new_meta_yaml",
    [
        ("build:\n  number: 2", "build:\n  number: 0\n"),
        (
            "outputs:\n  - build:\n      number: 2\n",
            "outputs:\n  - build:\n      number: 0\n",
        ),
        ("context:\n  build_number: 2\n", "context:\n  build_number: 0\n"),
        ("context:\n  build: 2\n", "context:\n  build: 0\n"),
    ],
)
def test_update_build_number_v1(meta_yaml, new_meta_yaml, tmp_path):
    filename = tmp_path / "recipe.yaml"
    filename.write_text(meta_yaml)
    did_update = update_build_number(filename, 0)
    assert did_update
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
