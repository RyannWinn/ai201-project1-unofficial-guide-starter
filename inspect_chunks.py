"""
Print N representative chunks from chunks.json and inspect them by hand.

For each chunk, ask: does this make sense on its own? Could someone answer a
question from this chunk alone, without reading what comes before or after?

Run:
    python inspect_chunks.py            # 5 chunks from chunks.json
    python inspect_chunks.py --n 8      # 8 chunks
    python inspect_chunks.py --file chunks.json --n 5
"""

import argparse
import json
from pathlib import Path


def pick_representative(chunks: list[dict], n: int) -> list[int]:
    """Pick a spread: an OVERALL chunk, the smallest and largest review chunks,
    then fill from professors not yet shown so the sample isn't all one page."""
    review_idx = [i for i, c in enumerate(chunks)
                  if c["metadata"]["section"] == "reviews"]
    chosen: list[int] = []

    overall = next((i for i, c in enumerate(chunks)
                    if c["metadata"]["section"] == "overall"), None)
    if overall is not None:
        chosen.append(overall)
    if review_idx:
        chosen.append(min(review_idx, key=lambda i: chunks[i]["metadata"]["tokens"]))
        chosen.append(max(review_idx, key=lambda i: chunks[i]["metadata"]["tokens"]))

    seen_prof = {chunks[i]["metadata"]["professor"] for i in chosen}
    for i in review_idx:
        if len(chosen) >= n:
            break
        prof = chunks[i]["metadata"]["professor"]
        if i not in chosen and prof not in seen_prof:
            chosen.append(i)
            seen_prof.add(prof)

    # If still short (few professors), top up with any unused chunks.
    for i in range(len(chunks)):
        if len(chosen) >= n:
            break
        if i not in chosen:
            chosen.append(i)

    return chosen[:n]


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect representative chunks.")
    ap.add_argument("--file", default="chunks.json", help="chunks JSON path")
    ap.add_argument("--n", type=int, default=5, help="how many chunks to print")
    args = ap.parse_args()

    chunks = json.loads(Path(args.file).read_text(encoding="utf-8"))
    print(f"Total chunks: {len(chunks)}\n")

    for n, i in enumerate(pick_representative(chunks, args.n), 1):
        c = chunks[i]
        m = c["metadata"]
        print("=" * 72)
        print(f"CHUNK {n}  id={c['id']}  prof={m['professor']}  "
              f"section={m['section']}  tokens={m['tokens']}")
        print("-" * 72)
        print(c["text"])
    print("=" * 72)


if __name__ == "__main__":
    main()
