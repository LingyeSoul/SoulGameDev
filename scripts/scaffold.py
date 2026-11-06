"""Copy the per-asset project template into an existing game repository.

The script refuses to overwrite anything. Run it once, then add one module per
output image or sound; the build orchestrators discover them automatically.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "project-template"


def copy_template(template: Path, target: Path, dry_run: bool) -> list[Path]:
    if not template.is_dir():
        raise SystemExit(f"template missing: {template}")
    if not target.is_dir():
        raise SystemExit(f"target is not a directory: {target}")

    copied: list[Path] = []
    conflicts: list[Path] = []
    for source in sorted(template.rglob("*")):
        if source.is_dir():
            continue
        relative = source.relative_to(template)
        destination = target / relative
        if destination.exists():
            conflicts.append(destination)
            continue
        copied.append(destination)

    if conflicts:
        listing = "\n".join(f"  {path}" for path in conflicts)
        raise SystemExit(f"refusing to overwrite existing files:\n{listing}")

    if dry_run:
        for destination in copied:
            print(f"[dry-run] {destination}")
        return copied

    for destination in copied:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template / destination.relative_to(target), destination)
        print(f"[scaffold] {destination}")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold the SoulGameDev asset pipelines.")
    parser.add_argument("--into", type=Path, required=True, help="existing project root")
    parser.add_argument("--dry-run", action="store_true", help="list files without copying")
    args = parser.parse_args()
    copied = copy_template(TEMPLATE, args.into.resolve(), args.dry_run)
    print(f"[scaffold] {len(copied)} file(s)")


if __name__ == "__main__":
    main()
