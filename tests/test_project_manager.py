import io
import zipfile
from pathlib import Path

from src.project_manager import get_project_summary, safe_extract_zip


def test_get_project_summary_counts_files_and_languages(tmp_path):
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (project_dir / "README.md").write_text("hello\n", encoding="utf-8")
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_app.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    summary = get_project_summary(project_dir)
    assert summary["file_count"] >= 3
    assert "Python" in summary["languages"]
    assert summary["has_tests"] is True


def test_safe_extract_zip_rejects_path_traversal(tmp_path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("../evil.py", "print('bad')\n")

    try:
        safe_extract_zip(zip_buffer.getvalue(), tmp_path / "extract")
        assert False, "Expected ZIP traversal to be rejected"
    except ValueError:
        pass


def test_safe_extract_zip_rejects_windows_path_traversal(tmp_path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr(r"..\..\outside.py", "print('bad')\n")

    try:
        safe_extract_zip(zip_buffer.getvalue(), tmp_path / "extract")
        assert False, "Expected Windows path traversal to be rejected"
    except ValueError as exc:
        assert "traversal" in str(exc).lower()


def test_safe_extract_zip_accepts_normal_files(tmp_path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as archive:
        archive.writestr("src/app.py", "print('ok')\n")
        archive.writestr("README.md", "demo\n")
        archive.writestr(".env", "SECRET=do-not-extract\n")
        archive.writestr("keys/private.pem", "private-key\n")

    extracted = safe_extract_zip(zip_buffer.getvalue(), tmp_path / "extract")
    assert "src/app.py" in extracted
    assert (tmp_path / "extract" / "src" / "app.py").exists()
    assert not (tmp_path / "extract" / ".env").exists()
    assert not (tmp_path / "extract" / "keys" / "private.pem").exists()


def test_project_scan_excludes_environment_files_and_private_keys(tmp_path):
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (project_dir / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    (project_dir / "credentials.json").write_text("{}", encoding="utf-8")
    (project_dir / "private.key").write_text("private\n", encoding="utf-8")

    summary = get_project_summary(project_dir)
    assert summary["files"] == ["main.py"]
