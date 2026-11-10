import pytest

from xqdb.catalog.sources import load_sources


def test_load_and_validate(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("""
daizhige:
  name: 殆知阁
  url: https://github.com/garychowcmu/daizhigev20
  license: unknown
  trust: tertiary
""", encoding="utf-8")
    src = load_sources(p)["daizhige"]
    assert src.trust == "tertiary"


def test_rejects_bad_trust(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("x: {name: x, url: x, license: x, trust: nope}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources(p)
