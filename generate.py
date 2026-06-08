"""
Generation stage for The Unofficial Guide (RMP RAG).

Pipeline stage implemented here (see planning.md -> Architecture diagram):
    Retrieval  ->  Generation
                   (Groq llama-3.3-70b-versatile answers ONLY from retrieved context)

This module ties the retriever (embed.retrieve) to the LLM and enforces the two
grounding guarantees the project requires:

  1. Answers come ONLY from retrieved context. The prompt passes the retrieved
     chunks as the sole source of truth and instructs the model to refuse when
     the context is insufficient ("I don't have enough information on that.").

  2. Source attribution is PROGRAMMATICALLY GUARANTEED. The list of sources we
     show the user is built in Python from the actual chunks returned by
     retrieve() -- it is NOT parsed out of the model's text. The model can only
     write prose; it can never invent, drop, or alter a citation. Every answer
     is therefore accompanied by the real documents it was grounded in.

Run:
    python generate.py                                  # smoke-test the 5 eval questions
    python generate.py --query "Are Lina Kloub's exams hard?" --k 5
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv
from groq import Groq

from embed import retrieve, DEFAULT_TOP_K

# --- Config -----------------------------------------------------------------
load_dotenv()  # read GROQ_API_KEY from .env (never hard-code or commit the key)

MODEL = "llama-3.3-70b-versatile"   # planning.md -> Generation (Groq, free tier)
REFUSAL = "I don't have enough information on that."

# When the closest chunk is further than this cosine distance from the query,
# we treat the corpus as having nothing relevant and refuse WITHOUT calling the
# LLM. This is a code-level guard against planning.md Anticipated Challenge #1
# (off-topic / wrong-professor retrieval): an empty-but-confident answer is
# worse than an honest "I don't know". 1.0 = orthogonal; tuned loose so we only
# short-circuit on clearly irrelevant queries and let the prompt handle the rest.
MAX_DISTANCE = 0.9

SYSTEM_PROMPT = (
    "You are The Unofficial Guide, a study assistant that answers questions "
    "about university professors using only real student reviews from "
    "RateMyProfessors. You must answer strictly from the provided documents."
)

# The retrieved chunks are injected as the ONLY source of truth. The model is
# told to ground every claim in them and to refuse rather than guess.
PROMPT_TEMPLATE = """\
Answer the question using only the information in the provided documents below. \
If the documents don't contain enough information to answer, say exactly: \
"{refusal}"

Do not use any outside knowledge. Do not guess. When you state a fact, it must \
be supported by the documents. Cite the documents you used with their bracketed \
numbers, e.g. [1], [2].

Documents:
{context}

Question: {question}

Answer:"""


@dataclass
class Source:
    """One retrieved chunk, as shown to the user. Built from retrieval metadata
    in code -- this is the unit that makes attribution programmatically guaranteed."""
    rank: int
    professor: str
    section: str
    source_file: str
    url: str
    similarity: float
    text: str


@dataclass
class Answer:
    """The complete result of a query: the model's prose plus the real sources."""
    text: str
    sources: list[Source] = field(default_factory=list)
    refused: bool = False


def _build_context(hits: list[dict]) -> tuple[str, list[Source]]:
    """Turn retrieved chunks into (numbered context string, Source list).

    The bracket number the model sees ([1], [2], ...) is the SAME index as the
    Source.rank we return, so a citation in the prose maps deterministically to
    a real document. Both come from the same loop -- they cannot drift apart.
    """
    blocks: list[str] = []
    sources: list[Source] = []
    for i, h in enumerate(hits, 1):
        m = h["metadata"]
        sim = 1 - h["distance"]
        blocks.append(f"[{i}] (Professor: {m['professor']}) {h['text']}")
        sources.append(Source(
            rank=i,
            professor=m["professor"],
            section=m.get("section", ""),
            source_file=m.get("source_file", ""),
            url=m.get("url", ""),
            similarity=sim,
            text=h["text"],
        ))
    return "\n\n".join(blocks), sources


