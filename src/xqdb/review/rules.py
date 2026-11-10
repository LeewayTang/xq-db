from dataclasses import dataclass

from ..normalize.simhash import hamming, simhash64

OPEN_ENDINGS = "（《「『“‘([{"


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    evidence: str


def check_text(
    text: str,
    *,
    known_hashes: dict[str, str] | None = None,
    signature: str | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    total = max(len(text), 1)

    ratio = text.count("�") / total
    if ratio > 0.01:
        findings.append(Finding(
            "encoding_corrupt", "error", f"replacement ratio {ratio:.3f}"))

    effective = [ch for ch in text if not ch.isspace()]
    if len(effective) < 200:
        findings.append(Finding(
            "fragmentary", "warn", f"{len(effective)} effective chars"))

    unique = len(set(effective))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    line_repeat = 1 - len(set(lines)) / len(lines) if lines else 0.0
    if unique < 50 or (len(lines) >= 4 and line_repeat > 0.8):
        findings.append(Finding(
            "low_information", "warn",
            f"unique={unique}, line_repeat={line_repeat:.2f}"))

    stripped = text.rstrip()
    if stripped and stripped[-1] in OPEN_ENDINGS:
        findings.append(Finding(
            "truncated", "warn", f"ends with {stripped[-1]!r}"))

    if known_hashes:
        current = signature or simhash64(text)
        for other_id, other in known_hashes.items():
            if hamming(current, other) <= 3:
                findings.append(Finding(
                    "high_duplication", "warn", f"near {other_id}"))
                break

    return findings


def grade(findings: list[Finding], text: str) -> str:
    kinds = {finding.kind for finding in findings}
    if "encoding_corrupt" in kinds or "unparsable" in kinds:
        return "Q"

    effective = sum(1 for ch in text if not ch.isspace())
    if "fragmentary" in kinds or "low_information" in kinds or effective < 200:
        return "C"

    if findings:
        return "B"
    return "A"
