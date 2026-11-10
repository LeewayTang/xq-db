from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    title: str
    level: int
    lines: list[str] = field(default_factory=list)


@dataclass
class ParsedWork:
    title: str
    front_matter: list[str]
    sections: list[ParsedSection]


def strip_indent(line: str) -> str:
    return line.lstrip("　 \t")


def parse_daizhige_text(text: str, fallback_title: str) -> ParsedWork:
    front_matter: list[str] = []
    sections: list[ParsedSection] = []
    current: ParsedSection | None = None
    blank_pending = False

    for raw in text.splitlines():
        line = strip_indent(raw).rstrip()
        if not line:
            blank_pending = True
            continue

        if line.startswith("◇"):
            title = line[1:].strip() or fallback_title
            current = ParsedSection(title=title, level=1)
            sections.append(current)
            blank_pending = False
            continue

        if current is None:
            front_matter.append(line)
        else:
            if blank_pending and current.lines:
                current.lines.append("")
            current.lines.append(line)
        blank_pending = False

    if not sections:
        body = list(front_matter)
        front_matter = []
        sections = [ParsedSection(title=fallback_title, level=1, lines=body)]

    return ParsedWork(
        title=fallback_title,
        front_matter=front_matter,
        sections=sections,
    )
