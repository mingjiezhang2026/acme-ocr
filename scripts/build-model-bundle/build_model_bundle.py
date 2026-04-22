from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from release_utils import (  # noqa: E402
    collapse_single_root_directory,
    copy_tree,
    download_file,
    extract_archive,
    sha256_file,
    write_json,
    zip_directory,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build AcmeOCR model bundle from official Paddle artifacts")
    parser.add_argument("--version", required=True, help="Model bundle version")
    parser.add_argument(
        "--model-key",
        default="ppocr-zh",
        help="Catalog entry key, e.g. ppocr-zh",
    )
    parser.add_argument(
        "--catalog",
        default="scripts/build-model-bundle/paddle_model_catalog.json",
        help="Path to the Paddle model catalog JSON",
    )
    parser.add_argument(
        "--output-dir",
        default="dist/model-bundles",
        help="Directory for zip artifacts",
    )
    parser.add_argument(
        "--download-cache-dir",
        default="dist/upstream-cache",
        help="Directory used to cache upstream model downloads",
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
        help="Ignore cached upstream model archives",
    )
    return parser.parse_args()


def load_catalog(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_model_manifest(target_dir: Path, payload: dict[str, object]) -> None:
    write_json(target_dir / "metadata" / "model-manifest.json", payload)


def copy_component_archive(
    component: dict[str, str],
    cache_dir: Path,
    output_dir: Path,
    force_redownload: bool,
) -> dict[str, object]:
    url = component["url"]
    archive_name = Path(url).name
    archive_path = download_file(url, cache_dir / archive_name, force=force_redownload)
    extract_dir = Path(tempfile.mkdtemp(prefix=f"acmeocr-model-{component['name']}-"))
    try:
        extracted_root = collapse_single_root_directory(extract_archive(archive_path, extract_dir))
        component_dir = output_dir / component["name"]
        copy_tree(extracted_root, component_dir)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

    return {
        "name": component["name"],
        "artifact": component.get("artifact", component["name"]),
        "sourceUrl": url,
        "archiveName": archive_name,
    }


def build_bundle(args: argparse.Namespace) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = (repo_root / args.catalog).resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    cache_dir = (repo_root / args.download_cache_dir).resolve()

    catalog = load_catalog(catalog_path)
    if args.model_key not in catalog:
        raise KeyError(f"Model key not found in catalog: {args.model_key}")

    model_definition = catalog[args.model_key]
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    bundle_name = args.bundle_name or f"model-bundle-{args.model_key}-{args.version}"
    archive_path = output_dir / f"{bundle_name}.zip"

    staging_parent = Path(tempfile.mkdtemp(prefix="acmeocr-model-bundle-"))
    staging_dir = staging_parent / bundle_name
    bundle_root = staging_dir
    bundle_root.mkdir(parents=True, exist_ok=True)

    try:
        packaged_components: list[dict[str, object]] = []
        for component in model_definition["components"]:
            packaged_components.append(
                copy_component_archive(
                    component=component,
                    cache_dir=cache_dir,
                    output_dir=bundle_root,
                    force_redownload=args.force_redownload,
                )
            )

        manifest = {
            "bundleKey": args.model_key,
            "version": args.version,
            "builtAt": datetime.now(timezone.utc).isoformat(),
            "description": model_definition.get("description"),
            "upstreamDocs": model_definition.get("upstreamDocs"),
            "components": packaged_components,
        }
        write_model_manifest(bundle_root, manifest)

        zip_directory(bundle_root, archive_path)
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

