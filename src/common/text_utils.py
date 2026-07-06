from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher
import re


CHINESE_CHAR_PATTERN = re.compile(r"[\u4e00-\u9fff]")
HEADING_PATTERN = re.compile(
    r"^(一|二|三|四|五|六|七|八|九|十|[0-9]+)[、.．]|^(第[一二三四五六七八九十0-9]+(部分|点|步|章|节)?[：:、.]?)|^(首先|其次|再次|最后|另外|还有)[：:，,]?|^#+\s*"
)


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def contains_chinese(text: str) -> bool:
    return bool(CHINESE_CHAR_PATTERN.search(text or ""))


def split_paragraphs(text: str) -> list[str]:
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []
    return [paragraph.strip() for paragraph in cleaned.split("\n") if paragraph.strip()]


def detect_headings(paragraphs: list[str]) -> list[str]:
    return [paragraph for paragraph in paragraphs if HEADING_PATTERN.search(paragraph)]


def estimate_word_count(text: str) -> int:
    chinese_chars = len(CHINESE_CHAR_PATTERN.findall(text))
    latin_words = len(re.findall(r"[A-Za-z0-9_]+", text))
    return chinese_chars + latin_words


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def paragraph_similarities(source: list[str], target: list[str]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for src in source:
        best_target = ""
        best_score = 0.0
        for tgt in target:
            score = similarity(src, tgt)
            if score > best_score:
                best_score = score
                best_target = tgt
        results.append(
            {
                "paragraph": src,
                "best_match": best_target,
                "similarity": round(best_score, 4),
            }
        )
    return results


def max_continuous_duplicate_chars(a: str, b: str) -> int:
    if not a or not b:
        return 0
    max_len = 0
    for i in range(len(a)):
        for j in range(len(b)):
            length = 0
            while i + length < len(a) and j + length < len(b) and a[i + length] == b[j + length]:
                length += 1
            if length > max_len:
                max_len = length
    return max_len


def contains_any(text: str, phrases: list[str]) -> list[str]:
    return [phrase for phrase in phrases if phrase in text]


def replace_phrases(text: str, replacements: dict[str, str]) -> str:
    updated = text
    for source, target in replacements.items():
        updated = updated.replace(source, target)
    return updated


def average_paragraph_length(paragraphs: list[str]) -> float:
    if not paragraphs:
        return 0.0
    return sum(len(p) for p in paragraphs) / len(paragraphs)


def top_terms(text: str, limit: int = 12) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", text.lower())
    counts = Counter(tokens)
    return [term for term, _ in counts.most_common(limit)]


def extract_informative_paragraphs(
    text: str,
    *,
    limit: int = 4,
    max_chars: int = 1800,
    topic_terms: list[str] | None = None,
) -> list[str]:
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return []

    topic_terms = [term.lower() for term in (topic_terms or []) if term]
    scored: list[tuple[int, int, str]] = []
    for index, paragraph in enumerate(paragraphs):
        if len(paragraph) < 40:
            continue
        score = _paragraph_score(paragraph, topic_terms)
        scored.append((score, index, paragraph))

    if not scored:
        return paragraphs[:limit]

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected: list[tuple[int, str]] = []
    total_chars = 0
    for _, index, paragraph in scored:
        if len(selected) >= limit:
            break
        if total_chars >= max_chars:
            break
        remaining = max_chars - total_chars
        snippet = paragraph[:remaining].strip()
        if not snippet:
            continue
        if len(paragraph) > remaining and remaining > 30:
            snippet = snippet.rstrip("，,；;：:。.") + "..."
        selected.append((index, snippet))
        total_chars += len(snippet)

    selected.sort(key=lambda item: item[0])
    return [paragraph for _, paragraph in selected]


def _paragraph_score(paragraph: str, topic_terms: list[str]) -> int:
    lowered = paragraph.lower()
    score = min(len(paragraph), 420)

    for term in topic_terms:
        if term and term in lowered:
            score += 80

    signal_markers = [
        "责任",
        "保险",
        "规定",
        "要求",
        "申请",
        "报告",
        "赔偿",
        "受伤",
        "事故",
        "维护",
        "安全",
        "law",
        "code",
        "rule",
        "must",
        "required",
        "liability",
        "injury",
        "claim",
        "insurance",
        "sidewalk",
        "construction",
    ]
    for marker in signal_markers:
        if marker in lowered:
            score += 20

    if re.search(r"\d", paragraph):
        score += 25
    if "http" in lowered:
        score -= 120
    if len(paragraph) > 900:
        score -= 60
    return score
