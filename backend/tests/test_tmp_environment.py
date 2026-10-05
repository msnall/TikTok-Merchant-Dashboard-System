from pathlib import Path


def test_tmp_path_uses_project_directory(tmp_path):
    actual = tmp_path.resolve()
    expected_root = Path(__file__).resolve().parents[1].resolve()
    print(f"TMP_PATH={actual}", flush=True)
    assert actual.is_relative_to(expected_root)
    assert "pytest-of-woko" not in str(actual)
