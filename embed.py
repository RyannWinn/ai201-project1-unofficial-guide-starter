"""
Embedding + Vector Store + Retrieval for The Unofficial Guide (RMP RAG).

Pipeline stages implemented here (see planning.md -> Architecture diagram):
    Embedding + Vector Store        ->   Retrieval
    (all-MiniLM-L6-v2 -> ChromaDB)       (top-k=5 similarity search)

Reads chunks.json (from ingest.py) and:
  1. embeds each chunk's text with all-MiniLM-L6-v2 (sentence-transformers),
  2. stores the vectors + source metadata in a persistent ChromaDB collection,
  3. exposes retrieve(query, k=5) for the next stage (generation).

Run:
    python embed.py                       # build the index from chunks.json
    python embed.py --query "Are Lina Kloub's exams hard?"   # query existing index
    python embed.py --query "..." --k 5 --professor "Lina Kloub"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# --- Config (from planning.md -> Retrieval Approach) ------------------------
CHUNKS_PATH = "chunks.json"
DB_DIR = "chroma_db"             # ChromaDB writes its files here (persists on disk)
COLLECTION_NAME = "rmp_reviews"
EMBED_MODEL = "all-MiniLM-L6-v2"  # the embedding model from the plan
DEFAULT_TOP_K = 5                 # plan says 3-5; ~5 is the sweet spot


def _embedding_function():
    """ChromaDB calls this object to turn text into vectors.

    SentenceTransformerEmbeddingFunction is Chroma's built-in wrapper around the
    `sentence-transformers` library -- the exact tool named in planning.md. By
    attaching it to the collection, Chroma uses all-MiniLM-L6-v2 to embed BOTH
    the chunks we add AND every query we search with, so the two can never drift
    out of sync (a common bug when you embed documents and queries separately).
    """
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )


def _sanitize(meta: dict) -> dict:
    """ChromaDB metadata values must be str/int/float/bool -- never None.
    Our chunk metadata uses empty strings for missing fields, but guard anyway."""
    return {k: ("" if v is None else v) for k, v in meta.items()}


# --- Build the index --------------------------------------------------------
def build_index(chunks_path: str = CHUNKS_PATH, db_dir: str = DB_DIR,
                name: str = COLLECTION_NAME) -> chromadb.Collection:
    """Load chunks.json and (re)build the ChromaDB collection from scratch."""
    chunks = json.loads(Path(chunks_path).read_text(encoding="utf-8"))

    # PersistentClient saves the database to `db_dir` on disk, so the index
    # survives between runs -- you embed once, then query as many times as you
    # like without re-embedding. (chromadb.Client() alone would be in-memory.)
    client = chromadb.PersistentClient(path=db_dir)

    # Drop any previous collection so re-running doesn't pile up duplicate /
    # stale vectors. A "collection" is Chroma's equivalent of a table: it holds
    # the embeddings, their source documents, and metadata together.
    try:
        client.delete_collection(name)
    except Exception:
        pass  # nothing to delete on first run

    collection = client.create_collection(
        name=name,
        embedding_function=_embedding_function(),
        # Tell Chroma's HNSW index to rank by COSINE similarity (good for
        # normalized sentence embeddings). Without this it defaults to L2
        # (Euclidean) distance. HNSW is the approximate-nearest-neighbor index
        # Chroma uses under the hood to make top-k search fast.
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c["id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [_sanitize(c["metadata"]) for c in chunks]

    # collection.add() does the embedding for us: it passes each string in
    # `documents` through the embedding_function above, then stores the vector
    # alongside its id, original text, and metadata. No manual model call needed.
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print(f"Built '{name}': {collection.count()} vectors "
          f"from {len(chunks)} chunks -> {db_dir}/")
    return collection


def get_collection(db_dir: str = DB_DIR,
                   name: str = COLLECTION_NAME) -> chromadb.Collection:
    """Open the existing on-disk collection for querying (no rebuild)."""
    client = chromadb.PersistentClient(path=db_dir)
    # Must pass the SAME embedding_function so queries get embedded with the
    # same model the documents were embedded with.
    return client.get_collection(name=name, embedding_function=_embedding_function())


# --- Retrieval --------------------------------------------------------------
def retrieve(query: str, k: int = DEFAULT_TOP_K, professor: str | None = None,
             db_dir: str = DB_DIR, name: str = COLLECTION_NAME) -> list[dict]:
    """Return the top-k most similar chunks to `query`.

    If `professor` is given, restrict the search to that professor's chunks via
    a metadata filter -- a direct lever against planning.md Anticipated
    Challenge #1 (wrong-professor retrieval).
    """
    collection = get_collection(db_dir, name)

    # `where` is Chroma's metadata filter: it narrows the search to vectors whose
    # stored metadata matches before similarity ranking. None = search everything.
    where = {"professor": professor} if professor else None

    # collection.query() embeds `query` with the SAME model, then returns the
    # n_results nearest vectors. query_texts is a LIST because Chroma supports
    # batching many queries at once -- which is why every field in the result is
    # nested one level (res["documents"][0] is the list for our single query).
    res = collection.query(
        query_texts=[query],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits: list[dict] = []
    for i in range(len(res["ids"][0])):
        hits.append({
            "id": res["ids"][0][i],
            "text": res["documents"][0][i],
            "metadata": res["metadatas"][0][i],
            # cosine distance: 0 = identical, larger = less similar.
            # similarity = 1 - distance, shown below for readability.
            "distance": res["distances"][0][i],
        })
    return hits


def _print_hits(query: str, hits: list[dict]) -> None:
    print(f'\nQuery: "{query}"  ->  {len(hits)} hits\n' + "=" * 72)
    for rank, h in enumerate(hits, 1):
        m = h["metadata"]
        sim = 1 - h["distance"]
        print(f"#{rank}  sim={sim:.3f}  {m['professor']}  "
              f"[{m['section']}]  ({m['source_file']})")
        print(h["text"])
        print("-" * 72)


# --- Main -------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="Embed chunks + retrieve.")
    ap.add_argument("--chunks", default=CHUNKS_PATH, help="chunks JSON path")
    ap.add_argument("--db", default=DB_DIR, help="ChromaDB directory")
    ap.add_argument("--query", help="if given, query the existing index instead of building")
    ap.add_argument("--k", type=int, default=DEFAULT_TOP_K, help="top-k results")
    ap.add_argument("--professor", help="restrict retrieval to one professor")
    args = ap.parse_args()

    if args.query:
        hits = retrieve(args.query, k=args.k, professor=args.professor, db_dir=args.db)
        _print_hits(args.query, hits)
    else:
        build_index(args.chunks, args.db)
        # Smoke test with one of the planning.md evaluation questions.
        demo = "Are Lina Kloub's exams difficult?"
        _print_hits(demo, retrieve(demo, k=args.k, db_dir=args.db))


if __name__ == "__main__":
    main()
