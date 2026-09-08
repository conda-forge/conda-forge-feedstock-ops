"""
Code from conda-forge-bot under BSD-3-Clause

  https://github.com/conda-forge/conda-forge-bot/blob/main/License

with modifications.
"""

import copy
import glob
import itertools
import os
import tempfile

import pytest
from conftest import skipif_no_containers

from conda_forge_feedstock_ops.update_build_number import update_build_number
from conda_forge_feedstock_ops.update_version import update_version
from conda_forge_feedstock_ops.yaml import get_yaml_parser

YAML_PATH_V0 = os.path.join(
    os.path.dirname(__file__),
    "data",
    "update_version_tests",
    "v0_yaml",
)

YAML_PATH_V1 = os.path.join(
    os.path.dirname(__file__),
    "data",
    "update_version_tests",
    "v1_yaml",
)

POSSIBLE_V0_REPLACEMENTS = {
    "multisrclist": [
        {
            "- url: https://mirrors.edge.kernel.org/pub/software/scm/git/git-{{ version }}.tar.gz  # [not win]": "- url: https://mirrors.edge.kernel.org/pub/software/scm/git/git-{{ version }}.tar.xz  # [not win]",
            "sha256: a98c9b96d91544b130f13bf846ff080dda2867e77fe08700b793ab14ba5346f6  # [not win]": "sha256: c060291a3ffb43d7c99f4aa5c4d37d3751cf6bca683e7344ea407ea504d9a8d0  # [not win]",
        },
    ]
}
POSSIBLE_V1_REPLACEMENTS = {}


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
def test_update_version_update_version_v0(fs_name, version, use_container):
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

        possible_outputs = [output]
        for rpls in POSSIBLE_V0_REPLACEMENTS.get(fs_name, []):
            possible_output = copy.copy(output)
            for k, v in rpls.items():
                possible_output = possible_output.replace(k, v)
            possible_outputs.append(possible_output)

        if not any(
            actual_output == possible_output for possible_output in possible_outputs
        ):
            assert actual_output == output


def _collect_all_v1_recipe_info():
    yaml = get_yaml_parser(typ="rt")

    fnames = sorted(
        list(glob.glob(os.path.join(YAML_PATH_V1, "version_*_correct.yaml")))
    )
    for fname in fnames:
        ver = None
        with open(fname) as fp:
            data = yaml.load(fp.read())

        if "context" in data and "version" in data["context"]:
            ver = str(data["context"]["version"])

        if ver is None:
            raise RuntimeError(f"Could not parse version from file {fname}!")

        fs_name = os.path.basename(fname)[len("version_") : -len("_correct.yaml")]
        if fs_name == "libssh":
            yval = pytest.param(
                fs_name,
                ver,
                marks=pytest.mark.xfail(reason="libssh urls tend to error a lot"),
            )
        else:
            yval = pytest.param(fs_name, ver)

        yield yval


@pytest.mark.parametrize(
    "fs_name,version",
    sorted(list(_collect_all_v1_recipe_info()), key=lambda x: x[0]),
)
@pytest.mark.parametrize(
    "use_container",
    [
        False,
        pytest.param(True, marks=[skipif_no_containers]),
    ],
)
def test_update_version_update_version_v1(fs_name, version, use_container):
    yaml = get_yaml_parser(typ="rt")

    with tempfile.TemporaryDirectory() as tmpdir:
        fs_dir = os.path.join(tmpdir, f"{fs_name}-feedstock")
        rp_dir = os.path.join(fs_dir, "recipe")
        os.makedirs(rp_dir, exist_ok=True)
        with open(os.path.join(rp_dir, "recipe.yaml"), "w") as f:
            with open(os.path.join(YAML_PATH_V1, f"version_{fs_name}.yaml")) as fp:
                f.write(fp.read())

            variants_pth = os.path.join(
                YAML_PATH_V1, f"version_{fs_name}_variants.yaml"
            )
            os.makedirs(os.path.join(fs_dir, ".ci_support"), exist_ok=True)

            if os.path.exists(variants_pth):
                with open(variants_pth) as fp:
                    cbc_text = fp.read()

                with open(os.path.join(rp_dir, "conda_build_config.yaml"), "w") as fp:
                    fp.write(cbc_text)

                build_variants = yaml.load(cbc_text)
            else:
                build_variants = {}

            if "target_platform" not in build_variants:
                build_variants["target_platform"] = ["linux-64", "osx-arm64", "win-64"]

            # move target_platform to the beginning of the keys
            build_variants = {
                "target_platform": build_variants.pop("target_platform"),
                **build_variants,
            }

            for assignment in itertools.product(*build_variants.values()):
                assignment_map = dict(zip(build_variants.keys(), assignment))
                variant_name = "_".join(
                    str(value).replace("-", "_").replace("/", "")
                    for value in assignment_map.values()
                )
                var_pth = os.path.join(fs_dir, ".ci_support", f"{variant_name}_.yaml")
                with open(var_pth, "w") as fp:
                    yaml.dump({k: [v] for k, v in assignment_map.items()}, fp)

        updated, errors = update_version(
            fs_dir,
            version,
            use_container=use_container,
        )

        assert updated, errors
        assert not errors, errors
        update_build_number(os.path.join(rp_dir, "recipe.yaml"), 0)

        with open(os.path.join(rp_dir, "recipe.yaml")) as f:
            actual_output = f.read()

        with open(os.path.join(YAML_PATH_V1, f"version_{fs_name}_correct.yaml")) as fp:
            output = fp.read()

        possible_outputs = [output]
        for rpls in POSSIBLE_V1_REPLACEMENTS.get(fs_name, []):
            possible_output = copy.copy(output)
            for k, v in rpls.items():
                possible_output = possible_output.replace(k, v)
            possible_outputs.append(possible_output)

        if not any(
            actual_output == possible_output for possible_output in possible_outputs
        ):
            assert actual_output == output
