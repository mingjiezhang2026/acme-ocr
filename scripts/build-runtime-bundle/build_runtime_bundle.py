from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from release_utils import (  # noqa: E402
    collapse_single_root_directory,
    copy_tree,
    detect_platform_label,
    download_file,
    extract_archive,
    fetch_json,
    run_checked,
    sha256_file,
    write_json,
    zip_directory,
)


DEFAULT_PYTHON_VERSION = "3.11.11"
DEFAULT_GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
PYTHON_ORG_EMBED_URL = "https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
PYTHON_BUILD_STANDALONE_API = "https://api.github.com/repos/astral-sh/python-build-standalone/releases"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AcmeOCR runtime bundle")
    parser.add_argument("--version", required=True, help="Runtime bundle version")
    parser.add_argument("--platform", default=detect_platform_label(), help="Bundle platform label")
    parser.add_argument(
        "--python-provider",
        choices=["auto", "python-build-standalone", "python-org-embed", "local-venv"],
        default="auto",
        help="How to acquire the base Python runtime",
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON_VERSION,
        help="Python version for official upstream downloads",
    )
    parser.add_argument(
        "--python-source-url",
        default="",
        help="Optional direct upstream archive URL overriding provider defaults",
    )
    parser.add_argument(
        "--python-build-standalone-release",
        default="latest",
        help="python-build-standalone release tag or 'latest'",
    )
    parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Builder Python executable used for local-venv mode",
    )
    parser.add_argument(
        "--requirements",
        default="services/ocr-worker/requirements.lock",
        help="Path to the worker requirements lock file",
    )
    parser.add_argument(
        "--worker-src",
        default="services/ocr-worker",
        help="Path to the worker source tree",
    )
    parser.add_argument(
        "--output-dir",
        default="dist/runtime-bundles",
        help="Directory for zip artifacts",
    )
    parser.add_argument(
        "--download-cache-dir",
        default="dist/upstream-cache",
        help="Directory used to cache upstream downloads",
    )
    parser.add_argument(
        "--wheelhouse",
        default="",
        help="Optional local wheelhouse path for offline installs",
    )
    parser.add_argument(
        "--pip-index-url",
        default="",
        help="Optional custom package index URL",
    )
    parser.add_argument(
        "--bundle-name",
        default="",
        help="Optional artifact name without .zip",
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Keep temporary build output for inspection",
    )
    parser.add_argument(
        "--force-redownload",
        action="store_true",
        help="Ignore cached upstream archives",
    )
    return parser.parse_args()


def provider_for_platform(provider: str, platform_label: str) -> str:
    if provider != "auto":
        return provider
    if platform_label == "windows-x64":
        return "python-org-embed"
    return "python-build-standalone"


def copy_worker_tree(source_dir: Path, target_dir: Path) -> None:
    ignore = shutil.ignore_patterns(
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "*.pyc",
        "*.pyo",
        "*.db",
        "*.sqlite3",
    )
    copy_tree(source_dir, target_dir, ignore=ignore)


def write_runtime_manifest(target_dir: Path, metadata: dict[str, object]) -> None:
    write_json(target_dir / "metadata" / "runtime-manifest.json", metadata)


def pbs_target(platform_label: str) -> str:
    mapping = {
        "windows-x64": "x86_64-pc-windows-msvc",
        "darwin-x64": "x86_64-apple-darwin",
        "darwin-aarch64": "aarch64-apple-darwin",
    }
    return mapping[platform_label]


