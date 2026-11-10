from xqdb.review.rules import check_text, grade, hamming, simhash64


def test_encoding_finding():
    f = check_text("正常" * 100 + "�" * 5)
    assert any(x.kind == "encoding_corrupt" for x in f)
    assert grade(f, "正常" * 100) == "Q"


def test_empty_or_toc_is_c():
    assert grade([], "目录") == "C"


def test_varied_text_is_a():
    text = "".join(chr(0x4E00 + i) for i in range(300))
    assert grade([], text) == "A"


def test_near_duplicate_detected():
    a = "左传隐公元年郑伯克段于鄢" * 20
    b = a[:-1] + "也"
    assert hamming(simhash64(a), simhash64(b)) <= 4


def test_fragmentary_and_low_information():
    assert any(x.kind == "fragmentary" for x in check_text("目录"))
    repeated = "子曰" * 200
    assert any(x.kind == "low_information" for x in check_text(repeated))


def test_known_duplicate_flagged():
    text = "左传隐公元年郑伯克段于鄢" * 20
    known = {"other": simhash64(text)}
    findings = check_text(text, known_hashes=known)
    assert any(x.kind == "high_duplication" for x in findings)


def test_truncated_open_bracket():
    text = "子曰" * 100 + "（"
    assert any(x.kind == "truncated" for x in check_text(text))
