from opencc import OpenCC

_converter = OpenCC("t2s")


def to_simplified(text: str) -> str:
    return _converter.convert(text)
