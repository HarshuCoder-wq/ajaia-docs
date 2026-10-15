"""Content handling: HTML sanitization and file import.

Everything that becomes document content passes through `sanitize_html`, whether it
came from the editor or from an uploaded file. Sanitizing on the server (not just
trusting the editor) is what makes sharing safe: a document one user writes is
rendered in another user's browser.
"""

import html
import io
import os

import mammoth
import markdown as md
import nh3

ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "h1", "h2", "h3", "ul", "ol", "li", "blockquote", "pre", "code", "a",
}
# Note: <span> is deliberately not allowed. Quill injects empty <span class="ql-ui">
# list markers into its DOM; dropping spans keeps stored HTML clean.
ALLOWED_ATTRIBUTES = {
    "a": {"href", "target"},
    # Quill 2 marks list items as bullet/ordered with data-list.
    "li": {"data-list"},
    "pre": {"spellcheck"},
}
_ALIGN = {"ql-align-center", "ql-align-right", "ql-align-justify"}
_INDENT = {f"ql-indent-{n}" for n in range(1, 9)}
ALLOWED_CLASSES = {tag: _ALIGN | _INDENT for tag in ("p", "h1", "h2", "h3", "li", "blockquote")}
ALLOWED_CLASSES["pre"] = {"ql-syntax"}

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".docx"}
SUPPORTED_LABEL = ".txt, .md, .docx (max 2 MB)"
MAX_TITLE = 200


class FileImportError(ValueError):
    """Raised when an uploaded file can't be turned into a document."""


def sanitize_html(raw: str) -> str:
    return nh3.clean(
        raw or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        allowed_classes=ALLOWED_CLASSES,
        url_schemes={"http", "https", "mailto"},
        clean_content_tags={"script", "style"},
    )


def clean_title(raw: str | None) -> str:
    title = " ".join((raw or "").split())
    if not title:
        raise ValueError("Title can't be empty.")
    if len(title) > MAX_TITLE:
        raise ValueError(f"Title must be {MAX_TITLE} characters or fewer.")
    return title


def _decode_text(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    raise FileImportError("Couldn't read the file as text. Please save it as UTF-8.")


def _txt_to_html(text: str) -> str:
    paras = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        lines = [html.escape(line) for line in block.split("\n")]
        if any(line.strip() for line in lines):
            paras.append("<p>" + "<br>".join(lines) + "</p>")
    return "".join(paras)


def import_file(filename: str, data: bytes) -> tuple[str, str]:
    """Convert an uploaded file into (title, sanitized_html)."""
    stem, ext = os.path.splitext(filename or "")
    ext = ext.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise FileImportError(f"Unsupported file type '{ext or 'none'}'. Supported: {SUPPORTED_LABEL}.")
    if not data:
        raise FileImportError("The uploaded file is empty.")

    if ext == ".txt":
        body = _txt_to_html(_decode_text(data))
    elif ext in (".md", ".markdown"):
        # Escape raw HTML embedded in markdown is handled by the sanitizer below.
        body = md.markdown(_decode_text(data), extensions=["sane_lists"])
    else:  # .docx
        try:
            result = mammoth.convert_to_html(io.BytesIO(data))
        except Exception as exc:  # mammoth raises a variety of zip/xml errors
            raise FileImportError("Couldn't read that .docx file. Is it a valid Word document?") from exc
        body = result.value

    # Our editor only supports h1-h3; fold deeper headings into h3.
    for level in (4, 5, 6):
        body = body.replace(f"<h{level}", "<h3").replace(f"</h{level}>", "</h3>")

    title = " ".join(stem.replace("_", " ").split())[:MAX_TITLE] or "Imported document"
    return title, sanitize_html(body)
