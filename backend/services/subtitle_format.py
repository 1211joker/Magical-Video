"""整理各平台提取的字幕片段，同时保留视频时间轴。"""
import math
import re
from dataclasses import dataclass, replace
from html import unescape


_WORD_TIME = re.compile(r"<\d{2,}:\d{2}(?::\d{2})?[.,]\d{3}>")
_CAPTION_TAG = re.compile(
    r"</?(?:c(?:\.[^\s.>]+)*|b|i|u|ruby|rt|v|lang|span|font|a|em|strong)(?:\s+[^>]+)?>"
    rf"|{_WORD_TIME.pattern}",
    re.IGNORECASE,
)
_LINE_TAG = re.compile(r"</?(?:br|p|div)(?:\s+[^>]*)?/?>", re.IGNORECASE)
_HAN_KANA = r"\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff"
_HAN_KANA_BREAK = re.compile(rf"(?<=[{_HAN_KANA}])[ \t]*\n[ \t]*(?=[{_HAN_KANA}])")
_EXTRA_SPACE = re.compile(r" (?=[，。！？、；：）】」』])|(?<=[（【「『]) ")
_SPEAKER = r"(?:[-—–]|>>)[ \t]+"
_SENTENCE_END = re.compile(
    rf"""[。！？]+[”’」』）》】]*|[.!?]+["'”’)\]]*(?=\s|$)|\n(?={_SPEAKER})"""
)
_ABBREVIATION = re.compile(r"\b(?:[A-Z]|[eE]\.g|[iI]\.e|Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs)\.$")
_MAX_JOIN_GAP = 0.7
_MAX_JOIN_SECONDS = 8
_MAX_JOIN_LENGTH = 120
_ROLLOVER_TRANSITION = 0.04


@dataclass(frozen=True)
class _Cue:
    start: float
    end: float
    text: str
    has_word_times: bool = False


def _compact(text: str) -> str:
    return _EXTRA_SPACE.sub("", " ".join(_HAN_KANA_BREAK.sub("", text).split()))


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
            cues.append(_Cue(start, max(end, start + 0.001), cleaned, bool(_WORD_TIME.search(text))))
    return sorted(cues, key=lambda cue: cue.start)


def _remove_rollover(cues: list[_Cue]) -> list[_Cue]:
    """带逐词时间戳的滚动更新可能把上一条字幕的末行带进来。"""
    distinct = []
    for cue in cues:
        previous = distinct[-1] if distinct else None
        first, _, remainder = cue.text.partition("\n")
        if (
            previous and cue.has_word_times and remainder
            and cue.start <= previous.end + _ROLLOVER_TRANSITION
            and first == previous.text.rsplit("\n", 1)[-1]
        ):
            # 有些滚动字幕会先用一个极短条目单独保留旧行，再显示下一行。
            if previous.end - previous.start <= _ROLLOVER_TRANSITION and len(distinct) >= 2:
                before = distinct[-2]
                if previous.text == before.text and previous.start <= before.end + _ROLLOVER_TRANSITION:
                    distinct.pop()
                    previous = before
            if previous.start < cue.start < previous.end:
                distinct[-1] = replace(previous, end=cue.start)
            cue = replace(cue, text=remainder)
        distinct.append(cue)
    return distinct


def _sentence_parts(cue: _Cue):
    """用原片段范围估算片段内部的断句时间。"""
    text = cue.text
    offset = 0
    start = cue.start
    for match in _SENTENCE_END.finditer(text):
        part = _compact(text[offset:match.end()])
        if not part or (match.group() == "." and _ABBREVIATION.search(part)):
            continue
        boundary = cue.start + (cue.end - cue.start) * match.end() / len(text)
        yield _Cue(start, boundary, part), True
        start, offset = boundary, match.end()
    tail = _compact(text[offset:])
    if tail:
        yield _Cue(start, cue.end, tail), False


def normalize_subtitle_segments(segments: list[dict]) -> list[dict]:
    """合并相邻的句子碎片，按标点或明确的说话人边界分段。"""
    cues = _remove_rollover(_read_cues(segments))
    grouped = []
    pending = None
    for cue in cues:
        for part, finished in _sentence_parts(cue):
            if pending is not None:
                combined = _compact(f"{pending.text}\n{part.text}")
                if (
                    part.start > pending.start and part.end >= pending.end
                    and part.start - pending.end <= _MAX_JOIN_GAP
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
