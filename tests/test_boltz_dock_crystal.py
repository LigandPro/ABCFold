from pathlib import Path

from abcfold.boltz.dock_crystal import (_parse_args,
                                        generate_boltz_crystal_dock_command,
                                        prepare_crystal_docking_input)


def atom_line(
    record: str,
    serial: int,
    atom: str,
    resname: str,
    chain: str,
    resnum: int,
    x_coord: float,
    y_coord: float,
    element: str,
) -> str:
    return (
        f"{record:<6}{serial:5d} {atom:<4} {resname:>3} {chain}{resnum:4d}"
        f"    {x_coord:8.3f}{y_coord:8.3f}{0.0:8.3f}"
        f"  1.00 20.00          {element:>2}"
    )


def write_receptor(path: Path) -> None:
    path.write_text(
        "\n".join([
            atom_line("ATOM", 1, "N", "ALA", "A", 1, 0.0, 0.0, "N"),
            atom_line("ATOM", 2, "CA", "ALA", "A", 1, 1.5, 0.0, "C"),
            atom_line("ATOM", 3, "C", "ALA", "A", 1, 2.5, 1.0, "C"),
            atom_line("ATOM", 4, "N", "GLY", "A", 2, 4.0, 1.0, "N"),
            atom_line("ATOM", 5, "CA", "GLY", "A", 2, 5.0, 2.0, "C"),
            atom_line("ATOM", 6, "C", "GLY", "A", 2, 6.0, 1.0, "C"),
            atom_line("ATOM", 7, "N", "SER", "A", 3, 8.0, 1.0, "N"),
            atom_line("ATOM", 8, "CA", "SER", "A", 3, 9.0, 2.0, "C"),
            atom_line("ATOM", 9, "C", "SER", "A", 3, 10.0, 1.0, "C"),
            atom_line("HETATM", 10, "C1", "LIG", "L", 1, 5.1, 2.1, "C"),
            atom_line("HETATM", 11, "O1", "LIG", "L", 1, 5.8, 2.1, "O"),
            "TER",
            "END",
            "",
        ])
    )


def test_prepare_crystal_docking_input_with_pdb_numbered_pocket(tmp_path):
    receptor = tmp_path / "receptor.pdb"
    write_receptor(receptor)
    args = _parse_args([
        str(receptor),
        "CCO",
        "--out_dir",
        str(tmp_path / "out"),
        "--pocket_residue",
        "A:2",
        "--affinity",
        "--dry_run",
    ])

    prepared = prepare_crystal_docking_input(args)
    yaml_text = prepared.yaml_path.read_text()

    assert prepared.contacts == [["A", 2]]
    assert "sequence: \"AGS\"" in yaml_text
    assert "smiles: \"CCO\"" in yaml_text
    assert "contacts: [[\"A\", 2]]" in yaml_text
    assert "templates:" in yaml_text
    assert "template_id: \"A1\"" in yaml_text
    assert "properties:" in yaml_text
    assert "--use_potentials" in prepared.command


def test_prepare_crystal_docking_input_can_infer_pocket(tmp_path):
    receptor = tmp_path / "receptor.pdb"
    write_receptor(receptor)
    args = _parse_args([
        str(receptor),
        "CCO",
        "--out_dir",
        str(tmp_path / "out"),
        "--reference_ligand_chain",
        "L",
        "--pocket_cutoff",
        "1.0",
        "--dry_run",
    ])

    prepared = prepare_crystal_docking_input(args)

    assert prepared.contacts == [["A", 2]]


def test_generate_boltz_crystal_dock_command(tmp_path):
    args = _parse_args([
        str(tmp_path / "receptor.pdb"),
        "CCO",
        "--pocket_residue",
        "A:1",
        "--use_msa_server",
        "--step_scale",
        "1.5",
        "--dry_run",
    ])

    cmd = generate_boltz_crystal_dock_command(
        tmp_path / "input.yaml",
        tmp_path / "out",
        args,
    )

    assert cmd[:2] == ["boltz", "predict"]
    assert "--use_msa_server" in cmd
    assert "--use_potentials" in cmd
    assert "--step_scale" in cmd
