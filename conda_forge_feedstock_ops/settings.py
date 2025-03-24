import sys
from typing import Annotated, Self

from pydantic import AfterValidator, AnyHttpUrl, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ._version import __version__

# https://github.com/pydantic/pydantic/issues/7186#issuecomment-1691594032
HttpProxyUrl = Annotated[AnyHttpUrl, AfterValidator(lambda x: str(x).rstrip("/"))]


def get_docker_host_hostname() -> str:
    """
    Get the default value for the `proxy_in_container` setting.
    https://stackoverflow.com/a/65505308
    """
    if sys.platform == "linux":
        return "http://172.17.0.1:8080"
    return "http://host.docker.internal:8080"


class FeedstockOpsSettings(BaseSettings):
    """
    The global settings object read from environment variables.

    To change a setting, set the environment variable `CF_FEEDSTOCK_OPS_<SETTING_NAME>`.
    Keys are case-insensitive. For example, to set the `container_name` setting, set the
    environment variable `CF_FEEDSTOCK_OPS_CONTAINER_NAME`.

    Developer note: Please note that consumers of this library might want to change some settings in between function
    invocations. Therefore, don't store the settings object in a global variable.
    """

    model_config = SettingsConfigDict(env_prefix="CF_FEEDSTOCK_OPS_")

    container_name: str = "condaforge/conda-forge-feedstock-ops"
    """
    The Docker image name to use for the container.
    """

    container_tag: str = __version__
    """
    The Docker image tag to use for the container. Defaults to the current version of this package.
    """

    in_container: bool = False
    """
    Whether the code is already running inside a container.
    """

    @property
    def container_full_name(self) -> str:
        """
        The full name of the Docker image to use for the container in the format `container_name:container_tag`.
        """
        return f"{self.container_name}:{self.container_tag}"

    container_proxy_mode: bool = False
    """
    Whether to use a proxy that is locally configured for all requests inside the container.
    """

    proxy_in_container: HttpProxyUrl = Field(default_factory=get_docker_host_hostname)
    """
    The hostname of the proxy to use in the container.
    The default value should reference the Docker host's hostname and works for
    - Docker Desktop on Windows and macOS
    - OrbStack

    For podman, set this manually to http://host.containers.internal:8080.
    """

    @model_validator(mode="after")
    def check_forgotten_container_proxy_mode(self) -> Self:
        if (
            "proxy_in_container" in self.model_fields_set
            and not self.container_proxy_mode
        ):
            raise ValueError(
                "The `proxy_in_container` setting requires `container_proxy_mode` to be enabled."
            )
        return self
