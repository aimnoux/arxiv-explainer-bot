import re

# All special characters that must be escaped in MarkdownV2
_MD_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")

MAX_MESSAGE_LENGTH = 4096


def escape_md(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", str(text))


def format_analysis(paper: dict, analysis: dict) -> str:
    authors = ", ".join(paper["authors"][:3])
    if len(paper["authors"]) > 3:
        authors += f" +{len(paper['authors']) - 3}"

    keywords = " ".join(f"#{re.sub(r'[^a-zA-Zа-яА-Я0-9]', '_', kw)}" for kw in analysis.get("keywords", []))

    lines = [
        f"📄 *{escape_md(analysis['title'])}*",
        f"👤 _{escape_md(authors)}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💡 *{escape_md('TL;DR')}*",
        escape_md(analysis["tldr"]),
        "",
        f"🎯 *{escape_md('Проблема')}*",
        escape_md(analysis["problem"]),
        "",
        f"🔬 *{escape_md('Метод')}*",
        escape_md(analysis["method"]),
        "",
        f"📊 *{escape_md('Результаты')}*",
        escape_md(analysis["results"]),
        "",
        f"⚠️ *{escape_md('Ограничения')}*",
        escape_md(analysis["limitations"]),
        "",
        f"🌍 *{escape_md('Почему это важно')}*",
        escape_md(analysis["why_it_matters"]),
        "",
        f"🏷️ `{escape_md(keywords)}`",
        "",
        f"🔗 [Открыть на arxiv]({paper['url']})",
    ]

    return "\n".join(lines)


def split_message(text: str) -> list[str]:
    if len(text) <= MAX_MESSAGE_LENGTH:
        return [text]

    parts = []
    while len(text) > MAX_MESSAGE_LENGTH:
        # try to cut at a paragraph boundary
        cut = text.rfind("\n\n", 0, MAX_MESSAGE_LENGTH)
        if cut == -1:
            cut = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if cut == -1:
            cut = MAX_MESSAGE_LENGTH
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")

    if text:
        parts.append(text)

    return parts
