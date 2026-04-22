from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from release_utils import sha256_file, write_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate release manifests for AcmeOCR")
    parser.add_argument("--owner", required=True, help="GitHub owner")
    parser.add_argument("--repo", required=True, help="GitHub repository name")
    parser.add_argument("--tag", required=True, help="GitHub release tag, e.g. v0.1.0")
    parser.add_argument("--app-version", required=True, help="Application version")
    parser.add_argument(
        "--output-dir",
        default="dist/release-manifests",
        help="Directory to write generated manifest files",
    )
    parser.add_argument(
        "--runtime",
        action="append",
        default=[],
        help="Runtime mapping in the form <platform>=<path-to-zip>",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Model mapping in the form <name>=<path-to-zip>",
    )
    return parser.parse_args()


def parse_mapping(entries: list[str]) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid mapping entry: {entry}")
        key, raw_path = entry.split("=", 1)
        parsed[key] = Path(raw_path).resolve()
    return parsed


def release_asset_url(owner: str, repo: str, tag: str, asset_name: str) -> str:
    return f"https://github.com/{owner}/{repo}/releases/download/{tag}/{asset_name}"


def build_model_entry(owner: str, repo: str, tag: str, name: str, path: Path) -> dict[str, object]:
    return {
        "name": name,
        "version": tag.removeprefix("v"),
        "url": release_asset_url(owner, repo, tag, path.name),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def build_runtime_entry(owner: str, repo: str, tag: str, path: Path) -> dict[str, object]:
    return {
        "version": tag.removeprefix("v"),
        "url": release_asset_url(owner, repo, tag, path.name),
        "sha256": sha256_file(path),
        "size": path.stat().st_size,
    }


def build_manifest(
    owner: str,
    repo: str,
    tag: str,
    app_version: str,
    platform: str,
    runtime_path: Path,
    models: dict[str, Path],
) -> dict[str, object]:
    return {
        "platform": platform,
        "appVersion": app_version,
        "runtime": build_runtime_entry(owner, repo, tag, runtime_path),
        "models": [
            build_model_entry(owner, repo, tag, model_name, model_path)
            for model_name, model_path in models.items()
        ],
        "features": [],
        "minAppVersion": app_version,
    }


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    runtimes = parse_mapping(args.runtime)
    models = parse_mapping(args.model)
    if not runtimes:
        raise ValueError("At least one --runtime entry is required")
    if not models:
        raise ValueError("At least one --model entry is required")

    for platform, runtime_path in runtimes.items():
        manifest = build_manifest(
            owner=args.owner,
            repo=args.repo,
            tag=args.tag,
            app_version=args.app_version,
            platform=platform,
            runtime_path=runtime_path,
            models=models,
        )
        write_json(output_dir / f"{platform}.json", manifest)
        print(f"Generated manifest: {output_dir / f'{platform}.json'}")


if __name__ == "__main__":
    main()

