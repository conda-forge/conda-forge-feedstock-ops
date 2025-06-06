import contextlib
import logging
import os

logger = logging.getLogger(__name__)


# https://stackoverflow.com/questions/6194499/pushd-through-os-system
@contextlib.contextmanager
def pushd(new_dir: str):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)


@contextlib.contextmanager
def override_env(name, value):
    """Override an environment variable temporarily."""
    old = os.environ.get(name)
    try:
        if value is None:
            del os.environ[name]
        else:
            os.environ[name] = value
        yield
    finally:
        if old is None:
            del os.environ[name]
        else:
            os.environ[name] = old
