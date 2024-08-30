import json
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
            if image["Repository"] == "conda-forge-tick" and image["Tag"] == "test":
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
