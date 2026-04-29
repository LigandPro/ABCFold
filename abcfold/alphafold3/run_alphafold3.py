import json
import logging
import shlex
import string
import subprocess
from pathlib import Path
from typing import Union

from abcfold.alphafold3.ccd_one_letter import CCD_NAME_TO_ONE_LETTER
from abcfold.alphafold3.check_install import check_af3_install

logger = logging.getLogger("logger")

ALPHAFAST_IMAGE = "romerolabduke/alphafast:latest"
CONTAINER_INPUT_DIR = Path("/root/af_input")
CONTAINER_OUTPUT_DIR = Path("/root/af_output")
CONTAINER_MODEL_DIR = Path("/root/models")
CONTAINER_DB_DIR = Path("/root/public_databases")
CONTAINER_MMSEQS_DB_DIR = CONTAINER_DB_DIR / "mmseqs"
CONTAINER_APP_DIR = Path("/app/alphafold")


def sanitize_job_name(name: str) -> str:
    """Match AlphaFold-style output directory sanitisation rules."""
    spaceless_name = name.replace(" ", "_")
    allowed_chars = set(string.ascii_letters + string.digits + "_-.")
    return "".join(char for char in spaceless_name if char in allowed_chars)


def _resolve_job_output_dir(input_json: Path) -> Path:
    with input_json.open("r") as handle:
        input_params = json.load(handle)

    name = input_params.get("name")
    if not name:
        raise ValueError("Input JSON must contain a non-empty 'name' field")
    return Path(sanitize_job_name(name))


def _gpu_flags(gpus: str) -> list[str]:
    if gpus.lower() == "cpu":
        return []
    if gpus.lower() == "all":
        return ["--gpus", "all"]
    return ["--gpus", f"device={gpus}"]


def _build_alphafast_docker_cmd(
    input_json: Path,
    output_dir: Path,
    model_params: Path,
    database_dir: Path,
    n_models: int,
    n_recycles: int,
    gpus: str,
    interactive: bool,
    use_precomputed_msas: bool,
    save_distogram: bool,
    image: str,
) -> tuple[list[str], Path]:
    job_output_dir = _resolve_job_output_dir(input_json)
    container_output_dir = (
        CONTAINER_OUTPUT_DIR / job_output_dir
        if use_precomputed_msas
        else CONTAINER_OUTPUT_DIR
    )

    cmd = ["docker", "run", "-i"] if interactive else ["docker", "run", "--rm"]
    cmd += _gpu_flags(gpus)
    cmd += [
        "--volume",
        f"{input_json.parent.resolve()}:{CONTAINER_INPUT_DIR}:ro",
        "--volume",
        f"{output_dir.resolve()}:{CONTAINER_OUTPUT_DIR}",
        "--volume",
        f"{model_params.resolve()}:{CONTAINER_MODEL_DIR}:ro",
        "--volume",
        f"{database_dir.resolve()}:{CONTAINER_DB_DIR}:ro",
        image,
        "python",
        str(CONTAINER_APP_DIR / "run_alphafold.py"),
        "--json_path",
        str(CONTAINER_INPUT_DIR / input_json.name),
        "--model_dir",
        str(CONTAINER_MODEL_DIR),
        "--output_dir",
        str(container_output_dir),
        "--db_dir",
        str(CONTAINER_DB_DIR),
        "--mmseqs_db_dir",
        str(CONTAINER_MMSEQS_DB_DIR),
        "--num_diffusion_samples",
        str(n_models),
        "--num_recycles",
        str(n_recycles),
    ]

    if save_distogram:
        cmd.append("--save_distogram")

    if use_precomputed_msas:
        cmd += ["--norun_data_pipeline", "--force_output_dir"]
    else:
        cmd.append("--use_mmseqs_gpu")

    return cmd, output_dir / job_output_dir


def _build_singularity_cmd(
    input_json: Path,
    output_dir: Path,
    model_params: Path,
    database_dir: Path,
    sif_path: Union[str, Path],
    number_of_models: int,
    num_recycles: int,
    save_distogram: bool,
    gpus: str,
) -> str:
    singularity_gpu_flag = "--nv" if gpus != "cpu" else ""
    distogram_flag = (
        f"        --save_distogram {str(save_distogram).lower()}\n"
        if save_distogram
        else ""
    )
    return f"""
        singularity exec \
        {singularity_gpu_flag} \
        --bind {input_json.parent.resolve()}:/root/af_input \
        --bind {output_dir.resolve()}:/root/af_output \
        --bind {model_params.resolve()}:/root/models \
        --bind {database_dir.resolve()}:/root/public_databases \
        {sif_path} \
        python /app/alphafold/run_alphafold.py \
        --json_path=/root/af_input/{input_json.name} \
        --model_dir=/root/models \
        --output_dir=/root/af_output \
        --db_dir=/root/public_databases \
        --num_diffusion_samples {number_of_models}\
        --num_recycles {num_recycles}\
{distogram_flag}
    """


