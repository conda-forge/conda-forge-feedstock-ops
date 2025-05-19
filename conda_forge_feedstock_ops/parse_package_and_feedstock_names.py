import glob
import logging
import os
from pathlib import Path

import conda_build.api
import conda_build.config
import rattler_build_conda_compat.render
from conda_build.metadata import MetaData
from conda_build.variants import combine_specs, parse_config_file
from conda_smithy.utils import get_feedstock_name_from_meta
from rattler_build_conda_compat.render import MetaData as RattlerBuildMetaData
from yaml import safe_load

from conda_forge_feedstock_ops import CF_FEEDSTOCK_OPS_DIR
from conda_forge_feedstock_ops.container_utils import (
    get_default_log_level_args,
    run_container_operation,
    should_use_container,
)
from conda_forge_feedstock_ops.json import loads
from conda_forge_feedstock_ops.os_utils import override_env
from conda_forge_feedstock_ops.virtual_mounts_host import VirtualMount

logger = logging.getLogger(__name__)
CONDA_BUILD = "conda-build"
RATTLER_BUILD = "rattler-build"


def parse_package_and_feedstock_names(feedstock_dir, use_container=None):
    """Parse the output package names and name of a feedstock.

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
    feedstock_name: str
        The name of the feedstock.
    package_names: set
        The built package names.
    subdirs: set
        The built package subdirs.
    """
    if should_use_container(use_container=use_container):
        return _parse_package_and_feedstock_names_containerized(feedstock_dir)
    else:
        return _parse_package_and_feedstock_names_local(feedstock_dir)


def _parse_package_and_feedstock_names_containerized(feedstock_dir: str):
    feedstock_dir = Path(feedstock_dir)
    args = [
        "conda-forge-feedstock-ops-container",
        "parse-package-and-feedstock-names",
    ] + get_default_log_level_args(logger)

    data = run_container_operation(
        args,
        extra_mounts=[
            VirtualMount(
                host_path=feedstock_dir,
                container_path=CF_FEEDSTOCK_OPS_DIR / feedstock_dir.name,
                read_only=False,
            )
        ],
        json_loads=loads,
    )

    return data["feedstock_name"], data["package_names"], data["subdirs"]


def _parse_package_and_feedstock_names_local(feedstock_dir):
    build_tool = _determine_build_tool(feedstock_dir)
    variants = glob.glob(os.path.join(feedstock_dir, ".ci_support", "*.yaml"))
    variants_by_platform_arch = _variants_by_platform_arch(variants)
    recipe_dir = os.path.join(feedstock_dir, "recipe")
    feedstock_name = _get_feedstock_name_from_feedstock(feedstock_dir)

    package_names = set()
    subdirs = set()
    for platform_arch, variants in variants_by_platform_arch.items():
        with override_env("CONDA_SUBDIR", platform_arch):
            _package_names, _subdirs = _get_built_distribution_names_and_subdirs(
                recipe_dir, variants, build_tool=build_tool
            )
            package_names |= _package_names
            subdirs |= _subdirs

    return feedstock_name, package_names, subdirs


def _variants_by_platform_arch(variants):
    variants_by_platform_arch = {}
    for variant in variants:
        platform_arch = "-".join(os.path.basename(variant).split("_")[:2])
        if platform_arch not in variants_by_platform_arch:
            variants_by_platform_arch[platform_arch] = []
        variants_by_platform_arch[platform_arch].append(variant)

    return variants_by_platform_arch


def _get_feedstock_name_from_feedstock(feedstock_dir):
    recipe_dir = os.path.join(feedstock_dir, "recipe")
    build_tool = _determine_build_tool(feedstock_dir)

    if build_tool == CONDA_BUILD:
        return get_feedstock_name_from_meta(MetaData(recipe_dir))
    else:
        return get_feedstock_name_from_meta(RattlerBuildMetaData(recipe_dir))


#############################################################
# these functions are pulled out of conda-forge-ci-setup


def _determine_build_tool(feedstock_root):
    build_tool = CONDA_BUILD

    if feedstock_root and os.path.exists(
        os.path.join(feedstock_root, "conda-forge.yml")
    ):
        with open(os.path.join(feedstock_root, "conda-forge.yml")) as f:
            conda_forge_config = safe_load(f)

            if conda_forge_config.get("conda_build_tool", CONDA_BUILD) == RATTLER_BUILD:
                build_tool = RATTLER_BUILD

    return build_tool


def _get_built_distribution_names_and_subdirs(
    recipe_dir, variant, build_tool=CONDA_BUILD
):
    additional_config = {}
    for v in variant:
        variant_dir, base_name = os.path.split(v)
        clobber_file = os.path.join(variant_dir, "clobber_" + base_name)
        if os.path.exists(clobber_file):
            additional_config = {"clobber_sections_file": clobber_file}
            break

    if build_tool == RATTLER_BUILD:
        # cribbed from conda_forge_ci_setup.utils
        # some conda-build magic here
        with open(variant[-1]) as f:
            final_variant = safe_load(f)
        if "target_platform" in final_variant:
            target_platform = final_variant["target_platform"][0]
            if target_platform != "noarch":
                platform, arch = target_platform.split("-")
                additional_config["platform"] = platform
                additional_config["arch"] = arch

        config = conda_build.config.Config(**additional_config)

        specs = {}
        for _variant_fname in variant:
            specs[_variant_fname] = parse_config_file(_variant_fname, config)
        variants = combine_specs(specs, log_output=False)
        metas = rattler_build_conda_compat.render.render(
            recipe_dir,
            variants=variants,
            finalize=False,
            bypass_env_check=True,
            config=config,
        )
    else:
        metas = conda_build.api.render(
            recipe_dir,
            variant_config_files=variant,
            finalize=False,
            bypass_env_check=True,
            **additional_config,
        )

    # Print the skipped distributions
    skipped_distributions = [m for m, _, _ in metas if m.skip()]
    for m in skipped_distributions:
        print(f"{m.name()} configuration was skipped in build/skip.")

    subdirs = set([m.config.target_subdir for m, _, _ in metas if not m.skip()])
    return set([m.name() for m, _, _ in metas if not m.skip()]), subdirs


# end of functions from conda-forge-ci-setup
#############################################################
