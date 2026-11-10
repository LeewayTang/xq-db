import hashlib
from collections import Counter


def _tokens(text: str, width: int = 2) -> list[str]:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return []
    if len(chars) <= width:
        return chars
    return ["".join(chars[i:i + width]) for i in range(len(chars) - width + 1)]


def simhash64(text: str, width: int = 2) -> str:
    tokens = _tokens(text, width)
    if not tokens:
        return "0" * 16

    bits = [0] * 64
    for token, weight in Counter(tokens).items():
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        for i in range(64):
            bits[i] += weight if (value >> i) & 1 else -weight

    signature = 0
    for i, weight in enumerate(bits):
        if weight > 0:
            signature |= 1 << i
    return f"{signature:016x}"


def hamming(a: str, b: str) -> int:
    return (int(a, 16) ^ int(b, 16)).bit_count()
