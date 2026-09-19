import atexit
import os
import subprocess
import tempfile
import uuid
from collections.abc import MutableMapping, MutableSequence

from conda_forge_feedstock_ops.utils import (
    clean_rattler_cache,
    print_debug,
)
from conda_forge_feedstock_ops.virtual_packages import (
    virtual_package_repodata,
)
from conda_forge_feedstock_ops.yaml import (
    get_yaml_parser,
)

atexit.register(clean_rattler_cache)


# conda-build returns every variant value as a string, keeping whatever
# spelling the config used, but conda-smithy writes the boolean pinning keys
# (is_abi3, is_python_min, is_freethreading, ...) into .ci_support as YAML
# booleans. rattler-build evaluates `if:` with minijinja, where the non-empty
# string "false" is truthy, so passing the stringified values through would
# take the wrong branch of `if: is_abi3` and friends.
#
# These are exactly the YAML 1.2 core schema spellings, which is what
# rattler-build itself recognises when it reads the same file directly. The
# YAML 1.1 spellings (yes/no/on/off/y/n) are plain strings to it, so they have
# to stay strings here too, or the bot would disagree with CI in the other
# direction.
_YAML_BOOLS = {
    "true": True,
    "True": True,
    "TRUE": True,
    "false": False,
    "False": False,
    "FALSE": False,
}


def restore_yaml_bools(value):
    """Undo conda-build's stringification of boolean variant values.

    Parameters
    ----------
    value : object
        A variant config, or any value nested inside one.

    Returns
    -------
    value : object
        The same structure with the strings ``"true"`` and ``"false"``
        replaced by the corresponding booleans.
    """
    if isinstance(value, str):
        return _YAML_BOOLS.get(value, value)
    if isinstance(value, MutableSequence):
        return [restore_yaml_bools(item) for item in value]
    if isinstance(value, MutableMapping):
        return {key: restore_yaml_bools(item) for key, item in value.items()}
    return value


def run_rattler_build(command):
    try:
        # Run the command and capture output
        print_debug("Running: %s", " ".join(command))
        result = subprocess.run(command, check=False, capture_output=True, text=True)

        # Get the status code
        status_code = result.returncode

        # Get stdout and stderr
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        return status_code, stdout, stderr
    except Exception as e:
        return -1, "", str(e)


def invoke_rattler_build(
    recipe_dir: str, channels, build_platform, host_platform, variants
) -> (bool, str):
    # this is OK since there is an lru cache
    virtual_package_repo_url = virtual_package_repodata()
    # create a temporary file and dump the variants as YAML
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        variants_file_name = os.path.join(tmpdir, str(uuid.uuid4()) + ".yaml")
        with open(variants_file_name, "w") as fp:
            channel_sources = variants.get("channel_sources", [])
            # Add virtual package repo URL to channel sources
            if channel_sources:
                variants["channel_sources"] = [
                    source + f",{virtual_package_repo_url}"
                    for source in channel_sources
                ]

            yaml = get_yaml_parser(typ="rt")
            yaml.dump(restore_yaml_bools(variants), fp)

        channels_args = []
        if not channel_sources:
            for c in channels:
                channels_args.extend(["-c", c])

            channels_args.extend(["-c", virtual_package_repo_url])

        args = (
            ["rattler-build", "build", "--recipe", recipe_dir]
            + channels_args
            + ["--target-platform", host_platform]
            + ["--build-platform", build_platform]
            + ["-m", variants_file_name]
            + ["--render-only", "--with-solve"]
        )

        status, out, err = run_rattler_build(args)
        out = f"Command: {' '.join(args)}\nLogs:\n{out}"

        if status == 0:
            return True, ""
        else:
            return False, out + err
