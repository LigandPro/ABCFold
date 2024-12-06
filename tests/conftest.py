from collections import namedtuple
from pathlib import Path

import pytest


# Code taken from SliceNDice
@pytest.fixture()
def test_data():
    """
    Return a namedtuple object with the paths to all the data files we require.

    Args:
        None

    Returns:
        namedtuple: A namedtuple object with the paths to all the data files we require.
    """
    data_dir = Path("./test_data")
    if not data_dir.exists():
        data_dir = Path("tests/test_data")
    if not data_dir.exists():
        msg = "Could not find the test_data, Please make sure that you're running the \
tests from the root of the repository or the tests directory"
        raise FileNotFoundError(msg)
    d = {}

    for test_file in data_dir.glob("*"):
        stem, suffix = test_file.stem, test_file.suffix[1:]
        d[f"test_{stem}_{suffix}"] = str(test_file)

    nt = namedtuple("TestData", d)

    return nt(**d)
