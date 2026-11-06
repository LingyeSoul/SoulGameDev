"""Import a SpriteKiln render as a first-class SoulGameDev sprite asset.

SpriteKiln owns YAML -> 8-direction atlas -> PNG/JSON/normal/emissive. This
bridge copies a render into ``art/sprites/<name>/`` and writes
``art/_meta/spritekiln.json`` with frames converted to the same ``[row, column]``
convention as ``atlas.json``.

Examples:
    python scripts/kiln_import.py --root . --name knight --render-dir art/specs/characters/knight/out/knight
    python scripts/kiln_import.py --root . --name knight --spec art/specs/characters/knight/knight.yaml --render
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RESOURCE_PREFIX = "res://"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
WINDOWS_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


def validate_name(name: str) -> None:
    if NAME_PATTERN.fullmatch(name) is None:
        raise SystemExit(
            f"invalid asset name {name!r}; use letters, digits, '_' and '-'"
        )
    if name.upper() in WINDOWS_RESERVED:
        raise SystemExit(f"invalid asset name {name!r}; Windows reserved device name")


def read_json_object(path: Path, label: str) -> dict:
    if not path.exists():
        raise SystemExit(f"{label} missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object for {label}")
    return data


def find_spritekiln() -> str:
    executable = shutil.which("spritekiln")
    if executable is not None:
        return executable
    name = "spritekiln.exe" if sys.platform == "win32" else "spritekiln"
    candidates = [Path(sys.executable).parent / name]
    if sys.platform == "win32":
        candidates.append(Path(sys.executable).parent / "Scripts" / name)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise SystemExit(
        "spritekiln is not available. Run `python -m pip install -r requirements.txt` "
        "in the project environment."
    )


def run_render(spec: Path, output_dir: Path, root: Path) -> None:
    executable = find_spritekiln()
    command = [executable, "render", str(spec), "-o", str(output_dir), "--force"]
    try:
        subprocess.run(command, cwd=root, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"spritekiln render failed with exit code {exc.returncode}") from exc


def load_render(render_dir: Path, name: str) -> tuple[dict, dict]:
    atlas_path = render_dir / f"{name}.json"
    if not atlas_path.exists():
        raise SystemExit(f"render atlas missing: {atlas_path}")
    data = read_json_object(atlas_path, "render atlas")
    kiln = data.get("spritekiln")
    if not isinstance(kiln, dict):
        raise SystemExit(f"{atlas_path}: missing the spritekiln metadata block")
    if kiln.get("name") != name:
        raise SystemExit(
            f"{atlas_path}: spec name is {kiln.get('name')!r}, expected {name!r}"
        )
    frames = data.get("frames")
    if not isinstance(frames, dict):
        raise SystemExit(f"{atlas_path}: expected an Aseprite frames object")
    return data, kiln


def build_sprite(render_dir: Path, name: str, data: dict, kiln: dict) -> dict:
    frames = data["frames"]
    cell = kiln.get("frame_size")
    if not isinstance(cell, int) or cell <= 0:
        raise SystemExit(f"{render_dir}: spritekiln.frame_size must be a positive integer")

    pivot = kiln.get("pivot")
    if (
        not isinstance(pivot, dict)
        or not isinstance(pivot.get("x"), (int, float))
        or not isinstance(pivot.get("y"), (int, float))
    ):
        raise SystemExit(f"{render_dir}: spritekiln.pivot.x and pivot.y must be numbers")

    animations: dict[str, dict] = {}
    animations_data = kiln.get("animations")
    if not isinstance(animations_data, dict) or not animations_data:
        raise SystemExit(f"{render_dir}: spritekiln.animations must be a non-empty object")
    for animation_name, animation in animations_data.items():
        if not isinstance(animation, dict):
            raise SystemExit(f"{render_dir}: animation {animation_name!r} must be an object")
        direction_map = animation.get("directions")
        if not isinstance(direction_map, dict):
            raise SystemExit(f"{render_dir}: animation {animation_name!r} needs a directions map")
        directions: dict[str, dict] = {}
        for direction, info in direction_map.items():
            if not isinstance(info, dict):
                raise SystemExit(f"{render_dir}: direction {direction!r} must be an object")
            row = info.get("row")
            if not isinstance(row, int) or row < 0:
                raise SystemExit(f"{render_dir}: direction {direction!r} needs a non-negative row")
            frame_names = info.get("frames")
            durations = info.get("durations")
            if not isinstance(frame_names, list) or not isinstance(durations, list):
                raise SystemExit(
                    f"{render_dir}: direction {direction!r} needs frames and durations lists"
                )
            if len(frame_names) != len(durations):
                raise SystemExit(
                    f"{render_dir}: direction {direction!r} has {len(frame_names)} frames "
                    f"but {len(durations)} durations"
                )
            if not all(isinstance(value, (int, float)) and value > 0 for value in durations):
                raise SystemExit(f"{render_dir}: direction {direction!r} has invalid durations")
            cells: list[list[int]] = []
            for frame_name in frame_names:
                entry = frames.get(frame_name)
                if entry is None:
                    raise SystemExit(f"{render_dir}: frame {frame_name!r} missing from atlas")
                if entry.get("rotated") or entry.get("trimmed"):
                    raise SystemExit(
                        f"{render_dir}: frame {frame_name!r} is rotated/trimmed; "
                        "the bridge expects a plain grid"
                    )
                rect = entry.get("frame")
                if not isinstance(rect, dict):
                    raise SystemExit(f"{render_dir}: frame {frame_name!r} has no rect")
                rect_width = rect.get("w")
                rect_height = rect.get("h")
                rect_x = rect.get("x")
                rect_y = rect.get("y")
                if not all(isinstance(value, int) for value in (rect_width, rect_height, rect_x, rect_y)):
                    raise SystemExit(f"{render_dir}: frame {frame_name!r} has a non-integer rect")
                if rect_width != cell or rect_height != cell:
                    raise SystemExit(
                        f"{render_dir}: frame {frame_name!r} is {rect_width}x{rect_height}, "
                        f"expected {cell}x{cell}"
                    )
                if rect_x % cell != 0 or rect_y != row * cell:
                    raise SystemExit(
                        f"{render_dir}: frame {frame_name!r} is at ({rect_x}, {rect_y}), "
                        f"not grid cell row {row}"
                    )
                cells.append([row, rect_x // cell])
            directions[direction] = {
                "row": row,
                "frames": cells,
                "durations": durations,
                "events": info.get("events", {}),
                "sockets": info.get("sockets", {}),
            }
        animations[animation_name] = {
            "loop": bool(animation.get("loop", True)),
            "directions": directions,
        }

    return {
        "sheet": f"{RESOURCE_PREFIX}art/sprites/{name}/{name}.png",
        "atlas": f"{RESOURCE_PREFIX}art/sprites/{name}/{name}.json",
        "normal": f"{RESOURCE_PREFIX}art/sprites/{name}/{name}_normal.png",
        "emissive": f"{RESOURCE_PREFIX}art/sprites/{name}/{name}_emissive.png",
        "cell": [cell, cell],
        "pivot": [float(pivot["x"]), float(pivot["y"])],
        "directions": list(kiln.get("directions", [])),
        "view": kiln.get("view"),
        "animations": animations,
    }


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"format": 1, "sprites": {}}
    data = read_json_object(path, "manifest")
    if not isinstance(data.get("sprites"), dict):
        raise SystemExit(f"{path}: expected an object with a sprites map")
    return data


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def copy_runtime(render_dir: Path, target: Path, name: str) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "_normal", "_emissive"):
        filename = f"{name}{suffix}.png"
        source = render_dir / filename
        if not source.exists():
            raise SystemExit(f"render file missing: {source}")
        shutil.copy2(source, target / filename)
    atlas = render_dir / f"{name}.json"
    if not atlas.exists():
        raise SystemExit(f"render atlas missing: {atlas}")
    shutil.copy2(atlas, target / atlas.name)
    qa = render_dir / "qa.json"
    if not qa.exists():
        raise SystemExit(f"render QA missing: {qa}")
    shutil.copy2(qa, target / qa.name)


def require_qa(render_dir: Path) -> dict:
    qa_path = render_dir / "qa.json"
    qa = read_json_object(qa_path, "render QA")
    if qa.get("ok") is not True:
        raise SystemExit(f"render QA failed: {qa.get('errors', 'unknown error')}")
    return qa


def import_render(root: Path, render_dir: Path, name: str) -> None:
    validate_name(name)
    if not render_dir.is_dir():
        raise SystemExit(f"render folder missing: {render_dir}")
    require_qa(render_dir)
    data, kiln = load_render(render_dir, name)
    sprite = build_sprite(render_dir, name, data, kiln)

    sprites_root = (root / "art" / "sprites").resolve()
    target = (sprites_root / name).resolve()
    if not target.is_relative_to(sprites_root):
        raise SystemExit(f"asset target escapes art/sprites: {target}")
    copy_runtime(render_dir, target, name)

    manifest_path = root / "art" / "_meta" / "spritekiln.json"
    manifest = load_manifest(manifest_path)
    manifest["sprites"][name] = sprite
    write_manifest(manifest_path, manifest)
    print(f"[kiln] {name} -> art/sprites/{name}/ and art/_meta/spritekiln.json (QA ok)")


def resource_path(root: Path, value: str) -> Path:
    if value.startswith(RESOURCE_PREFIX):
        return root / value[len(RESOURCE_PREFIX):]
    return root / value


def png_size(path: Path) -> tuple[int, int]:
    if not path.exists():
        raise SystemExit(f"PNG missing: {path}")
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SystemExit(f"{path}: not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    if width <= 0 or height <= 0:
        raise SystemExit(f"{path}: invalid PNG dimensions {width}x{height}")
    return width, height


def check_sprite(root: Path, name: str, sprite: dict) -> None:
    for field in ("sheet", "atlas", "normal", "emissive"):
        value = sprite.get(field)
        if not isinstance(value, str):
            raise SystemExit(f"sprite[{name}]: missing {field!r} path")
        if not resource_path(root, value).exists():
            raise SystemExit(f"sprite[{name}]: {field} file missing: {resource_path(root, value)}")

    cell = sprite.get("cell")
    if (
        not isinstance(cell, list)
        or len(cell) != 2
        or not all(isinstance(value, int) and value > 0 for value in cell)
    ):
        raise SystemExit(f"sprite[{name}]: cell must be [width, height]")
    if cell[0] != cell[1]:
        raise SystemExit(f"sprite[{name}]: the bridge expects a square cell, got {cell}")

    pivot = sprite.get("pivot")
    if (
        not isinstance(pivot, list)
        or len(pivot) != 2
        or not all(isinstance(value, (int, float)) for value in pivot)
    ):
        raise SystemExit(f"sprite[{name}]: pivot must be [x, y]")

    sheet_path = resource_path(root, sprite["sheet"])
    sheet_width, sheet_height = png_size(sheet_path)
    if sheet_width % cell[0] != 0 or sheet_height % cell[1] != 0:
        raise SystemExit(
            f"sprite[{name}]: sheet {sheet_width}x{sheet_height} is not divisible by cell {cell}"
        )
    if not 0 <= float(pivot[0]) <= sheet_width or not 0 <= float(pivot[1]) <= sheet_height:
        raise SystemExit(f"sprite[{name}]: pivot {pivot} is outside the sheet")
    for field in ("normal", "emissive"):
        if png_size(resource_path(root, sprite[field])) != (sheet_width, sheet_height):
            raise SystemExit(f"sprite[{name}]: {field} size differs from the sheet")

    qa_path = sheet_path.parent / "qa.json"
    qa = read_json_object(qa_path, "QA")
    if qa.get("ok") is not True:
        raise SystemExit(f"sprite[{name}]: QA is not ok: {qa.get('errors', 'unknown error')}")

    atlas_path = resource_path(root, sprite["atlas"])
    atlas = read_json_object(atlas_path, "atlas")
    meta = atlas.get("meta")
    if not isinstance(meta, dict) or meta.get("size") != {"w": sheet_width, "h": sheet_height}:
        raise SystemExit(f"{atlas_path}: meta.size does not match the sheet")

    atlas_kiln = atlas.get("spritekiln")
    if not isinstance(atlas_kiln, dict):
        raise SystemExit(f"{atlas_path}: spritekiln metadata missing")
    atlas_cell = atlas_kiln.get("frame_size")
    if not isinstance(atlas_cell, int) or cell != [atlas_cell, atlas_cell]:
        raise SystemExit(f"{atlas_path}: frame_size {atlas_cell!r} does not match cell {cell}")
    atlas_pivot = atlas_kiln.get("pivot")
    if (
        not isinstance(atlas_pivot, dict)
        or not isinstance(atlas_pivot.get("x"), (int, float))
        or not isinstance(atlas_pivot.get("y"), (int, float))
        or abs(float(atlas_pivot["x"]) - float(pivot[0])) > 0.01
        or abs(float(atlas_pivot["y"]) - float(pivot[1])) > 0.01
    ):
        raise SystemExit(f"{atlas_path}: pivot does not match {pivot}")

    atlas_frames = atlas.get("frames")
    if not isinstance(atlas_frames, dict) or not atlas_frames:
        raise SystemExit(f"{atlas_path}: frames must be a non-empty object")
    for frame_name, entry in atlas_frames.items():
        rect = entry.get("frame") if isinstance(entry, dict) else None
        if (
            not isinstance(rect, dict)
            or rect.get("w") != cell[0]
            or rect.get("h") != cell[1]
        ):
            raise SystemExit(f"{atlas_path}: frame {frame_name!r} does not match cell {cell}")
        if entry.get("rotated") or entry.get("trimmed"):
            raise SystemExit(f"{atlas_path}: frame {frame_name!r} is rotated/trimmed")

    directions = sprite.get("directions")
    if (
        not isinstance(directions, list)
        or not directions
        or not all(isinstance(value, str) and value for value in directions)
        or len(set(directions)) != len(directions)
    ):
        raise SystemExit(f"sprite[{name}]: directions must be a non-empty list of unique strings")
    declared_directions = set(directions)

    animations = sprite.get("animations")
    if not isinstance(animations, dict) or not animations:
        raise SystemExit(f"sprite[{name}]: animations must be a non-empty object")
    for animation_name, animation in animations.items():
        if not isinstance(animation, dict):
            raise SystemExit(f"sprite[{name}]: animation {animation_name!r} must be an object")
        if not isinstance(animation.get("loop"), bool):
            raise SystemExit(f"sprite[{name}]: animation {animation_name!r} loop must be boolean")
        directions_map = animation.get("directions")
        if not isinstance(directions_map, dict) or not directions_map:
            raise SystemExit(f"sprite[{name}]: animation {animation_name!r} needs directions")
        for direction, info in directions_map.items():
            if direction not in declared_directions:
                raise SystemExit(
                    f"sprite[{name}]: animation {animation_name!r} uses unknown direction {direction!r}"
                )
            if not isinstance(info, dict):
                raise SystemExit(f"sprite[{name}]: direction {direction!r} must be an object")
            row = info.get("row")
            frames = info.get("frames")
            durations = info.get("durations")
            events = info.get("events", {})
            sockets = info.get("sockets", {})
            if not isinstance(row, int) or row < 0:
                raise SystemExit(f"sprite[{name}]: direction {direction!r} has no row")
            if not isinstance(frames, list) or not isinstance(durations, list):
                raise SystemExit(f"sprite[{name}]: direction {direction!r} needs frames/durations")
            if len(frames) != len(durations):
                raise SystemExit(f"sprite[{name}]: direction {direction!r} frame/duration mismatch")
            if not all(isinstance(value, (int, float)) and value > 0 for value in durations):
                raise SystemExit(f"sprite[{name}]: direction {direction!r} has invalid durations")
            if not isinstance(events, dict) or not all(
                isinstance(key, str) and isinstance(value, list) and all(isinstance(item, str) for item in value)
                for key, value in events.items()
            ):
                raise SystemExit(f"sprite[{name}]: direction {direction!r} has invalid events")
            if not isinstance(sockets, dict) or not all(
                isinstance(value, list)
                and len(value) == len(frames)
                and all(
                    isinstance(position, list)
                    and len(position) == 3
                    and all(isinstance(number, (int, float)) for number in position)
                    for position in value
                )
                for value in sockets.values()
            ):
                raise SystemExit(f"sprite[{name}]: direction {direction!r} has invalid sockets")
            for frame in frames:
                if (
                    not isinstance(frame, list)
                    or len(frame) != 2
                    or not all(isinstance(value, int) and value >= 0 for value in frame)
                ):
                    raise SystemExit(f"sprite[{name}]: invalid frame {frame!r}")
                frame_row, frame_column = frame
                if frame_row != row:
                    raise SystemExit(f"sprite[{name}]: frame row {frame_row} != {row}")
                if (
                    (frame_column + 1) * cell[0] > sheet_width
                    or (frame_row + 1) * cell[1] > sheet_height
                ):
                    raise SystemExit(f"sprite[{name}]: frame {frame!r} exceeds the sheet")


def check_manifest(root: Path, name: str | None, require_manifest: bool) -> None:
    path = root / "art" / "_meta" / "spritekiln.json"
    if not path.exists():
        if require_manifest or name is not None:
            raise SystemExit(f"manifest missing: {path}")
        print("[kiln] no spritekiln manifest; nothing to check")
        return
    manifest = load_manifest(path)
    sprites = manifest["sprites"]
    if not sprites:
        raise SystemExit(f"{path}: no sprites to check")
    names = sorted(sprites) if name is None else [name]
    for sprite_name in names:
        sprite = sprites.get(sprite_name)
        if not isinstance(sprite, dict):
            raise SystemExit(f"{path}: sprite {sprite_name!r} missing")
        check_sprite(root, sprite_name, sprite)
        print(f"[kiln] check ok: {sprite_name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import or validate SpriteKiln renders for a SoulGameDev project."
    )
    parser.add_argument("--root", type=Path, required=True, help="project root")
    parser.add_argument("--name", help="asset key; must match the spec name")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate spritekiln.json and every referenced file, without importing",
    )
    parser.add_argument(
        "--require-manifest",
        action="store_true",
        help="with --check, fail when spritekiln.json is absent",
    )
    source = parser.add_mutually_exclusive_group(required=False)
    source.add_argument("--render-dir", type=Path, help="existing render folder")
    source.add_argument("--render", action="store_true", help="render the spec first")
    parser.add_argument("--spec", type=Path, help="SpriteKiln YAML spec, required with --render")
    args = parser.parse_args()

    if args.name is not None:
        validate_name(args.name)
    if args.require_manifest and not args.check:
        parser.error("--require-manifest requires --check")

    root = args.root.resolve()
    if args.check:
        if args.render or args.render_dir is not None or args.spec is not None:
            parser.error("--check cannot be combined with render options")
        check_manifest(root, args.name, args.require_manifest)
        return

    if args.name is None:
        parser.error("--name is required unless --check is used")
    if not args.render and args.render_dir is None:
        parser.error("--render-dir or --render is required")
    if args.render and args.spec is None:
        parser.error("--render requires --spec")
    if args.spec is not None and not args.render:
        parser.error("--spec is only used with --render")

    if args.render:
        spec = args.spec if args.spec.is_absolute() else (root / args.spec)
        with tempfile.TemporaryDirectory(prefix="soulgame-kiln-") as temporary:
            render_dir = Path(temporary)
            run_render(spec, render_dir, root)
            import_render(root, render_dir, args.name)
        return

    render_dir = args.render_dir if args.render_dir.is_absolute() else (root / args.render_dir)
    import_render(root, render_dir, args.name)


if __name__ == "__main__":
    main()