def run_alphafold3(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    model_params: Union[str, Path],
    database_dir: Union[str, Path],
    sif_path: Union[str, Path, None],
    config: dict,
    interactive: bool = False,
    number_of_models: int = 5,
    num_recycles: int = 10,
    save_distogram: bool = False,
    gpus: str = "all",
    use_precomputed_msas: bool = False,
) -> Path | None:
    """
    Run Alphafold3 using AlphaFast as the default container backend.

    When `sif_path` is provided, fall back to the legacy Singularity flow.
    """
    input_json = process_input_json(Path(input_json))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    check_af3_install(config=config, interactive=False, sif_path=sif_path)

    run_args: str | list[str]
    if sif_path is not None and sif_path != "None":
        cmd = generate_af3_cmd(
            input_json=input_json,
            output_dir=output_dir,
            model_params=model_params,
            database_dir=database_dir,
            sif_path=sif_path,
            config=config,
            interactive=interactive,
            number_of_models=number_of_models,
            num_recycles=num_recycles,
            save_distogram=save_distogram,
            gpus=gpus,
        )
        job_output_dir = output_dir
        run_args = cmd
        run_shell = True
    else:
        image = config.get("af3_docker_env", ALPHAFAST_IMAGE)
        cmd_list, job_output_dir = _build_alphafast_docker_cmd(
            input_json=input_json,
            output_dir=output_dir,
            model_params=Path(model_params),
            database_dir=Path(database_dir),
            n_models=number_of_models,
            n_recycles=num_recycles,
            gpus=gpus,
            interactive=interactive,
            use_precomputed_msas=use_precomputed_msas,
            save_distogram=save_distogram,
            image=image,
        )
        run_args = cmd_list
        run_shell = False

    logger.info("Running Alphafold3")
    try:
        subprocess.run(
            run_args,
            shell=run_shell,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        error_log = exc.stderr or ""
        logger.error(error_log)
        output_err_file = output_dir / "af3_error.log"
        output_err_file.write_text(error_log)
        logger.error("Alphafold3 run failed. Error log is in %s", output_err_file)
        return None

    logger.info("Alphafold3 run complete")
    logger.info("Output files are in %s", job_output_dir)
    return job_output_dir


def process_input_json(input_json: Union[str, Path]) -> Path:
    """
    Process the input JSON file so post-translational modifications are included
    in the MSA sequence when AlphaFold-compatible one-letter codes are known.
    """
    input_json = Path(input_json)
    with open(input_json, "r") as f:
        json_dict = json.load(f)

    updated = False
    for sequence in json_dict["sequences"]:
        protein = sequence.get("protein")
        if protein is None:
            continue
        modifications = protein.get("modifications", [])
        for modification in modifications:
            one_letter_code = None
            position = None
            msa = None
            if "ptmType" in modification:
                ptm_type = modification["ptmType"]
                if ptm_type in CCD_NAME_TO_ONE_LETTER:
                    one_letter_code = CCD_NAME_TO_ONE_LETTER[ptm_type]
                    position = modification["ptmPosition"]
                    msa = protein.get("unpairedMsa")
            if one_letter_code is not None and position is not None and msa is not None:
                msa_lines = msa.splitlines()
                input_seq = msa_lines[1]
                idx = int(position) - 1
                input_seq = input_seq[:idx] + one_letter_code + input_seq[idx + 1:]
                msa_lines[1] = input_seq
                protein["unpairedMsa"] = "\n".join(msa_lines)
                updated = True

    if updated:
        with open(input_json, "w") as f:
            json.dump(json_dict, f, indent=4)

    return input_json


def generate_af3_cmd(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    model_params: Union[str, Path],
    database_dir: Union[str, Path],
    sif_path: Union[str, Path, None],
    config: dict,
    number_of_models: int = 10,
    num_recycles: int = 5,
    interactive: bool = False,
    save_distogram: bool = False,
    gpus: str = "all",
    use_precomputed_msas: bool = False,
) -> str:
    """
    Generate the Alphafold3 command.

    Docker mode uses AlphaFast by default. Singularity mode keeps the legacy AF3 flow.
    """
    input_json = Path(input_json)
    output_dir = Path(output_dir)

    if sif_path is not None and sif_path != "None":
        return _build_singularity_cmd(
            input_json=input_json,
            output_dir=output_dir,
            model_params=Path(model_params),
            database_dir=Path(database_dir),
            sif_path=sif_path,
            number_of_models=number_of_models,
            num_recycles=num_recycles,
            save_distogram=save_distogram,
            gpus=gpus,
        )

    image = config.get("af3_docker_env", ALPHAFAST_IMAGE)
    cmd, _ = _build_alphafast_docker_cmd(
        input_json=input_json,
        output_dir=output_dir,
        model_params=Path(model_params),
        database_dir=Path(database_dir),
        n_models=number_of_models,
        n_recycles=num_recycles,
        gpus=gpus,
        interactive=interactive,
        use_precomputed_msas=use_precomputed_msas,
        save_distogram=save_distogram,
        image=image,
    )
    return shlex.join(cmd)
