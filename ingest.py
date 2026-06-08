"""
Document ingestion + chunking for The Unofficial Guide (RateMyProfessors RAG).

Pipeline stages implemented here (see planning.md → Architecture):
    Document Ingestion  ->  Chunking
    (load .txt files)       (recursive, 350 tokens, 20-token overlap)

Output: chunks.json — a list of {"id", "text", "metadata"} objects ready for the
next stage (embedding with all-MiniLM-L6-v2 + ChromaDB).

Run:
    python ingest.py                 # uses ./documents, writes ./chunks.json
    python ingest.py --docs-dir documents --out chunks.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# --- Chunking parameters (from planning.md → Chunking Strategy) -------------
CHUNK_SIZE_TOKENS = 230      # target chunk size (kept < all-MiniLM-L6-v2's 256 limit)
CHUNK_OVERLAP_TOKENS = 20    # overlap between consecutive chunks

# Recursive separators, tried in order: paragraphs -> lines -> sentences ->
# words -> characters. This is the "recursive chunking" strategy from the plan:
# it keeps whole reviews together when they fit, and only splits mid-review as a
# last resort.
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

# The embedding model all-MiniLM-L6-v2 (planning.md → Retrieval Approach). We
# count tokens with ITS tokenizer so chunk sizes match what the model sees.
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Prepend the professor's name to each chunk's embedded text. This directly
# targets Anticipated Challenge #1 (wrong-professor retrieval): the name becomes
# part of the embedding, helping the retriever tell near-identical reviews apart.
PREPEND_PROFESSOR = True

# Lines like "[Paste each review below ...]" left in unfilled template files.
_TEMPLATE_HINT = re.compile(r"^\s*\[.*\]\s*$", re.DOTALL)
# A review's optional first line, e.g. "Quality 5.0 | Difficulty 3.0 | CSE2050".
_RATING_LINE = re.compile(
    r"^\s*Quality\s*([\d.]+)\s*\|\s*Difficulty\s*([\d.]+)\s*(?:\|\s*(\S+))?\s*$",
    re.IGNORECASE,
)


# --- Token counting ---------------------------------------------------------
def _build_token_len():
    """Return a function str -> token count.

    Prefer the real MiniLM tokenizer so chunk sizes are accurate. Fall back to a
    word-count approximation if transformers isn't installed yet, so the script
    still runs before `pip install -r requirements.txt`.
    """
    try:
        from transformers import AutoTokenizer  # type: ignore

        tok = AutoTokenizer.from_pretrained(EMBED_MODEL_NAME)

        def token_len(text: str) -> int:
            return len(tok.encode(text, add_special_tokens=False))

        token_len.backend = "minilm-tokenizer"  # type: ignore[attr-defined]
        return token_len
    except Exception:
        def token_len(text: str) -> int:
            # Rough heuristic: ~1.3 tokens per whitespace word.
            words = len(text.split())
            return int(round(words * 1.3))

        token_len.backend = "word-approx"  # type: ignore[attr-defined]
        return token_len


# --- Parsing ----------------------------------------------------------------
@dataclass
class ProfessorDoc:
    professor: str
    rmp_id: str
    url: str
    source_file: str
    overall: str = ""           # cleaned text of the OVERALL block (may be empty)
    reviews: list[str] = field(default_factory=list)  # cleaned review prose


def _clean_block(text: str) -> str:
    """Join hard-wrapped lines into clean prose and collapse whitespace."""
    text = text.replace("\r\n", "\n")
    # Join lines within the block (RMP text is hard-wrapped) into one paragraph.
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _parse_header(lines: list[str]) -> dict[str, str]:
    header = {"PROFESSOR": "", "RMP_ID": "", "URL": ""}
    for line in lines:
        m = re.match(r"^(PROFESSOR|RMP_ID|URL):\s*(.*)$", line.strip())
        if m:
            header[m.group(1)] = m.group(2).strip()
    return header


def parse_file(path: Path) -> ProfessorDoc | None:
    """Parse one RMP .txt file into a ProfessorDoc. Returns None if it has no
    usable review content (e.g. an unfilled template)."""
    raw = path.read_text(encoding="utf-8")

    # Split into header / OVERALL / REVIEWS sections on the === markers.
    header_part = raw
    overall_part = ""
    reviews_part = ""

    if "=== OVERALL ===" in raw:
        header_part, rest = raw.split("=== OVERALL ===", 1)
        if "=== REVIEWS ===" in rest:
            overall_part, reviews_part = rest.split("=== REVIEWS ===", 1)
        else:
            overall_part = rest
    elif "=== REVIEWS ===" in raw:
        header_part, reviews_part = raw.split("=== REVIEWS ===", 1)

    header = _parse_header(header_part.splitlines())

    # OVERALL: keep only the non-empty stat lines (drop blanks / trailing labels).
    overall_lines = [
        ln.strip() for ln in overall_part.splitlines()
        if ln.strip() and not _TEMPLATE_HINT.match(ln)
    ]
    # A stat line is only meaningful if it has a value after the colon.
    overall_stats = [
        ln for ln in overall_lines
        if ":" in ln and ln.split(":", 1)[1].strip()
    ]
    overall_text = " | ".join(overall_stats)

    # REVIEWS: split into blocks on blank lines.
    reviews: list[str] = []
    blocks = re.split(r"\n\s*\n", reviews_part)
    for block in blocks:
        block = block.strip()
        if not block or _TEMPLATE_HINT.match(block):
            continue  # skip leftover template instructions

        block_lines = block.splitlines()
        # Drop the optional "Quality X | Difficulty Y | Course" rating line; the
        # numbers live in OVERALL, and dropping them keeps embedded text clean.
        if block_lines and _RATING_LINE.match(block_lines[0]):
            block_lines = block_lines[1:]

        prose = _clean_block("\n".join(block_lines))
        if prose:
            reviews.append(prose)

    if not reviews:
        return None  # unfilled template — nothing to ingest

    return ProfessorDoc(
        professor=header["PROFESSOR"] or path.stem,
        rmp_id=header["RMP_ID"],
        url=header["URL"],
        source_file=path.name,
        overall=overall_text,
        reviews=reviews,
    )


# --- Recursive chunking -----------------------------------------------------
def _merge_splits(splits, separator, token_len, chunk_size, chunk_overlap):
    """Greedily merge small pieces into chunks up to chunk_size tokens, carrying
    chunk_overlap tokens of context from the end of one chunk into the next.
    (Standard recursive-splitter merge logic, measured in tokens.)"""
    sep_len = token_len(separator) if separator else 0
    chunks: list[str] = []
    current: list[str] = []
    total = 0

    for piece in splits:
        piece_len = token_len(piece)
        added = piece_len + (sep_len if current else 0)
        if total + added > chunk_size and current:
            doc = separator.join(current).strip()
            if doc:
                chunks.append(doc)
            # Trim from the front to leave ~chunk_overlap tokens of context.
            while current and (
                total > chunk_overlap
                or (total + added > chunk_size and total > 0)
            ):
                total -= token_len(current[0]) + (sep_len if len(current) > 1 else 0)
                current.pop(0)
        current.append(piece)
        total += piece_len + (sep_len if len(current) > 1 else 0)

    doc = separator.join(current).strip()
    if doc:
        chunks.append(doc)
    return chunks


def split_text(text, token_len, separators=SEPARATORS,
               chunk_size=CHUNK_SIZE_TOKENS, chunk_overlap=CHUNK_OVERLAP_TOKENS):
    """Recursively split text on the separator hierarchy, then merge back up to
    the target chunk size with overlap."""
    final: list[str] = []

    # Pick the first separator that appears in the text.
    separator = separators[-1]
    remaining = separators[separators.index(separator) + 1:]
    for i, sep in enumerate(separators):
        if sep == "":
            separator = sep
            remaining = []
            break
        if sep in text:
            separator = sep
            remaining = separators[i + 1:]
            break

    pieces = list(text) if separator == "" else text.split(separator)

    good: list[str] = []
    for piece in pieces:
        if token_len(piece) < chunk_size:
            good.append(piece)
        else:
            if good:
                final.extend(_merge_splits(good, separator, token_len,
                                           chunk_size, chunk_overlap))
                good = []
            if not remaining:
                final.append(piece)  # can't split further
            else:
                final.extend(split_text(piece, token_len, remaining,
                                         chunk_size, chunk_overlap))
    if good:
        final.extend(_merge_splits(good, separator, token_len,
                                   chunk_size, chunk_overlap))
    return final


# --- Chunk assembly ---------------------------------------------------------
def chunk_document(doc: ProfessorDoc, token_len) -> list[dict]:
    """Produce chunks for one professor. The OVERALL stats become their own
    chunk so figures like 'would take again %' stay retrievable; reviews are
    packed together by the recursive splitter."""
    out: list[dict] = []

    def make(text: str, section: str, idx: int) -> dict:
        embedded = text
        if PREPEND_PROFESSOR and doc.professor:
            embedded = f"Professor: {doc.professor}\n{text}"
        return {
            "id": f"{doc.rmp_id or doc.source_file}-{section}-{idx}",
            "text": embedded,
            "metadata": {
                "professor": doc.professor,
                "rmp_id": doc.rmp_id,
                "url": doc.url,
                "source_file": doc.source_file,
                "section": section,
                "tokens": token_len(embedded),
            },
        }

    if doc.overall:
        for i, piece in enumerate(split_text(doc.overall, token_len)):
            out.append(make(piece, "overall", i))

    reviews_text = "\n\n".join(doc.reviews)
    for i, piece in enumerate(split_text(reviews_text, token_len)):
        out.append(make(piece, "reviews", i))

    return out


# --- Main -------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest + chunk RMP documents.")
    ap.add_argument("--docs-dir", default="documents", help="folder of .txt files")
    ap.add_argument("--out", default="chunks.json", help="output JSON path")
    args = ap.parse_args()

    docs_dir = Path(args.docs_dir)
    token_len = _build_token_len()
    print(f"Token counting backend: {token_len.backend}")
    if CHUNK_SIZE_TOKENS > 256:
        print(f"NOTE: chunk size {CHUNK_SIZE_TOKENS} > all-MiniLM-L6-v2's 256-token "
              "limit; longer chunks get truncated at embedding time. Consider <=256.")

    all_chunks: list[dict] = []
    skipped: list[str] = []

    for path in sorted(docs_dir.glob("*.txt")):
        doc = parse_file(path)
        if doc is None:
            skipped.append(path.name)
            continue
        chunks = chunk_document(doc, token_len)
        all_chunks.extend(chunks)
        print(f"  {path.name}: {len(doc.reviews)} reviews -> {len(chunks)} chunks")

    Path(args.out).write_text(json.dumps(all_chunks, indent=2, ensure_ascii=False),
                              encoding="utf-8")

    print(f"\nProcessed {len({c['metadata']['source_file'] for c in all_chunks})} "
          f"professor file(s) -> {len(all_chunks)} chunks total.")
    if all_chunks:
        sizes = [c["metadata"]["tokens"] for c in all_chunks]
        print(f"Chunk tokens: min={min(sizes)}, max={max(sizes)}, "
              f"avg={sum(sizes) / len(sizes):.0f}")
    if skipped:
        print(f"Skipped {len(skipped)} unfilled template(s): {', '.join(skipped)}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
