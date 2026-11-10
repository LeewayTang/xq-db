from dataclasses import dataclass

UTF8_BOM = b"\xef\xbb\xbf"
ENCODINGS = ("utf-8", "gb18030", "big5")

# 常用汉字与文言高频字，用于在多个可解码结果中挑选最可信的一个。
COMMON = set(
    "的一是不了在人有我他她它这那为之大来以个中上们到说国和地也子时道出"
    "而要于就下得可你年生自会那后能对着事其里所去行过家十用发天如然作方"
    "成者多日都三小军二无同么经法当起与好看学进种将还分此心前面又定见只"
    "主没公从知全现点情明力理外问间由题手机关开并体合正实系但业因很最重"
    "物被给等已几口两长山金指便美再书决西革反处让死向信更回比或报吃老四"
    "解至则听声王门东南北中春秋左氏传郑伯克段于鄢伯仲叔季侯将相君子曰诗"
    "书礼乐仁义道德阴阳天地皇帝臣民父母兄弟夫妻男女老少生鬼神祭祀卜筮木"
    "水火土风雨雷电山川河海州郡县邑都城镇乡村田野道路车马兵戈甲胄弓矢剑"
    "戟旗鼓钟磬鼎彝圭璧帛币粟米麦豆桑麻丝漆皮革竹陶瓦宫室台榭郭沟池社稷"
    "宗庙朝聘盟会征伐侵袭弑奔逃囚执杀戮赏罚爵禄封赐田宅奴婢宾客师徒朋友"
    "仇雠婚姻丧葬疾病医药巫觋祝史梦兆怪异祥瑞灾祸饥馑疾疫螟蝗旱地震崩蚀"
    "星陨彗孛問問題為與國學時東長門馬車見言語說聽聲書寫讀"
)


def _plausibility(text: str) -> float:
    chars = [ch for ch in text if not ch.isspace()]
    if not chars:
        return 0.0
    cjk = sum(1 for ch in chars if "一" <= ch <= "鿿")
    common = sum(1 for ch in chars if ch in COMMON)
    return cjk / len(chars) + 0.5 * common / len(chars)


@dataclass(frozen=True)
class Decoded:
    text: str
    encoding: str
    replacement_ratio: float
    had_bom: bool


def decode_bytes(data: bytes) -> Decoded:
    had_bom = data.startswith(UTF8_BOM)
    body = data[len(UTF8_BOM):] if had_bom else data

    best: tuple[float, str, str] | None = None
    for encoding in ENCODINGS:
        try:
            text = body.decode(encoding)
        except UnicodeDecodeError:
            continue
        score = _plausibility(text)
        if best is None or score > best[0]:
            best = (score, encoding, text)

    if best is not None:
        _, encoding, text = best
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
