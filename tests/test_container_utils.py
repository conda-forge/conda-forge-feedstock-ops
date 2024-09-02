from conda_forge_feedstock_ops.container_utils import should_use_container
from conda_forge_feedstock_ops.os_utils import override_env


def test_should_use_container():
    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "tRue"):
        assert not should_use_container()

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false"):
        assert should_use_container()

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", None):
        assert should_use_container()

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "true"):
        assert not should_use_container(use_container=True)

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false"):
        assert should_use_container(use_container=True)

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "true"):
        assert not should_use_container(use_container=False)

    with override_env("CF_FEEDSTOCK_OPS_IN_CONTAINER", "false"):
        assert not should_use_container(use_container=False)
