from xqdb.normalize.encoding import decode_bytes


def test_utf8():
    d = decode_bytes("左传".encode())
    assert d.text == "左传" and d.encoding == "utf-8" and d.replacement_ratio == 0


def test_utf8_bom():
    d = decode_bytes(b"\xef\xbb\xbf" + "论语".encode())
    assert d.text == "论语" and d.had_bom


def test_gb18030():
    d = decode_bytes("春秋".encode("gb18030"))
    assert d.text == "春秋" and d.encoding == "gb18030"


def test_invalid_bytes_reported():
    d = decode_bytes(b"\xff\xfe\xfa\xfb")
    assert d.replacement_ratio > 0
