from dataclasses import dataclass

UTF8_BOM = b"\xef\xbb\xbf"
ENCODINGS = ("utf-8", "gb18030", "big5")


@dataclass(frozen=True)
class Decoded:
    text: str
    encoding: str
    replacement_ratio: float
    had_bom: bool


def decode_bytes(data: bytes) -> Decoded:
    had_bom = data.startswith(UTF8_BOM)
    body = data[len(UTF8_BOM):] if had_bom else data

    for encoding in ENCODINGS:
        try:
            text = body.decode(encoding)
        except UnicodeDecodeError:
            continue
        return Decoded(
            text=text,
            encoding=encoding,
            replacement_ratio=0.0,
            had_bom=had_bom,
        )

    text = body.decode("utf-8", errors="replace")
    ratio = text.count("�") / max(len(text), 1)
    return Decoded(
        text=text,
        encoding="utf-8",
        replacement_ratio=ratio,
        had_bom=had_bom,
    )
