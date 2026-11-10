import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawFile:
    path: Path
    rel_path: str
    sha256: str
    size: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enumerate_corpus(root: Path) -> list[RawFile]:
    files: list[RawFile] = []
    for path in root.rglob("*.txt"):
        if not path.is_file():
            continue
        files.append(RawFile(
            path=path,
            rel_path=path.relative_to(root).as_posix(),
            sha256=_sha256(path),
            size=path.stat().st_size,
        ))
    return sorted(files, key=lambda item: item.rel_path)


def fetch_repo(dest: Path, url: str) -> Path:
    if (dest / ".git").exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(dest)],
        check=True,
    )
    return dest
