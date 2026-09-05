"""Generic, non-destructive HTML reduction for extraction contexts."""

from bs4 import BeautifulSoup, Tag


def preprocess_html(body: bytes | str) -> str:
    """Return compact Markdown-like text while preserving headings, tables, and links."""
    soup = BeautifulSoup(body, "lxml")
    for node in soup.select("script, style, noscript, svg, canvas, template"):
        node.decompose()
    for node in soup.select("header, footer, nav"):
        node.decompose()

    lines: list[str] = []
    root = soup.body or soup
    for node in root.find_all(
        ["h1", "h2", "h3", "h4", "p", "li", "table", "a", "dt", "dd"]
    ):
        if not isinstance(node, Tag) or node.find_parent(["table", "p", "li"]):
            continue
        value = " ".join(node.get_text(" ", strip=True).split())
        if not value:
            continue
        if node.name and node.name.startswith("h"):
            lines.append(f"{'#' * int(node.name[1])} {value}")
        elif node.name == "li":
            lines.append(f"- {value}")
        elif node.name == "table":
            for row in node.find_all("tr"):
                cells = [
                    " ".join(cell.get_text(" ", strip=True).split())
                    for cell in row.find_all(["th", "td"])
                ]
                if cells:
                    lines.append(" | ".join(cells))
        elif node.name == "a":
            href = node.get("href")
            lines.append(f"[{value}]({href})" if href else value)
        else:
            links = []
            for link in node.find_all("a", href=True):
                label = " ".join(link.get_text(" ", strip=True).split())
                if label:
                    links.append(f"{label}: {link['href']}")
            lines.append(value + (f" [links: {'; '.join(links)}]" if links else ""))

    # Many modern sites render meaningful cards as otherwise unsemantic divs. Retain
    # compact leaf cards inside the main content area without duplicating text already
    # represented by headings, paragraphs, lists, tables, or links above.
    represented = "\n".join(lines)
    for node in root.select("main div, article div, [role='main'] div"):
        if node.find(["div", "section", "article", "table", "p", "li"]):
            continue
        value = " ".join(node.get_text(" ", strip=True).split())
        if 2 <= len(value) <= 500 and value not in represented:
            lines.append(value)
            represented += f"\n{value}"
    return "\n".join(dict.fromkeys(lines))
