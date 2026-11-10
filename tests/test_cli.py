from xqdb.cli import main


def test_version(capsys):
    assert main(["version"]) == 0
    assert "xqdb" in capsys.readouterr().out
