import hashlib
import json
import tarfile
from datetime import UTC, datetime
from pathlib import Path

import zstandard

LAYERS = (
    ("raw", "raw"),
    ("normalized", "corpus"),
    ("knowledge", "knowledge"),
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stats(src: Path) -> tuple[int, int]:
    files = [path for path in src.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


def _make_archive(src: Path, dest: Path) -> None:
    compressor = zstandard.ZstdCompressor(level=10)
    with (dest.open("wb") as handle,
          compressor.stream_writer(handle) as writer,
          tarfile.open(fileobj=writer, mode="w|") as tar):
        tar.add(src, arcname=src.name)


def build_release(root: Path, tag: str) -> Path:
    root = Path(root)
    out = root / "dist" / tag
    out.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%d")
    assets: list[dict] = []

    for label, dirname in LAYERS:
        src = root / "data" / dirname
        if not src.exists():
            continue
        files, size = _stats(src)
        if files == 0:
            continue
        name = f"{label}-{stamp}.tar.zst"
        dest = out / name
        _make_archive(src, dest)
        assets.append({
            "name": name,
            "layer": label,
            "files": files,
            "bytes": size,
            "sha256": _sha256_file(dest),
        })

    manifest = {
        "tag": tag,
        "created_at": now.isoformat(),
        "assets": assets,
    }
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
