"""
Interface stage for The Unofficial Guide (RMP RAG).

Pipeline stage implemented here (see planning.md -> Architecture diagram):
    Generation  ->  User-facing interface (Gradio)

A thin Gradio front-end over generate.answer_question(). It does NOT do any
retrieval or LLM logic itself -- that all lives in generate.py / embed.py. Its
only job is to take a question, call the grounded pipeline, and render:

    * the answer (from retrieved context only), and
    * the source list (built programmatically from the retrieved chunks, so the
      attribution shown here is guaranteed to be the documents actually used).

Run:
    python app.py
then open the printed local URL (http://127.0.0.1:7860) in a browser.
"""

from __future__ import annotations

import gradio as gr

from embed import DEFAULT_TOP_K
from generate import answer_question, attribution_line, Source

# Professors in the corpus, for the optional filter dropdown (planning.md
# Anticipated Challenge #1: lets the user pin retrieval to one professor).
PROFESSORS = [
    "Alexander Russell", "David Strimple", "Derek Aguiar", "Justin Furuness",
    "Laurent Michel", "Lina Kloub", "Olga Glebova",
    "Swamy Narayan Jignaas Pattipati", "Timothy Curry", "Zhije Jerry Shi",
]

EXAMPLES = [
    "Are Lina Kloub's exams difficult?",
    "Do students recommend taking Swamy's class?",
    "Is attendance mandatory for Olga's class?",
    "Is David Strimple's grading rubric harsh?",
    "What teaching style do reviews describe for David Strimple?",
]


def _sources_markdown(sources: list[Source]) -> str:
    """Render the (programmatically built) source list as Markdown."""
    if not sources:
        return "_No sources — the answer was not grounded in any document._"
    lines = ["### Sources", ""]
    for s in sources:
        header = (
            f"**[{s.rank}] {s.professor}** — {s.section} "
            f"· similarity {s.similarity:.2f} · "
            f"[{s.source_file}]({s.url})"
        )
        # Quote the exact chunk text so the user can verify the answer themselves.
        quoted = "> " + s.text.replace("\n", "  \n> ")
        lines += [header, "", quoted, ""]
    return "\n".join(lines)


def ask(question: str, professor: str, k: int):
    """Gradio callback: question -> (answer markdown, sources markdown)."""
    question = (question or "").strip()
    if not question:
        return "Please enter a question.", ""

    prof = None if professor in ("Any professor", "", None) else professor
    ans = answer_question(question, k=int(k), professor=prof)

    if ans.refused:
        # Make refusals visually distinct so they aren't mistaken for an answer.
        answer_md = f"⚠️ {ans.text}"
    else:
        # Append the programmatically built source-document attribution directly
        # under the answer, so the answer itself names where it came from.
        answer_md = f"{ans.text}\n\n_{attribution_line(ans.sources)}_"
    return answer_md, _sources_markdown(ans.sources)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="The Unofficial Guide") as demo:
        gr.Markdown(
            "# 🎓 The Unofficial Guide\n"
            "Ask about a professor and get an answer grounded **only** in real "
            "RateMyProfessors student reviews. Every answer lists the exact "
            "review chunks it was built from."
        )

        with gr.Row():
            question = gr.Textbox(
                label="Your question",
                placeholder="e.g. Are Lina Kloub's exams difficult?",
                scale=4,
                lines=2,
            )
        with gr.Row():
            professor = gr.Dropdown(
                choices=["Any professor"] + PROFESSORS,
                value="Any professor",
                label="Restrict to professor (optional)",
                scale=3,
            )
            k = gr.Slider(
                minimum=1, maximum=10, value=DEFAULT_TOP_K, step=1,
                label="Chunks to retrieve (top-k)", scale=2,
            )
            submit = gr.Button("Ask", variant="primary", scale=1)

        answer = gr.Markdown(label="Answer")
        sources = gr.Markdown(label="Sources")

        gr.Examples(examples=EXAMPLES, inputs=question)

        # Wire the interface to the grounded pipeline. Both the button and
        # pressing Enter in the textbox trigger the same callback.
        submit.click(ask, inputs=[question, professor, k], outputs=[answer, sources])
        question.submit(ask, inputs=[question, professor, k], outputs=[answer, sources])

    return demo


if __name__ == "__main__":
    build_ui().launch()
