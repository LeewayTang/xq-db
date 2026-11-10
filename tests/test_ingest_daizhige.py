import hashlib
import subprocess

from xqdb.ingest.daizhige import enumerate_corpus, fetch_repo


def test_enumerates_txt_only(tmp_path):
    (tmp_path / "儒藏" / "春秋").mkdir(parents=True)
    (tmp_path / "儒藏" / "春秋" / "左传.txt").write_text(
        "◇隐公元年\n正文", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    files = enumerate_corpus(tmp_path)
    assert [f.rel_path for f in files] == ["儒藏/春秋/左传.txt"]
    assert len(files[0].sha256) == 64


def test_keeps_empty_files_for_review(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"")
    files = enumerate_corpus(tmp_path)
    assert len(files) == 1 and files[0].size == 0
    assert files[0].sha256 == hashlib.sha256(b"").hexdigest()


def test_fetch_repo_clones_once(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    subprocess.run(["git", "init", "-q", str(src)], check=True)
    (src / "a.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "-C", str(src), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(src), "-c", "user.email=a@b", "-c", "user.name=a",
         "commit", "-qm", "init"], check=True)

    dest = fetch_repo(tmp_path / "dest", str(src))
    assert (dest / "a.txt").exists()
    assert fetch_repo(dest, str(src)) == dest
