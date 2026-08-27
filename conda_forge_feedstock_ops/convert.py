import os
import subprocess

from ruamel.yaml import YAML


def _get_yaml_parser(typ="jinja2"):
    """Yaml parser that is jinja2 aware."""
    # using a function here so settings are always the same

    def represent_none(self, data):
        return self.represent_scalar("tag:yaml.org,2002:null", "")

    parser = YAML(typ=typ)  # spellchecker:disable-line
    parser.indent(mapping=2, sequence=4, offset=2)
    parser.width = 320
    parser.preserve_quotes = True
    parser.representer.ignore_aliases = lambda x: True
    parser.representer.add_representer(type(None), represent_none)
    return parser


def _post_process_returncode_and_stderr(returncode, stderr):
    new_lines = []
    for line in stderr.splitlines():
        line = line.strip()
        if "license_family" in line:
            continue

        if (
            "Recipe upgrades cannot currently upgrade ambiguous version constraints on dependencies that use variables"
            in line
        ):
            continue

        if "The recipe parser was unable to evaluate the JINJA expression" in line:
            continue

        if "Could not patch unrecognized license" in line:
            continue

        if (
            "errors and" in line
            and "warnings were found." in line
            and line.startswith("0")
        ):
            continue

        new_lines.append(line.strip())

    if not new_lines:
        return 0, stderr
    else:
        return returncode, stderr


def convert_feedstock_to_v1_local(feedstock_dir: str):
    recipe_yaml_pth = os.path.join(feedstock_dir, "recipe", "recipe.yaml")
    meta_yaml_pth = os.path.join(feedstock_dir, "recipe", "meta.yaml")
    cf_yaml_path = os.path.join(feedstock_dir, "conda-forge.yml")

    if (not os.path.exists(recipe_yaml_pth)) and os.path.exists(meta_yaml_pth):
        ret = subprocess.run(
            ["conda-recipe-manager", "convert", meta_yaml_pth],
            capture_output=True,
            text=True,
            check=False,
        )

        returncode, stderr = _post_process_returncode_and_stderr(
            ret.returncode, ret.stderr
        )

        if returncode != 0:
            with open(meta_yaml_pth) as fp:
                meta_yaml = fp.read()
            if not meta_yaml.endswith("\n"):
                meta_yaml += "\n"

            raise RuntimeError(
                "Error converting recipe to v1:\n"
                f"returncode: {returncode}\n"
                f"stderr:\n{stderr}\n"
                f"generated recipe.yaml:\n{ret.stdout}\n"
                f"original meta.yaml:\n{meta_yaml}"
            )

        with open(recipe_yaml_pth, "w") as fp:
            fp.write(ret.stdout)

        subprocess.run(
            ["git", "rm", "-f", os.path.join("recipe", "meta.yaml")],
            cwd=feedstock_dir,
            check=False,
        )

    yaml = _get_yaml_parser()
    with open(cf_yaml_path) as fp:
        cf_yaml = yaml.load(fp.read())

    if ("conda_build_tool" not in cf_yaml) or cf_yaml[
        "conda_build_tool"
    ] != "rattler-build":
        cf_yaml["conda_build_tool"] = "rattler-build"
        with open(cf_yaml_path, "w") as fp:
            yaml.dump(cf_yaml, fp)
