import os
import tempfile

from conda_forge_feedstock_ops.json import dump, dumps, load, loads


def test_json_round_trip_str():
    data = {"a": 1, "b": 2, "c": set([1, 2, 3])}
    dres = dumps(data)
    lres = loads(dres)
    assert data == lres


def test_json_round_trip_file():
    data = {"a": 1, "b": 2, "c": set([1, 2, 3])}

    with tempfile.TemporaryDirectory() as tmpdir:
        fname = os.path.join(tmpdir, "test.json")
        with open(fname, "w") as fp:
            dump(data, fp)

        with open(fname) as fp:
            lres = load(fp)

        assert data == lres
