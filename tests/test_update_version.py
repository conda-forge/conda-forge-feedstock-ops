"""
Code from conda-forge-bot under BSD-3-Clause

  https://github.com/conda-forge/conda-forge-bot/blob/main/License

with modifications.
"""

import glob
import os
import re
import tempfile

import pytest
from conftest import skipif_no_containers

from conda_forge_feedstock_ops.update_build_number import update_build_number
from conda_forge_feedstock_ops.update_version import update_version

V0_VERSION_RE = re.compile(r"\{}")

YAML_PATH_V0 = os.path.join(
    os.path.dirname(__file__),
    "data",
    "update_version_tests",
    "v0_yaml",
)


def _collect_all_v0_recipe_info():
    fnames = sorted(
        list(glob.glob(os.path.join(YAML_PATH_V0, "version_*_correct.yaml")))
    )
    for fname in fnames:
        ver = None
        with open(fname) as fp:
            for line in fp.readlines():
                if line.startswith('{% set version = "'):
                    ver = (
                        line.strip()
                        .replace('{% set version = "', "")
                        .replace('" %}', "")
                    )
                    break

        if ver is None:
            raise RuntimeError(f"Could not parse version from file {fname}!")

        fs_name = os.path.basename(fname)[len("version_") : -len("_correct.yaml")]
        if fs_name == "cb3multi":
            yval = pytest.param(
                fs_name, ver, marks=[pytest.mark.xfail(reason="pypy sources moved!")]
            )
        elif fs_name == "mumps":
            yval = pytest.param(
                fs_name, ver, marks=[pytest.mark.xfail(reason="mumps sources moved!")]
            )
        elif fs_name in [
            "polars_mixed_selectors",
            "polars_name_selectors",
            "polars_variant_selectors",
        ]:
            yval = pytest.param(
                fs_name,
                ver,
                marks=[
                    pytest.mark.xfail(
                        reason="Variants depending on selectors are not supported!"
                    )
                ],
            )
        else:
            yval = pytest.param(fs_name, ver)

        yield yval


@pytest.mark.parametrize(
    "fs_name,version",
    sorted(list(_collect_all_v0_recipe_info()), key=lambda x: x[0]),
)
@pytest.mark.parametrize(
    "use_container",
    [
        False,
        pytest.param(True, marks=[skipif_no_containers]),
    ],
)
def test_update_version_update_version_v0_local(fs_name, version, use_container):
    with tempfile.TemporaryDirectory() as tmpdir:
        no_up_tuples = [
            ("badvernoup", "10.12.0"),
            ("selshaurlnoup", "3.8.0"),
            ("missingjinja2noup", "7.8.0"),
            ("nouphasurl", "3.11.3"),
            ("giturl", "7.0"),
        ]

        for _fs_name, _ver in no_up_tuples:
            if fs_name == _fs_name:
                version = _ver
                break

        fs_dir = os.path.join(tmpdir, f"{fs_name}-feedstock")
        rp_dir = os.path.join(fs_dir, "recipe")
        os.makedirs(rp_dir, exist_ok=True)
        with open(os.path.join(rp_dir, "meta.yaml"), "w") as f:
            with open(os.path.join(YAML_PATH_V0, f"version_{fs_name}.yaml")) as fp:
                f.write(fp.read())

        updated, errors = update_version(
            fs_dir,
            version,
            use_container=use_container,
        )

        if fs_name in [nutp[0] for nutp in no_up_tuples]:
            assert not updated, errors
            assert len(errors) > 0
        else:
            assert updated, errors
            assert not errors, errors
            update_build_number(os.path.join(rp_dir, "meta.yaml"), 0)

        with open(os.path.join(rp_dir, "meta.yaml")) as f:
            actual_output = f.read()

        with open(os.path.join(YAML_PATH_V0, f"version_{fs_name}_correct.yaml")) as fp:
            output = fp.read()

        assert actual_output == output
