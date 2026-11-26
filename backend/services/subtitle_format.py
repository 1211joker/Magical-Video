"""整理各平台提取的字幕片段，同时保留视频时间轴。"""
import math
import re
from dataclasses import dataclass, replace
from html import unescape


_CAPTION_TAG = re.compile(
    r"</?(?:c(?:\.[^\s.>]+)*|b|i|u|ruby|rt|v|lang|span|font|a|em|strong)(?:\s+[^>]+)?>"
    r"|<\d{2,}:\d{2}(?::\d{2})?[.,]\d{3}>",
    re.IGNORECASE,
)
_LINE_TAG = re.compile(r"</?(?:br|p|div)(?:\s+[^>]*)?/?>", re.IGNORECASE)
_CJK = r"\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af"
_EXTRA_SPACE = re.compile(
    rf"(?<=[{_CJK}]) (?=[{_CJK}])| (?=[，。！？、；：）】」』])|(?<=[（【「『]) "
)
_SPEAKER = r"(?:[-—–]|>>)[ \t]+"
_SENTENCE_END = re.compile(
    rf"""[。！？]+[”’」』）》】]*|[.!?]+["'”’)\]]*(?=\s|$)|\n(?={_SPEAKER})"""
)
_ABBREVIATION = re.compile(r"\b(?:[A-Z]|[eE]\.g|[iI]\.e|Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs)\.$")
_MAX_JOIN_GAP = 0.7
_MAX_JOIN_SECONDS = 8
_MAX_JOIN_LENGTH = 120


@dataclass(frozen=True)
class _Cue:
    start: float
    end: float
    text: str


def _compact(text: str) -> str:
    return _EXTRA_SPACE.sub("", " ".join(text.split()))


def _read_cues(segments: list[dict]) -> list[_Cue]:
    cues = []
    for segment in segments:
        text = segment.get("text")
        if not isinstance(text, str):
            continue
        try:
            start, end = float(segment["start_time"]), float(segment["end_time"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
            continue
        text = _LINE_TAG.sub("\n", text)
        lines = (_compact(unescape(_CAPTION_TAG.sub("", line))) for line in text.splitlines())
        cleaned = "\n".join(line for line in lines if line)
        if cleaned:
            cues.append(_Cue(start, max(end, start + 0.001), cleaned))
    return sorted(cues, key=lambda cue: cue.start)


def _remove_rollover(cues: list[_Cue]) -> list[_Cue]:
    """滚动字幕有时会把上一行原样放在新字幕的第一行。"""
    distinct = []
    for cue in cues:
        previous = distinct[-1] if distinct else None
        if previous and cue.start <= previous.end + 0.04:
            if cue.text == previous.text and (
                cue.start < previous.end or min(cue.end - cue.start, previous.end - previous.start) <= 0.04
            ):
                distinct[-1] = replace(previous, end=max(previous.end, cue.end))
                continue
            first, _, remainder = cue.text.partition("\n")
            if remainder and first == previous.text.rsplit("\n", 1)[-1]:
                cue = replace(cue, text=remainder)
        distinct.append(cue)
    return distinct


def _sentence_parts(cue: _Cue, end: float):
    """用原片段范围估算片段内部的断句时间。"""
    text = cue.text
    offset = 0
    start = cue.start
    for match in _SENTENCE_END.finditer(text):
        part = _compact(text[offset:match.end()])
        if not part or (match.group() == "." and _ABBREVIATION.search(part)):
            continue
        boundary = cue.start + (end - cue.start) * match.end() / len(text)
        yield _Cue(start, boundary, part), True
        start, offset = boundary, match.end()
    tail = _compact(text[offset:])
    if tail:
        yield _Cue(start, end, tail), False


def normalize_subtitle_segments(segments: list[dict]) -> list[dict]:
    """合并相邻的句子碎片，按标点或明确的说话人边界分段。"""
    cues = _remove_rollover(_read_cues(segments))
    grouped = []
    pending = None
    for index, cue in enumerate(cues):
        # 平台可能把前一条字幕保留到后一条开始之后，取后一条的起点作为换行边界。
        end = cue.end
        if index + 1 < len(cues):
            next_start = cues[index + 1].start
            if next_start > cue.start:
                end = min(end, next_start)
        for part, finished in _sentence_parts(cue, end):
            if pending is not None:
                combined = _compact(f"{pending.text} {part.text}")
                if (
                    part.start - pending.end <= _MAX_JOIN_GAP
                    and part.end - pending.start <= _MAX_JOIN_SECONDS
                    and len(combined) <= _MAX_JOIN_LENGTH
                    and not re.match(_SPEAKER, part.text)
                ):
                    part = _Cue(pending.start, max(pending.end, part.end), combined)
                else:
                    grouped.append(pending)
            pending = None if finished else part
            if finished:
                grouped.append(part)
    if pending is not None:
        grouped.append(pending)

    return [
        {"start_time": cue.start, "end_time": cue.end, "text": cue.text}
        for cue in sorted(grouped, key=lambda cue: cue.start)
    ]
