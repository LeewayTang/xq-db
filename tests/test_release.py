import json
import tarfile

import zstandard

from xqdb.release import build_release


def _members(archive):
    with (zstandard.open(archive, "rb") as handle,
          tarfile.open(fileobj=handle, mode="r|") as tar):
        return tar.getnames()


def test_release_manifest_and_archives(tmp_path):
    for directory in ("data/raw", "data/corpus", "data/knowledge"):
        (tmp_path / directory).mkdir(parents=True)
    (tmp_path / "data/corpus/a.md").write_text("正文", encoding="utf-8")
    (tmp_path / "data/personal/secret.md").parent.mkdir()
    (tmp_path / "data/personal/secret.md").write_text("笔记", encoding="utf-8")

    out = build_release(tmp_path, "data-v0.0.1")
    manifest = json.loads((out / "MANIFEST.json").read_text("utf-8"))

    assert manifest["tag"] == "data-v0.0.1"
    assert any(a["name"].startswith("normalized-") for a in manifest["assets"])
    assert (out / "MANIFEST.json").exists()

    normalized = next(
        a for a in manifest["assets"] if a["name"].startswith("normalized-"))
    assert len(normalized["sha256"]) == 64
    assert normalized["files"] == 1
    names = _members(out / normalized["name"])
    assert any(name.endswith("a.md") for name in names)
    assert not any("personal" in name for name in names)
