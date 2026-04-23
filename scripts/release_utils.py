from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path


USER_AGENT = "AcmeOCR-BundleBuilder/0.1"


def detect_platform_label() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows" and machine in {"amd64", "x86_64"}:
        return "windows-x64"
    if system == "macos":
        system = "darwin"
    if system == "darwin" and machine in {"x86_64", "amd64"}:
        return "darwin-x64"
    if system == "darwin" and machine in {"arm64", "aarch64"}:
        return "darwin-aarch64"
    raise SystemExit(f"Unsupported build platform: {system}-{machine}")


def run_checked(command: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def download_file(url: str, target: Path, force: bool = False) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        print(f"Using cached file: {target}")
        return target

    print(f"Downloading: {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return target


def fetch_json(url: str) -> dict[str, object]:
    token = os.getenv("GITHUB_TOKEN")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json, application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        url,
        headers=headers,
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_archive(archive_path: Path, target_dir: Path) -> Path:
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    suffixes = archive_path.suffixes
    if suffixes[-1:] == [".zip"]:
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target_dir)
    elif suffixes[-2:] == [".tar", ".gz"] or suffixes[-1:] in ([ ".tgz"], [".tar"]):
        with tarfile.open(archive_path, "r:*") as archive:
            archive.extractall(target_dir)
    else:
        raise ValueError(f"Unsupported archive format: {archive_path.name}")

    return target_dir


def collapse_single_root_directory(target_dir: Path) -> Path:
    entries = [entry for entry in target_dir.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return target_dir


def copy_tree(source_dir: Path, target_dir: Path, ignore=None) -> None:
    shutil.copytree(source_dir, target_dir, dirs_exist_ok=True, ignore=ignore)


def zip_directory(source_dir: Path, archive_path: Path) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(source_dir.rglob("*")):
            archive.write(path, path.relative_to(source_dir))
