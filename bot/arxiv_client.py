import re
import xml.etree.ElementTree as ET

import fitz  # PyMuPDF
import httpx

ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")
ARXIV_API = "http://export.arxiv.org/api/query?id_list={arxiv_id}"
ARXIV_PDF = "https://arxiv.org/pdf/{arxiv_id}"

NS = {"atom": "http://www.w3.org/2005/Atom"}


def extract_arxiv_id(text: str) -> str | None:
    m = ARXIV_ID_RE.search(text)
    return m.group(0) if m else None


async def fetch_paper_text(arxiv_id: str, max_pages: int = 20) -> dict:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        meta = await _fetch_metadata(client, arxiv_id)
        full_text = await _fetch_pdf_text(client, arxiv_id, max_pages)

    return {**meta, "full_text": full_text}


async def _fetch_metadata(client: httpx.AsyncClient, arxiv_id: str) -> dict:
    url = ARXIV_API.format(arxiv_id=arxiv_id)
    resp = await client.get(url)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entry = root.find("atom:entry", NS)
    if entry is None:
        raise ValueError(f"Статья не найдена: {arxiv_id}")

    title = _text(entry, "atom:title").replace("\n", " ").strip()
    abstract = _text(entry, "atom:summary").replace("\n", " ").strip()
    authors = [
        _text(a, "atom:name")
        for a in entry.findall("atom:author", NS)
    ]
    clean_id = arxiv_id.split("v")[0]

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "url": f"https://arxiv.org/abs/{clean_id}",
        "pdf_url": f"https://arxiv.org/pdf/{clean_id}",
    }


async def _fetch_pdf_text(client: httpx.AsyncClient, arxiv_id: str, max_pages: int) -> str:
    url = ARXIV_PDF.format(arxiv_id=arxiv_id)
    resp = await client.get(url)
    resp.raise_for_status()

    pdf_bytes = resp.content
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = min(len(doc), max_pages)

    parts = []
    for i in range(pages):
        parts.append(doc[i].get_text())

    return "\n".join(parts)


def _text(element, tag: str) -> str:
    node = element.find(tag, NS)
    return (node.text or "").strip() if node is not None else ""
