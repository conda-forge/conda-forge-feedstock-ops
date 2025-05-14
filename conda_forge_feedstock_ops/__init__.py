from pathlib import PurePosixPath

from ._version import __version__  # noqa

CF_FEEDSTOCK_OPS_DIR = PurePosixPath("/cf_feedstock_ops_dir")
"""
This is a special directory inside the container which is marked as safe git directory.
You can mount your feedstock directory under this directory.
"""


def setup_logging(level: str = "INFO") -> None:
    import logging

    logging.basicConfig(
        format="%(asctime)-15s %(levelname)-8s %(name)s || %(message)s",
        level=level.upper(),
    )
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("github3").setLevel(logging.WARNING)
