"""Discover per-asset generator modules and merge their metadata into atlas.json.

There is deliberately no central drawing code here. Add a new image by adding
one module under tools/art/<category>/<asset>.py; this file only orchestrates.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.art._lib.pixel_lib import preview

RESOURCE_PREFIX = "res://"
BACKGROUND = (18, 20, 26, 255)
EXCLUDED_NAMES = {"build.py", "__init__.py"}
EXCLUDED_DIRS = {"__pycache__", "_lib", "_data"}


def discover(art_tools: Path) -> list[Path]:
    modules: list[Path] = []
    for path in sorted(art_tools.rglob("*.py")):
        if path.name in EXCLUDED_NAMES:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        modules.append(path)
    if not modules:
        raise RuntimeError(f"no asset modules found under {art_tools}")
    return modules


def load_module(path: Path, art_tools: Path):
    relative = path.relative_to(art_tools).with_suffix("")
    module_name = "soul_asset_" + "_".join(relative.parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load asset module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise RuntimeError(f"{path}: asset module must expose build(root) -> dict")
    return module, relative.as_posix()


def merge(atlas: dict, metadata: dict, module_path: Path, root: Path) -> None:
    for field in ("kind", "key", "output"):
        if field not in metadata:
            raise RuntimeError(f"{module_path}: metadata is missing {field!r}")
    kind = metadata["kind"]
    key = str(metadata["key"])
    output = str(metadata["output"])
    asset_path = root / "art" / output
    if not asset_path.exists():
        raise RuntimeError(f"{module_path}: declared output does not exist: {asset_path}")

    if kind == "image":
        if key in atlas["images"] or key in atlas["sheets"]:
            raise RuntimeError(f"{module_path}: duplicate asset key {key!r}")
        atlas["images"][key] = f"{RESOURCE_PREFIX}art/{output}"
        return

    if kind != "sheet":
        raise RuntimeError(f"{module_path}: unknown kind {kind!r}; use 'sheet' or 'image'")
    for field in ("cell", "pivot", "animations"):
        if field not in metadata:
            raise RuntimeError(f"{module_path}: sheet metadata is missing {field!r}")
    if key in atlas["sheets"] or key in atlas["images"]:
        raise RuntimeError(f"{module_path}: duplicate asset key {key!r}")
    atlas["sheets"][key] = {
        "path": f"{RESOURCE_PREFIX}art/{output}",
        "cell": metadata["cell"],
        "pivot": metadata["pivot"],
        "animations": metadata["animations"],
    }


def write_atlas(root: Path, atlas: dict) -> Path:
    out = root / "art" / "_meta" / "atlas.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(atlas, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load_atlas(path: Path) -> dict:
    if not path.exists():
        return {"sheets": {}, "images": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "sheets" not in data or "images" not in data:
        raise RuntimeError(f"{path}: expected an object with sheets and images")
    return data


def merge_into_existing(existing: dict, fresh: dict) -> dict:
    """A partial rebuild updates its keys but keeps every other asset."""
    for key in fresh["sheets"]:
        existing["sheets"].pop(key, None)
        existing["images"].pop(key, None)
    for key in fresh["images"]:
        existing["sheets"].pop(key, None)
        existing["images"].pop(key, None)
    existing["sheets"].update(fresh["sheets"])
    existing["images"].update(fresh["images"])
    return existing


def render_previews(root: Path, atlas: dict) -> None:
    meta_dir = root / "art" / "_meta"
    for section in ("sheets", "images"):
        for key in sorted(atlas[section]):
            info = atlas[section][key]
            relative = info["path"] if isinstance(info, dict) else info
            if relative.startswith(RESOURCE_PREFIX):
                relative = relative[len(RESOURCE_PREFIX):]
            source = root / relative
            preview([source], meta_dir / f"preview_{key}.png", 1, 4, BACKGROUND)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build every per-asset art module.")
    parser.add_argument("--root", type=Path, required=True, help="project root")
    parser.add_argument("--only", nargs="+", default=None, help="module paths such as actors/player")
    parser.add_argument("--preview", action="store_true", help="write 4x contact previews")
    args = parser.parse_args()

    root = args.root.resolve()
    art_tools = root / "tools" / "art"
    if not art_tools.is_dir():
        raise SystemExit(f"missing {art_tools}; scaffold the template first")
    sys.path.insert(0, str(root))

    selected = discover(art_tools)
    if args.only is not None:
        wanted = set(args.only)
        selected = [
            path
            for path in selected
            if path.relative_to(art_tools).with_suffix("").as_posix() in wanted
        ]
        if not selected:
            raise SystemExit(f"no modules matched --only {sorted(wanted)}")

    atlas: dict = {"sheets": {}, "images": {}}
    for path in selected:
        module, relative = load_module(path, art_tools)
        metadata = module.build(root)
        merge(atlas, metadata, path, root)
        print(f"[art] {relative} -> art/{metadata['output']}")

    if args.only is not None:
        atlas = merge_into_existing(load_atlas(root / "art" / "_meta" / "atlas.json"), atlas)
    target = write_atlas(root, atlas)
    if args.preview:
        render_previews(root, atlas)
    print(f"[art] {len(selected)} module(s), atlas written to {target}")


if __name__ == "__main__":
    main()
