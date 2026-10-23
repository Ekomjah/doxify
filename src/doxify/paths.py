from __future__ import annotations

from pathlib import Path, PurePosixPath

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".next",
    "dist",
    "build",
    "coverage",
    "vendor",
    ".idea",
    ".vscode",
}

SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".der"}
SECRET_PARTS = ("secret", "credential", "password", "token", "apikey", "api_key")

LANGUAGE_BY_SUFFIX = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".sh": "Shell",
    ".sql": "SQL",
    ".md": "Markdown",
    ".toml": "TOML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
}

DEPLOY_NAMES = {
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Procfile",
    "fly.toml",
    "render.yaml",
    "netlify.toml",
    "vercel.json",
}

MANIFEST_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
}


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_skippable(relative: PurePosixPath) -> bool:
    if any(part in SKIP_DIRS for part in relative.parts):
        return True
    name = relative.name.lower()
    if name.endswith((".min.js", ".min.css", ".map")):
        return True
    return bool("lock" in name and name.endswith((".json", ".lock")))


def is_secret(relative: PurePosixPath) -> bool:
    name = relative.name.lower()
    if name == ".env":
        return True
    if name.startswith(".env.") and name != ".env.example":
        return True
    if relative.suffix.lower() in SECRET_SUFFIXES:
        return True
    return any(part in name for part in SECRET_PARTS)


def is_probably_binary(data: bytes) -> bool:
    return b"\x00" in data[:4096]


def read_text_limited(path: Path, max_bytes: int) -> str | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) > max_bytes or is_probably_binary(data):
        return None
    return data.decode("utf-8", errors="replace")


def is_readme(relative: PurePosixPath) -> bool:
    return relative.name.lower().startswith("readme")


def is_manifest(relative: PurePosixPath) -> bool:
    return relative.name in MANIFEST_NAMES


def is_deploy(relative: PurePosixPath) -> bool:
    if relative.name in DEPLOY_NAMES:
        return True
    return any(part in {".github", ".gitlab"} for part in relative.parts) and relative.suffix.lower() in {
        ".yml",
        ".yaml",
    }


def is_test(relative: PurePosixPath) -> bool:
    name = relative.name.lower()
    if name.startswith("test_") or name.endswith(
        ("_test.py", ".test.js", ".spec.js", ".test.ts", ".spec.ts", "-test.js", "-test.ts")
    ):
        return True
    if "smoke" in name:
        return True
    return "test" in {part.lower() for part in relative.parts} or "tests" in {
        part.lower() for part in relative.parts
    }


def language_for(relative: PurePosixPath) -> str | None:
    return LANGUAGE_BY_SUFFIX.get(relative.suffix.lower())
