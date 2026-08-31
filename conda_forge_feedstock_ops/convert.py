import json
import logging
import os
import shutil
import subprocess
import tempfile

from conda_forge_feedstock_ops.container_utils import (
    get_default_log_level_args,
    run_container_operation,
    should_use_container,
)
from conda_forge_feedstock_ops.os_utils import (
    chmod_plus_rwX,
    get_user_execute_permissions,
    reset_permissions_with_user_execute,
    sync_dirs,
)
from conda_forge_feedstock_ops.utils import get_yaml_parser

logger = logging.getLogger(__name__)


def convert_feedstock_to_v1(feedstock_dir, use_container=None):
    """Convert a feedstock to the v1 recipe format.

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.
    use_container
        Whether to use a container to run the rerender.
        If None, the function will use a container if the environment
        variable `CF_FEEDSTOCK_OPS_IN_CONTAINER` is 'false'. This feature can be
        used to avoid container in container calls.

    Returns
    -------
    bool
        Return True if changes were made, False otherwise.
    """
    if should_use_container(use_container=use_container):
        return convert_feedstock_to_v1_containerized(
            feedstock_dir,
        )
    else:
        return convert_feedstock_to_v1_local(
            feedstock_dir,
        )


def convert_feedstock_to_v1_containerized(feedstock_dir):
    """Convert a feedstock to the v1 recipe format inside of a container.

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.

    Returns
    -------
    bool
        Return True if changes were made, False otherwise.
    """
    args = [
        "conda-forge-feedstock-ops-container",
        "convert-feedstock-to-v1",
    ] + get_default_log_level_args(logger)

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        tmp_feedstock_dir = os.path.join(tmpdir, os.path.basename(feedstock_dir))
        sync_dirs(
            feedstock_dir, tmp_feedstock_dir, ignore_dot_git=True, update_git=False
        )

        perms = get_user_execute_permissions(feedstock_dir)
        with open(
            os.path.join(tmpdir, f"permissions-{os.path.basename(feedstock_dir)}.json"),
            "w",
        ) as f:
            json.dump(perms, f)

        chmod_plus_rwX(tmpdir, recursive=True)

        logger.debug(
            "host feedstock dir %s: %r",
            feedstock_dir,
            os.listdir(feedstock_dir),
        )
        logger.debug(
            "copied host feedstock dir %s: %r",
            tmp_feedstock_dir,
            os.listdir(tmp_feedstock_dir),
        )

        data = run_container_operation(
            args,
            mount_readonly=False,
            mount_dir=tmpdir,
        )

        if data["patch"] is not None:
            patch_file = os.path.join(
                tmpdir, f"convert-to-v1-diff-{os.path.basename(feedstock_dir)}.patch"
            )
            with open(patch_file, "w") as fp:
                fp.write(data["patch"])
            subprocess.run(
                ["git", "apply", "--allow-empty", patch_file],
                check=True,
                cwd=feedstock_dir,
            )
            reset_permissions_with_user_execute(feedstock_dir, data["permissions"])
            subprocess.run(
                ["git", "add", "-f", "."],
                check=True,
                cwd=feedstock_dir,
            )

        # When tempfile removes tempdir, it tries to reset permissions on subdirs.
        # This causes a permission error since the subdirs were made by the user
        # in the container. So we remove the subdir we made before cleaning up.
        shutil.rmtree(tmp_feedstock_dir)

    return data["changed"]


def _post_process_returncode_and_stderr(returncode, stderr):
    deprecated_fields = [
        # about
        "prelink_message",
        "license_family",
        "identifiers",
        "tags",
        "keywords",
        "doc_source_url",
        "license_family",
        # build
        "pre-link",
        "noarch_python",
        "features",
        "msvc_compiler",
        "requires_features",
        "provides_features",
        "preferred_env",
        "preferred_env_executable_paths",
        "disable_pip",
        "pin_depends",
        "overlinking_ignore_patterns",
        # we do not ignore rpaths_patcher since this
        # change could be important, maybe?
        # "rpaths_patcher",
        "post-link",
        "pre-unlink",
        "pre-link",
    ]
    new_lines = []
    for line in stderr.splitlines():
        line = line.strip()
        # ignore field deprecations
        if any(
            f"/{df}" in line and "Field at" in line and "no longer supported"
            for df in deprecated_fields
        ):
            continue

        if (
            "Recipe upgrades cannot currently upgrade ambiguous version constraints on dependencies that use variables"
            in line
        ):
            continue

        if "The recipe parser was unable to evaluate the JINJA expression" in line:
            continue

        if "Could not patch unrecognized license" in line:
            continue

        if (
            " error" in line
            and " and " in line
            and " warning" in line
            and line.startswith("0")
        ):
            continue

        new_lines.append(line.strip())

    if not new_lines:
        return 0, stderr
    else:
        return returncode, stderr


def convert_feedstock_to_v1_local(feedstock_dir: str):
    """Convert a feedstock to the v1 recipe format.

    Parameters
    ----------
    feedstock_dir : str
        The path to the feedstock directory.

    Returns
    -------
    bool
        Return True if changes were made, False otherwise.
    """
    recipe_yaml_pth = os.path.join(feedstock_dir, "recipe", "recipe.yaml")
    meta_yaml_pth = os.path.join(feedstock_dir, "recipe", "meta.yaml")
    cf_yaml_path = os.path.join(feedstock_dir, "conda-forge.yml")

    changed = False

    if (not os.path.exists(recipe_yaml_pth)) and os.path.exists(meta_yaml_pth):
        ret = subprocess.run(
            [
                "conda-recipe-manager",
                "convert",
                "--also-test-latest-python",
                meta_yaml_pth,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        returncode, stderr = _post_process_returncode_and_stderr(
            ret.returncode, ret.stderr
        )

        if returncode != 0:
            with open(meta_yaml_pth) as fp:
                meta_yaml = fp.read()
            if not meta_yaml.endswith("\n"):
                meta_yaml += "\n"

            raise RuntimeError(
                "Error converting recipe to v1:\n"
                f"returncode: {returncode}\n"
                f"stderr:\n{stderr}\n"
                f"generated recipe.yaml:\n{ret.stdout}\n"
                f"original meta.yaml:\n{meta_yaml}"
            )

        recipe_yaml = ret.stdout
        if recipe_yaml.endswith("\n\n"):
            recipe_yaml = recipe_yaml[:-1]

        with open(recipe_yaml_pth, "w") as fp:
            fp.write(recipe_yaml)

        subprocess.run(
            ["git", "rm", "-f", os.path.join("recipe", "meta.yaml")],
            cwd=feedstock_dir,
            check=False,
            capture_output=True,
        )

        changed = True

    yaml = get_yaml_parser()
    with open(cf_yaml_path) as fp:
        cf_yaml = yaml.load(fp.read())

    if ("conda_build_tool" not in cf_yaml) or cf_yaml[
        "conda_build_tool"
    ] != "rattler-build":
        cf_yaml["conda_build_tool"] = "rattler-build"
        with open(cf_yaml_path, "w") as fp:
            yaml.dump(cf_yaml, fp)

        changed = True

    return changed