def find_python_executable(root: Path, platform_label: str) -> Path:
    candidates = [
        root / "python.exe",
        root / "bin" / "python3",
        root / "bin" / "python",
        root / "install" / "python.exe",
        root / "install" / "bin" / "python3",
        root / "install" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    names = ["python.exe"] if platform_label.startswith("windows") else ["python3", "python"]
    matches: list[Path] = []
    for name in names:
        matches.extend(root.rglob(name))
    if matches:
        return sorted(matches, key=lambda item: len(item.parts))[0]
    raise FileNotFoundError(f"python executable not found under {root}")


def flatten_python_root_layout(python_root: Path) -> None:
    while True:
        entries = list(python_root.iterdir())
        if len(entries) != 1 or not entries[0].is_dir() or entries[0].name not in {"install", "python"}:
            return
        nested_root = entries[0]
        for item in nested_root.iterdir():
            shutil.move(str(item), str(python_root / item.name))
        nested_root.rmdir()


def enable_windows_embeddable_site_packages(python_root: Path) -> None:
    for pth_file in python_root.glob("python*._pth"):
        lines = pth_file.read_text(encoding="utf-8").splitlines()
        normalized: list[str] = []
        has_site_packages = False
        for line in lines:
            stripped = line.strip()
            if stripped == "#import site":
                normalized.append("import site")
                continue
            if "site-packages" in stripped:
                has_site_packages = True
            normalized.append(line)
        if not has_site_packages:
            normalized.insert(-1 if normalized else 0, "Lib\\site-packages")
        pth_file.write_text("\n".join(normalized) + "\n", encoding="utf-8")


def bootstrap_pip(
    python_bin: Path,
    provider: str,
    cache_dir: Path,
    force_redownload: bool,
) -> None:
    try:
        run_checked([str(python_bin), "-m", "pip", "--version"])
        return
    except Exception:
        pass

    try:
        run_checked([str(python_bin), "-m", "ensurepip", "--upgrade"])
        run_checked([str(python_bin), "-m", "pip", "--version"])
        return
    except Exception:
        if provider != "python-org-embed":
            raise

    get_pip = download_file(
        DEFAULT_GET_PIP_URL,
        cache_dir / "get-pip.py",
        force=force_redownload,
    )
    run_checked([str(python_bin), str(get_pip)])


def pip_install_runtime(
    python_bin: Path,
    requirements_file: Path,
    wheelhouse: Path | None,
    pip_index_url: str | None,
) -> None:
    env = os.environ.copy()
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"

    run_checked(
        [str(python_bin), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        env=env,
    )

    install_cmd = [str(python_bin), "-m", "pip", "install", "-r", str(requirements_file)]
    if wheelhouse is not None:
        install_cmd.extend(["--no-index", "--find-links", str(wheelhouse)])
    elif pip_index_url:
        install_cmd.extend(["--index-url", pip_index_url])
    run_checked(install_cmd, env=env)


def latest_pbs_release(tag_or_latest: str) -> dict[str, object]:
    if tag_or_latest != "latest":
        return fetch_json(f"{PYTHON_BUILD_STANDALONE_API}/tags/{tag_or_latest}")
    return fetch_json(f"{PYTHON_BUILD_STANDALONE_API}/latest")


def resolve_pbs_asset_url(
    python_version: str,
    platform_label: str,
    release_tag: str,
) -> tuple[str, str]:
    release_data = latest_pbs_release(release_tag)
    tag_name = str(release_data["tag_name"])
    target = pbs_target(platform_label)
    pattern = re.compile(
        rf"^cpython-{re.escape(python_version)}\+{re.escape(tag_name)}-{re.escape(target)}-install_only(?:_stripped)?\.(?:tar\.gz|zip)$"
    )

    for asset in release_data.get("assets", []):
        asset_name = str(asset.get("name", ""))
        if pattern.match(asset_name):
            return str(asset["browser_download_url"]), tag_name

    raise RuntimeError(
        f"Could not find python-build-standalone asset for Python {python_version}, platform {platform_label}, release {tag_name}"
    )


def acquire_python_from_local_venv(
    python_root: Path,
    builder_python: str,
    platform_label: str,
) -> tuple[Path, dict[str, object]]:
    run_checked([builder_python, "-m", "venv", "--copies", str(python_root)])
    python_bin = find_python_executable(python_root, platform_label)
    metadata = {
        "provider": "local-venv",
        "builderPython": builder_python,
    }
    return python_bin, metadata


def acquire_python_from_python_org_embed(
    python_root: Path,
    cache_dir: Path,
    python_version: str,
    source_url: str | None,
    force_redownload: bool,
) -> tuple[Path, dict[str, object]]:
    url = source_url or PYTHON_ORG_EMBED_URL.format(version=python_version)
    archive_path = download_file(
        url,
        cache_dir / Path(url).name,
        force=force_redownload,
    )
    extracted_root = extract_archive(archive_path, python_root)
    _ = collapse_single_root_directory(extracted_root)
    flatten_python_root_layout(python_root)
    enable_windows_embeddable_site_packages(python_root)
    python_bin = find_python_executable(python_root, "windows-x64")
    metadata = {
        "provider": "python-org-embed",
        "upstreamUrl": url,
        "upstreamArchive": archive_path.name,
    }
    return python_bin, metadata


def acquire_python_from_pbs(
    python_root: Path,
    cache_dir: Path,
    python_version: str,
    platform_label: str,
    release_tag: str,
    source_url: str | None,
    force_redownload: bool,
) -> tuple[Path, dict[str, object]]:
    if source_url:
        url = source_url
        resolved_release = release_tag
    else:
        url, resolved_release = resolve_pbs_asset_url(python_version, platform_label, release_tag)

    archive_path = download_file(
        url,
        cache_dir / Path(url).name,
        force=force_redownload,
    )
    extract_dir = Path(tempfile.mkdtemp(prefix="acmeocr-python-"))
    try:
        extracted_root = collapse_single_root_directory(extract_archive(archive_path, extract_dir))
        copy_tree(extracted_root, python_root)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

    flatten_python_root_layout(python_root)
    python_bin = find_python_executable(python_root, platform_label)
    metadata = {
        "provider": "python-build-standalone",
        "upstreamUrl": url,
        "upstreamArchive": archive_path.name,
        "pythonBuildStandaloneRelease": resolved_release,
    }
    return python_bin, metadata


def build_bundle(args: argparse.Namespace) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    output_dir = (repo_root / args.output_dir).resolve()
    worker_src = (repo_root / args.worker_src).resolve()
    requirements_file = (repo_root / args.requirements).resolve()
    download_cache_dir = (repo_root / args.download_cache_dir).resolve()
    wheelhouse = (repo_root / args.wheelhouse).resolve() if args.wheelhouse else None

    output_dir.mkdir(parents=True, exist_ok=True)
    download_cache_dir.mkdir(parents=True, exist_ok=True)

    bundle_name = args.bundle_name or f"runtime-bundle-{args.platform}-{args.version}"
    archive_path = output_dir / f"{bundle_name}.zip"

    staging_parent = Path(tempfile.mkdtemp(prefix="acmeocr-runtime-"))
    staging_dir = staging_parent / bundle_name
    bundle_root = staging_dir
    python_root = bundle_root / "python"
    worker_root = bundle_root / "worker"

    bundle_root.mkdir(parents=True, exist_ok=True)
    provider = provider_for_platform(args.python_provider, args.platform)
    print(f"Building runtime bundle in {staging_dir}")
    print(f"Python provider: {provider}")

    try:
        if provider == "local-venv":
            python_bin, provider_metadata = acquire_python_from_local_venv(
                python_root,
                builder_python=args.python_executable,
                platform_label=args.platform,
            )
        elif provider == "python-org-embed":
            if args.platform != "windows-x64":
                raise RuntimeError("python-org-embed mode currently supports only windows-x64")
            python_bin, provider_metadata = acquire_python_from_python_org_embed(
                python_root,
                cache_dir=download_cache_dir,
                python_version=args.python_version,
                source_url=args.python_source_url or None,
                force_redownload=args.force_redownload,
            )
        else:
            python_bin, provider_metadata = acquire_python_from_pbs(
                python_root,
                cache_dir=download_cache_dir,
                python_version=args.python_version,
                platform_label=args.platform,
                release_tag=args.python_build_standalone_release,
                source_url=args.python_source_url or None,
                force_redownload=args.force_redownload,
            )

        bootstrap_pip(
            python_bin,
            provider=provider,
            cache_dir=download_cache_dir,
            force_redownload=args.force_redownload,
        )
        pip_install_runtime(
            python_bin=python_bin,
            requirements_file=requirements_file,
            wheelhouse=wheelhouse,
            pip_index_url=args.pip_index_url or None,
        )
        copy_worker_tree(worker_src, worker_root)

        metadata = {
            "version": args.version,
            "platform": args.platform,
            "builtAt": datetime.now(timezone.utc).isoformat(),
            "pythonVersion": args.python_version,
            "pythonExecutable": str(python_bin.relative_to(staging_dir)),
            "workerSource": str(worker_src.relative_to(repo_root)),
            "requirementsFile": str(requirements_file.relative_to(repo_root)),
            "wheelhouse": str(wheelhouse) if wheelhouse is not None else None,
            **provider_metadata,
        }
        write_runtime_manifest(staging_dir, metadata)

        zip_directory(staging_dir, archive_path)
        checksum = sha256_file(archive_path)
        (archive_path.with_suffix(".zip.sha256")).write_text(
            f"{checksum}  {archive_path.name}\n",
            encoding="utf-8",
        )

        print(f"Created: {archive_path}")
        print(f"SHA256: {checksum}")
        return archive_path
    finally:
        if args.keep_staging:
            print(f"Keeping staging directory: {staging_dir}")
        else:
            shutil.rmtree(staging_parent, ignore_errors=True)


def main() -> None:
    args = parse_args()
    build_bundle(args)


if __name__ == "__main__":
    main()
