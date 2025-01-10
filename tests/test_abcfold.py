# from abcfold.abcfold import main
# import pytest
# import os
# import tempfile
# import argparse

# from pathlib import Path


# @pytest.mark.skipif(
#     os.getenv("CI") == "true" and os.getenv("FULL_TEST") is None,
#     reason="Skipping test in CI environment",
# )
# def test_abcfold(test_data):
#     with tempfile.TemporaryDirectory() as temp_dir_str:
#         temp_dir = Path(temp_dir_str)
#         args = argparse.Namespace(
#             input_json=test_data.test_inputAB_json,
#             output_dir=temp_dir,
#             model_params=test_data.test_model_params,
#             database_dir=test_data.test_database_dir,
#             interactive=False,
#         )
#         main(args)