def _client() -> Groq:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your "
            "free key from https://console.groq.com"
        )
    return Groq(api_key=key)


def answer_question(query: str, k: int = DEFAULT_TOP_K,
                    professor: str | None = None) -> Answer:
    """Retrieve -> ground -> generate. Returns an Answer with guaranteed sources.

    Source attribution is guaranteed because `sources` is derived entirely from
    what retrieve() returned; the LLM's output never touches it.
    """
    hits = retrieve(query, k=k, professor=professor)

    # No chunks at all, or nothing even loosely relevant -> refuse in code,
    # before spending an LLM call. A refusal has no grounded answer, so there is
    # nothing to attribute: we return no sources (same as the LLM-refusal path).
    if not hits or (1 - hits[0]["distance"]) < (1 - MAX_DISTANCE):
        return Answer(text=REFUSAL, sources=[], refused=True)

    context, sources = _build_context(hits)
    prompt = PROMPT_TEMPLATE.format(refusal=REFUSAL, context=context, question=query)

    resp = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,   # near-deterministic: we want faithful, not creative
    )
    text = resp.choices[0].message.content.strip()

    refused = text.strip().rstrip(".").lower() == REFUSAL.rstrip(".").lower()
    # On an in-code refusal we drop the sources -- they weren't actually used.
    return Answer(text=text, sources=[] if refused else sources, refused=refused)


def attribution_line(sources: list[Source]) -> str:
    """A one-line, programmatically built statement of which DOCUMENTS the answer
    came from. This is appended to the answer text after generation so the source
    names travel with the answer itself (not only in a separate panel). Because it
    is built from the retrieved Source objects -- never from the model's text -- it
    is guaranteed to name the real documents used.

    Returns e.g.:
        Sources used: David Strimple (david_strimple_2872422.txt), ...
    """
    if not sources:
        return ""
    seen: list[str] = []
    for s in sources:
        label = f"{s.professor} ({s.source_file})"
        if label not in seen:           # de-dupe: several chunks share one document
            seen.append(label)
    return "Sources used: " + "; ".join(seen)


def attributed_text(ans: "Answer") -> str:
    """The answer text with the programmatic source attribution appended.
    Refusals carry no attribution (nothing was grounded)."""
    if ans.refused or not ans.sources:
        return ans.text
    return f"{ans.text}\n\n{attribution_line(ans.sources)}"


def format_sources(sources: list[Source]) -> str:
    """Render the full source list as plain text (used by the CLI and as a fallback)."""
    if not sources:
        return ""
    lines = ["Sources:"]
    for s in sources:
        lines.append(
            f"  [{s.rank}] {s.professor} — {s.section} "
            f"(sim={s.similarity:.2f})  {s.url}"
        )
    return "\n".join(lines)


# --- Main / smoke test ------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Generate grounded answers (Groq).")
    ap.add_argument("--query", help="single question; omit to run the eval set")
    ap.add_argument("--k", type=int, default=DEFAULT_TOP_K, help="top-k chunks")
    ap.add_argument("--professor", help="restrict retrieval to one professor")
    args = ap.parse_args()

    # The 5 evaluation questions from planning.md -> Evaluation Plan.
    eval_questions = [
        "Are Lina Kloub's exams difficult?",
        "Do students recommend taking Swamy's class?",
        "Is attendance mandatory for Olga's class?",
        "Is David Strimple's grading rubric harsh?",
        "What teaching style do reviews describe for David Strimple?",
    ]
    queries = [args.query] if args.query else eval_questions

    for q in queries:
        ans = answer_question(q, k=args.k, professor=args.professor)
        print("=" * 72)
        print(f"Q: {q}\n")
        print(attributed_text(ans) + "\n")   # answer + inline source attribution
        print(format_sources(ans.sources))   # full per-chunk source list
        print()


if __name__ == "__main__":
    main()
