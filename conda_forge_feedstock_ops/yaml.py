from ruamel.yaml import YAML


def get_yaml_parser(*, typ):
    """Get a yaml parser.

    Parameters
    ----------
    typ : str
        The type of parser (e.g., "rt", "jinja2", etc.)

    Returns
    -------
    parser : ruamel.yaml.YAML
        The parser instance.
    """
    # using a function here so settings are always the same

    parser = YAML(typ=typ)  # spellchecker:disable-line
    parser.indent(mapping=2, sequence=4, offset=2)
    parser.width = 320
    parser.preserve_quotes = True

    # represent None as an empty string
    class _DummyRepresenter(parser.Representer):  # type: ignore[name-defined]
        pass

    def represent_none(self, data):
        return self.represent_scalar("tag:yaml.org,2002:null", "")

    _DummyRepresenter.add_representer(type(None), represent_none)
    parser.Representer = _DummyRepresenter
    parser.representer.add_representer(type(None), represent_none)

    # do not use yaml anchors
    parser.representer.ignore_aliases = lambda x: True

    return parser
