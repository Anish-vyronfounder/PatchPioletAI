from __future__ import annotations

import io
import os
import posixpath
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Iterable

ALLOWED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".cc",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".php",
    ".rb",
    ".swift",
    ".kt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env.example",
    ".md",
    ".txt",
    ".xml",
    ".html",
    ".css",
    ".sql",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    ".dist",
    "dist",
    "build",
    "coverage",
    ".idea",
    ".vscode",
}

SKIP_FILE_NAMES = {".env", ".env.local", ".DS_Store"}
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 1000
MAX_ARCHIVE_SIZE_BYTES = 100 * 1024 * 1024
SENSITIVE_FILE_NAMES = {
    "credentials",
    "credentials.json",
    "secrets",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
    ".npmrc",
    ".pypirc",
}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}


def detect_language(path: str | os.PathLike[str]) -> str:
    suffix = Path(path).suffix.lower()
    mapping = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "React JSX",
        ".ts": "TypeScript",
        ".tsx": "React TSX",
        ".java": "Java",
        ".cpp": ".cpp",
        ".c": "C",
        ".cc": "C++",
        ".h": "C Header",
        ".hpp": "C++ Header",
        ".cs": "C#",
        ".go": "Go",
        ".rs": "Rust",
        ".php": "PHP",
        ".rb": "Ruby",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".toml": "TOML",
        ".ini": "INI",
        ".cfg": "Config",
        ".md": "Markdown",
        ".txt": "Text",
        ".xml": "XML",
        ".html": "HTML",
        ".css": "CSS",
        ".sql": "SQL",
    }
    return mapping.get(suffix, "Other")


def detect_framework(files: Iterable[str]) -> list[str]:
    files_lower = [f.lower() for f in files]
    frameworks: list[str] = []
    if any(f.endswith("requirements.txt") for f in files_lower):
        frameworks.append("Python")
    if any(f.endswith("pyproject.toml") or f.endswith("setup.py") for f in files_lower):
        frameworks.append("Python package")
    if any(f.endswith("package.json") for f in files_lower):
        frameworks.append("Node.js")
    if any(f.endswith("next.config.js") or f.endswith("next.config.mjs") for f in files_lower):
        frameworks.append("Next.js")
    if any(f.endswith("vite.config.js") or f.endswith("vite.config.ts") for f in files_lower):
        frameworks.append("Vite")
    if any(f.endswith("streamlit_app.py") or f.endswith("app.py") for f in files_lower):
        frameworks.append("Streamlit")
    if any(f.endswith("go.mod") for f in files_lower):
        frameworks.append("Go module")
    if any(f.endswith("pom.xml") or f.endswith("build.gradle") for f in files_lower):
        frameworks.append("JVM")
    if any(f.endswith("Dockerfile") for f in files_lower):
        frameworks.append("Containerized")
    return frameworks


def _is_excluded(rel_path: str) -> bool:
    parts = PurePosixPath(rel_path).parts
    if any(part in SKIP_DIRS for part in parts):
        return True
    if any(part.startswith(".env") and part != ".env.example" for part in parts):
        return True
    file_name = PurePosixPath(rel_path).name
    if file_name.lower() in SENSITIVE_FILE_NAMES:
        return True
    if PurePosixPath(file_name).suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    if file_name in SKIP_FILE_NAMES:
        return True
    if file_name.startswith(".") and file_name not in {".env.example"}:
        return True
    return False


def read_text_file(path: str | os.PathLike[str]) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write_text_file(path: str | os.PathLike[str], content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def get_project_files(project_dir: str | os.PathLike[str]) -> list[str]:
    project_path = Path(project_dir)
    if not project_path.exists():
        return []

    result: list[str] = []
    for path in sorted(project_path.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(project_path).as_posix()
        if _is_excluded(rel_path):
            continue
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            continue
        if Path(rel_path).suffix.lower() not in ALLOWED_EXTENSIONS and Path(rel_path).name not in {"Dockerfile", "Makefile", "README.md", "requirements.txt"}:
            continue
        result.append(rel_path)
    return result


def get_project_summary(project_dir: str | os.PathLike[str]) -> dict[str, object]:
    files = get_project_files(project_dir)
    language_counts: dict[str, int] = {}
    for rel in files:
        lang = detect_language(rel)
        language_counts[lang] = language_counts.get(lang, 0) + 1

    project_files = list(files)
    def _is_test_file(file_name: str) -> bool:
        lower_name = file_name.lower()
        return (
            lower_name.endswith("pytest.ini")
            or lower_name.endswith("package.json")
            or lower_name.startswith("test_")
            or lower_name.endswith("_test.py")
            or "test" in lower_name.split("/")[-1].split(".")[0]
            or "/tests/" in lower_name
        )

    return {
        "file_count": len(project_files),
        "languages": language_counts,
        "frameworks": detect_framework(project_files),
        "files": project_files,
        "has_tests": any(_is_test_file(file) for file in project_files),
        "has_requirements": any(file.endswith("requirements.txt") or file.endswith("pyproject.toml") or file.endswith("package.json") for file in project_files),
    }


def safe_extract_zip(zip_bytes: bytes, destination: str | os.PathLike[str]) -> list[str]:
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    destination_root = destination_path.resolve()

    extracted: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise ValueError(f"ZIP contains more than {MAX_ARCHIVE_MEMBERS} entries.")

        total_size = sum(info.file_size for info in members if not info.is_dir())
        if total_size > MAX_ARCHIVE_SIZE_BYTES:
            raise ValueError(
                f"ZIP expands beyond the {MAX_ARCHIVE_SIZE_BYTES // (1024 * 1024)} MB limit."
            )

        seen_paths: set[str] = set()
        for info in members:
            if info.is_dir():
                continue
            member_name = info.filename.replace("\\", "/")
            normalized = posixpath.normpath(member_name)
            if normalized in {"", "."}:
                continue
            parts = PurePosixPath(normalized).parts
            if (
                normalized.startswith("/")
                or (parts and parts[0].endswith(":"))
                or ".." in parts
            ):
                raise ValueError(f"ZIP path traversal detected: {info.filename}")
            if _is_excluded(normalized):
                continue
            if any(part in SKIP_DIRS for part in parts[:-1]):
                continue
            if Path(normalized).suffix.lower() not in ALLOWED_EXTENSIONS and Path(normalized).name not in {
                "Dockerfile",
                "Makefile",
                "README.md",
                "requirements.txt",
            }:
                continue
            if info.file_size > MAX_FILE_SIZE_BYTES:
                raise ValueError(f"ZIP entry exceeds the 2 MB per-file limit: {normalized}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError(f"ZIP symbolic links are not supported: {normalized}")
            normalized_key = normalized.casefold()
            if normalized_key in seen_paths:
                raise ValueError(f"ZIP contains a duplicate path: {normalized}")
            seen_paths.add(normalized_key)

            target = destination_path.joinpath(*parts)
            target_resolved = target.resolve()
            if target_resolved != destination_root and destination_root not in target_resolved.parents:
                raise ValueError(f"ZIP path traversal detected: {info.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
            extracted.append(target.relative_to(destination_path).as_posix())
    return extracted


def get_file_tree(project_dir: str | os.PathLike[str]) -> list[str]:
    files = get_project_files(project_dir)
    return files


def is_supported_source_file(file_name: str) -> bool:
    suffix = Path(file_name).suffix.lower()
    return suffix in ALLOWED_EXTENSIONS or file_name in {"Dockerfile", "Makefile"}
