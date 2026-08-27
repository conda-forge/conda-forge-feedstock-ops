import os
from unittest import mock

import pytest
from conda_forge_feedstock_ops._version import __version__
from pydantic import ValidationError

from conda_forge_feedstock_ops.settings import FeedstockOpsSettings


class TestFeedstockOpsSettings:
    def test_example_parsing(self, temporary_env_variables):
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_NAME"] = "test-container"
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_TAG"] = "test-tag"
        os.environ["CF_FEEDSTOCK_OPS_IN_CONTAINER"] = "true"
        os.environ["CF_FEEDSTOCK_OPS_CONTAINER_PROXY_MODE"] = "true"
        os.environ["CF_FEEDSTOCK_OPS_PROXY_IN_CONTAINER"] = "http://proxy:8000"

        settings = FeedstockOpsSettings()

        assert settings.container_name == "test-container"
        assert settings.container_tag == "test-tag"
        assert settings.in_container is True
        assert settings.container_proxy_mode is True
        assert str(settings.proxy_in_container) == "http://proxy:8000"

        assert settings.container_full_name == "test-container:test-tag"

    @pytest.mark.parametrize(
        "platform, expected_proxy",
        [
            ["linux", "http://172.17.0.1:8080"],
            ["darwin", "http://host.docker.internal:8080"],
            ["win32", "http://host.docker.internal:8080"],
        ],
    )
    def test_default_values(
        self, platform: str, expected_proxy: str, temporary_env_variables
    ):
        os.environ.clear()

        with mock.patch("conda_forge_feedstock_ops.settings.sys.platform", platform):
            settings = FeedstockOpsSettings()

        assert settings.container_name == "condaforge/conda-forge-feedstock-ops"
        assert settings.container_tag == __version__
        assert settings.in_container is False
        assert settings.container_proxy_mode is False
        assert str(settings.proxy_in_container) == expected_proxy
        assert (
            settings.container_full_name
            == f"{settings.container_name}:{settings.container_tag}"
        )

    def test_check_forgotten_container_proxy_mode(self, temporary_env_variables):
        os.environ.clear()

        os.environ["CF_FEEDSTOCK_OPS_PROXY_IN_CONTAINER"] = "http://proxy:8000"

        with pytest.raises(
            ValidationError, match="requires `container_proxy_mode` to be enabled"
        ):
            FeedstockOpsSettings()
