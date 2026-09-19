from conda_forge_feedstock_ops.rattler_build import restore_yaml_bools


def test_restore_yaml_bools_variant_config():
    variants = {
        "is_abi3": ["false"],
        "is_python_min": ["true"],
        "python": ["3.14.* *_cp314t"],
        "python_min": ["3.11"],
        "zip_keys": [["python", "is_python_min", "is_abi3"]],
        "pin_run_as_build": {"python": {"min_pin": "x.x", "max_pin": "x.x"}},
    }

    assert restore_yaml_bools(variants) == {
        "is_abi3": [False],
        "is_python_min": [True],
        "python": ["3.14.* *_cp314t"],
        "python_min": ["3.11"],
        "zip_keys": [["python", "is_python_min", "is_abi3"]],
        "pin_run_as_build": {"python": {"min_pin": "x.x", "max_pin": "x.x"}},
    }


def test_restore_yaml_bools_yaml_12_spellings():
    """rattler-build reads the core schema spellings as booleans, so we must too"""
    assert restore_yaml_bools(["true", "True", "TRUE"]) == [True, True, True]
    assert restore_yaml_bools(["false", "False", "FALSE"]) == [False, False, False]


def test_restore_yaml_bools_leaves_yaml_11_spellings_alone():
    """yes/no/on/off are plain strings to rattler-build, so they stay strings"""
    for spelling in ("yes", "no", "Yes", "No", "on", "off", "y", "n", "N"):
        assert restore_yaml_bools(spelling) == spelling


def test_restore_yaml_bools_leaves_other_values_alone():
    assert restore_yaml_bools("conda-forge main") == "conda-forge main"
    assert restore_yaml_bools("3.14.* *_cp314t") == "3.14.* *_cp314t"
    assert restore_yaml_bools(15) == 15
    assert restore_yaml_bools(None) is None
