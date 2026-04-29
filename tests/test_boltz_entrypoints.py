from importlib.metadata import entry_points


def test_boltz_console_entrypoints_are_registered():
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in entry_points(group="console_scripts")
    }

    assert scripts["boltz-affinity"] == "abcfold.boltz.score_existing:main"
    assert scripts["boltz-dock"] == "abcfold.boltz.dock_crystal:main"
