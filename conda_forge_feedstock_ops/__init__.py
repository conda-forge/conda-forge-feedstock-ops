from ._version import __version__  # noqa


def setup_logging(level: str = "INFO") -> None:
    import logging

    logging.basicConfig(
        format="%(asctime)-15s %(levelname)-8s %(name)s || %(message)s",
        level=level.upper(),
    )
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("github3").setLevel(logging.WARNING)
