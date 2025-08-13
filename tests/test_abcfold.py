import argparse
import configparser
import os
import tempfile
from pathlib import Path

import pytest

from abcfold.abcfold import run


@pytest.mark.skipif(
    os.getenv("FULL_TEST") != "true",
    reason="This test is skipped in the full test suite",
)
def test_abcfold(test_data):
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        config_file_path = temp_dir / "config.ini"

        config_file_path.write_text(
            """
[Databases]
model_params = None
database_dir = None
"""
        )

        defaults = {}
        config = configparser.SafeConfigParser()

        if config_file_path.exists():
            config.read(str(config_file_path))
            defaults.update(dict(config.items("Databases")))

        args = argparse.Namespace(
            input_json=test_data.test_inputAB_json,
            output_dir=temp_dir / "output",
            model_params=str(temp_dir),
            database_dir=str(temp_dir),
            # interactive=False,
            override=True,
            alphafold3=False,
            boltz=True,
            chai1=True,
            mmseqs2=True,
            output_json=None,
            templates=False,
            num_templates=0,
            custom_template=False,
            custom_template_chain=None,
            target_id=None,
            save_input=False,
        )

        run(
            args,
            config_file=config_file_path,
            defaults=defaults,
            config=config,
        )

        out_dirs = [x.name for x in Path(args.output_dir).iterdir()]
        print(out_dirs)

        assert "chai1" in out_dirs
        assert "boltz_inputAB_mmseqs" in out_dirs
