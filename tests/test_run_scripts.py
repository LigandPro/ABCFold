import subprocess


def test_alphafold3_script():
    with subprocess.Popen(
        "python -m src.alphafold3 --help",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as p:
        stdout, stderr = p.communicate()
        assert p.returncode == 0, f"Return code: {p.returncode}\n{stderr.decode()}"
        assert (
            b"usage: alphafold3" in stdout
        ), f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"


def test_add_custom_template_script():
    with subprocess.Popen(
        "python -m src.add_custom_template --help",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as p:
        stdout, stderr = p.communicate()
        assert p.returncode == 0, f"Return code: {p.returncode}\n{stderr.decode()}"
        assert (
            b"usage: add_custom_template" in stdout
        ), f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"


def test_add_mmseqs_msa_script():
    with subprocess.Popen(
        "python -m src.add_mmseqs_msa --help",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as p:
        stdout, stderr = p.communicate()
        assert p.returncode == 0, f"Return code: {p.returncode}\n{stderr.decode()}"
        assert (
            b"usage: add_mmseqs_msa" in stdout
        ), f"stdout: {stdout.decode()}\nstderr: {stderr.decode()}"
