import json
import os
import shutil
import subprocess

import pytest

HAVE_CONTAINERS = (
    shutil.which("docker") is not None
    and subprocess.run(["docker", "--version"], capture_output=True).returncode == 0
)

if HAVE_CONTAINERS:
    HAVE_TEST_IMAGE = False
    try:
        for line in subprocess.run(
            [
                "docker",
                "images",
                "--format",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines():
            image = json.loads(line)
            if (
                image["Repository"] == "conda-forge-feedstock-ops"
                and image["Tag"] == "test"
            ):
                HAVE_TEST_IMAGE = True
                break
    except subprocess.CalledProcessError as e:
        print(
            f"Could not list local docker images due "
            f"to error {e}. Skipping container tests!"
        )


skipif_no_containers = pytest.mark.skipif(
    not (HAVE_CONTAINERS and HAVE_TEST_IMAGE), reason="containers not available"
)


@pytest.fixture(autouse=True, scope="session")
def set_cf_feedstock_ops_container_tag_to_test():
    old_cftct = os.environ.get("CF_FEEDSTOCK_OPS_CONTAINER_TAG")
    if old_cftct is None:
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_TAG"] = "test"

    yield

    if old_cftct is None:
        del os.environ["CF_FEEDSTOCK_OPS_CONTAINER_TAG"]
    else:
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_TAG"] = old_cftct


@pytest.fixture(autouse=True, scope="session")
def set_cf_feedstock_ops_container_name_to_local():
    old_cftcn = os.environ.get("CF_FEEDSTOCK_OPS_CONTAINER_NAME")
    if old_cftcn is None:
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_NAME"] = "conda-forge-feedstock-ops"

    yield

    if old_cftcn is None:
        del os.environ["CF_FEEDSTOCK_OPS_CONTAINER_NAME"]
    else:
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_NAME"] = old_cftcn


@pytest.fixture(autouse=True, scope="session")
def turn_off_containers_by_default():
    old_in_container = os.environ.get("CF_FEEDSTOCK_OPS_IN_CONTAINER")

    # tell the code we are in a container so that it
    # doesn't try to run docker commands
    os.environ["CF_FEEDSTOCK_OPS_IN_CONTAINER"] = "true"

    yield

    if old_in_container is None:
        os.environ.pop("CF_FEEDSTOCK_OPS_IN_CONTAINER", None)
    else:
        os.environ["CF_FEEDSTOCK_OPS_IN_CONTAINER"] = old_in_container


@pytest.fixture
def use_containers():
    old_in_container = os.environ.get("CF_FEEDSTOCK_OPS_IN_CONTAINER")

    os.environ["CF_FEEDSTOCK_OPS_IN_CONTAINER"] = "false"

    yield

    if old_in_container is None:
        os.environ.pop("CF_FEEDSTOCK_OPS_IN_CONTAINER", None)
    else:
        os.environ["CF_FEEDSTOCK_OPS_IN_CONTAINER"] = old_in_container


@pytest.fixture
def temporary_env_variables():
    old_env = os.environ.copy()
    yield
    os.environ = old_env
