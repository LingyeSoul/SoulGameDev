"""Discover per-sound generator modules and merge their metadata into audio.json.

One module owns one output file. This orchestrator only imports, validates and
writes the manifest; it never synthesizes anything itself.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

RESOURCE_PREFIX = "res://"
EXCLUDED_NAMES = {"build.py", "__init__.py"}
EXCLUDED_DIRS = {"__pycache__", "_lib", "_data"}


def discover(audio_tools: Path) -> list[Path]:
    modules: list[Path] = []
    for path in sorted(audio_tools.rglob("*.py")):
        if path.name in EXCLUDED_NAMES:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        modules.append(path)
    if not modules:
        raise RuntimeError(f"no audio modules found under {audio_tools}")
    return modules


def load_module(path: Path, audio_tools: Path):
    relative = path.relative_to(audio_tools).with_suffix("")
    module_name = "soul_audio_" + "_".join(relative.parts)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load audio module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "build"):
        raise RuntimeError(f"{path}: audio module must expose build(root) -> dict")
    return module, relative.as_posix()


def merge(manifest: dict, metadata: dict, module_path: Path, root: Path) -> None:
    for field in ("kind", "key", "output", "bus", "loop"):
        if field not in metadata:
            raise RuntimeError(f"{module_path}: metadata is missing {field!r}")
    if metadata["kind"] != "audio":
        raise RuntimeError(f"{module_path}: kind must be 'audio', got {metadata['kind']!r}")
    key = str(metadata["key"])
    bus = str(metadata["bus"])
    if bus not in {"SFX", "Music", "Master"}:
        raise RuntimeError(f"{module_path}: bus must be SFX, Music or Master, got {bus!r}")
    output = str(metadata["output"])
    asset_path = root / "art" / output
    if not asset_path.exists():
        raise RuntimeError(f"{module_path}: declared output does not exist: {asset_path}")
    if key in manifest["clips"]:
        raise RuntimeError(f"{module_path}: duplicate audio key {key!r}")
    manifest["clips"][key] = {
        "path": f"{RESOURCE_PREFIX}art/{output}",
        "bus": bus,
        "loop": bool(metadata["loop"]),
    }


def write_manifest(root: Path, manifest: dict) -> Path:
    out = root / "art" / "_meta" / "audio.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return out


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"clips": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "clips" not in data:
        raise RuntimeError(f"{path}: expected an object with clips")
    return data


def merge_into_existing(existing: dict, fresh: dict) -> dict:
    """A partial rebuild updates its clips but keeps every other sound."""
    for key in fresh["clips"]:
        existing["clips"].pop(key, None)
    existing["clips"].update(fresh["clips"])
    return existing


def main() -> None:
    parser = argparse.ArgumentParser(description="Build every per-sound audio module.")
    parser.add_argument("--root", type=Path, required=True, help="project root")
    parser.add_argument("--only", nargs="+", default=None, help="module paths such as sfx/hit")
    args = parser.parse_args()

    root = args.root.resolve()
    audio_tools = root / "tools" / "audio"
    if not audio_tools.is_dir():
        raise SystemExit(f"missing {audio_tools}; scaffold the template first")
    sys.path.insert(0, str(root))

    selected = discover(audio_tools)
    if args.only is not None:
        wanted = set(args.only)
        selected = [
            path
            for path in selected
            if path.relative_to(audio_tools).with_suffix("").as_posix() in wanted
        ]
        if not selected:
            raise SystemExit(f"no modules matched --only {sorted(wanted)}")

    manifest: dict = {"clips": {}}
    for path in selected:
        module, relative = load_module(path, audio_tools)
        metadata = module.build(root)
        merge(manifest, metadata, path, root)
        print(f"[audio] {relative} -> art/{metadata['output']}")

    if args.only is not None:
        manifest = merge_into_existing(load_manifest(root / "art" / "_meta" / "audio.json"), manifest)
    target = write_manifest(root, manifest)
    print(f"[audio] {len(selected)} module(s), manifest written to {target}")


if __name__ == "__main__":
    main()
