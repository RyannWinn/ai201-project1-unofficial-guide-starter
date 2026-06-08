# The Unofficial Guide — Project 1

## Domain

The domain I chose is Rate My Profesors. This knowledge is valuable because these 
are real reviews that students who have taken the class submitted.

---

## Document Sources

| # | Source | Type | URL or file path |
|---|--------|------|-----------------|
| 1 | Rate My Profesor | Lina Kloub's RMP | https://www.ratemyprofessors.com/professor/2754387 | 
| 2 | Rate My Profesor | Olga's RMP | https://www.ratemyprofessors.com/professor/2963544 |
| 3 | Rate My Profesor | Swamy's RMP | https://www.ratemyprofessors.com/professor/3044671 |
| 4 | Rate My Profesor | Justin's RMP | https://www.ratemyprofessors.com/professor/3127655 |
| 5 | Rate My Profesor | David Strimple's RMP | https://www.ratemyprofessors.com/professor/2872422 |
| 6 | Rate My Profesor | Derek's RMP | https://www.ratemyprofessors.com/professor/2460362 |
| 7 | Rate My Profesor | Laurent's RMP | https://www.ratemyprofessors.com/professor/1135923 |
| 8 | Rate My Profesor | Timothy Curry's RMP | https://www.ratemyprofessors.com/professor/2945690 |
| 9 | Rate My Profesor | Zhije's RMP | https://www.ratemyprofessors.com/professor/1282131 |
| 10 | Rate My Profesor | Alexander Russell's RMP | https://www.ratemyprofessors.com/professor/1691848 |

---

## Chunking Strategy

**Chunk size:**
230 tokens

**Overlap:**
20 tokens

**Why these choices fit your documents:**
Since each review is separate from each other, the overlap doesn't have to be as drastic since it will be searching
for key words only. Recursive chunking strategy is best for these documents. Chunk size is capped at 230 tokens
because all-MiniLM-L6-v2 only embeds the first 256 tokens of any input and silently truncates the rest; 230 leaves
headroom for the "Professor:" prefix while keeping every chunk fully within the model's window. Preprocessing strips
the per-review rating line and joins hard-wrapped lines into clean prose before chunking.

**Final chunk count:**
47 chunks total across 10 professors (each professor contributes 1 "overall" stats chunk plus
~3-4 review chunks).

---

## Embedding Model

**Model used:**
All-MiniLM-L6-v2 via sentence-transformers

**Production tradeoff reflection:**
I might use a larger hosted model like OpenAI text-embedding-3-large for better accuracy on heavier review texts with slang and higher retrieval quality. It would also weigh in multilingual spport if reviews span different languages.

---

## Grounded Generation

**System prompt grounding instruction:**

The model is given a fixed role that forbids outside knowledge before it ever sees a question
in `SYSTEM_PROMPT` in `generate.py`. This is the prompt I used in Claude Code:

> You are The Unofficial Guide, a study assistant that answers questions about
> university professors using only real student reviews from RateMyProfessors. You
> must answer strictly from the provided documents.

Then every question is wrapped in this template (`PROMPT_TEMPLATE` in `generate.py`),
which injects the retrieved chunks as the *only* source of truth and gives the model
an explicit escape hatch instead of guessing:

> Answer the question using only the information in the provided documents below. If
> the documents don't contain enough information to answer, say exactly: "I don't have
> enough information on that."
>
> Do not use any outside knowledge. Do not guess. When you state a fact, it must be
> supported by the documents. Cite the documents you used with their bracketed
> numbers, e.g. [1], [2].

**Context formatting** - Retrieved chunks are numbered and that bracket number is the
  *same* index as the source we later display, so a ciatation maps to a real document.
  The model can't cite a document that wasn't retrieved.

**Low-relevance filtering.** Before any LLM call, if there are no chunks — or the
  closest chunk's cosine similarity is below the `MAX_DISTANCE` threshold — the
  system returns the refusal string in code and never queries the model. An
  off-topic question (e.g. "Is the sky blue?") is refused without the LLM 
  seeing it at all.

**How source attribution is surfaced in the response:**

Source attribution is **programmatically guaranteed** as it is built in Python from the chunks
the retrieve actually returned, never parsed from the model's text, so the model can't invent a citation.
There's three levels to this source attribution:

1. **Inline citations** - the model writes `[1]`, `[2]` mapping to the numbered context blocks.
2. **A document-name line appeneded after generation** - `Sources used: David Strimple (david_strimple_2872422.txt)` -
built from the retrieved chunks' metadata so it travels with the answer itself.
3. **A full Sources panel** - In the gradio UI, it lists each chunk's profesor, section, the quoted chunk text, distance
score, and a clickable RateMyProfessors link.

---

## Evaluation Report

| # | Question | Expected answer | System response (summarized) | Retrieval quality | Response accuracy |
|---|----------|-----------------|------------------------------|-------------------|-------------------|
| 1 | Are Lina Kloub's exams difficult? | Lina Kloub's exams might seem a bit difficult but fair since the material on the exams if everything she has shown. | According to the documents, there are mixed reviews about the difficulty of Lina Kloub's exams. Some students found them manageable [2], fair [3], and had no complaints [3], while others thought they were difficult [4]. It can be concluded that the difficulty of Lina Kloub's exams may vary depending on individual student preparation and perspective. | Relevant | |
| 2 | Do students recommend taking Swamy's class? | 86% of students recommend taking Swamy's class with a lot of students saying he is caring. | Yes, students recommend taking Swamy's class. According to the reviews, many students have positive opinions about Swamy, with one student stating "Best prof for CSE3100. If you are willing to learn, you will gain a lot" [4]. Additionally, the overall rating is 4.3/5 and 86% of students would take the class again [5]. | Partially Relevant | Partially Accurate |
| 3 | Is attendance mandatory for Olga's class? | Attendance for Olga's class is not mandatory and lectures are often not helpful. | According to the documents, attendance is not mandatory for Olga Glebova's class [1]. | Relevant | Accurate |
| 4 | Is David Strimple's grading rubric harsh? | Many students suggest David Strimple is a tough grader and that you will have to learn everything yourself. | Yes, according to the reviews, David Strimple's grading rubric is harsh. In document [1], he is tagged as a "Tough Grader" and in document [3], a student mentions that he "is definitely a harsh grader and will take points off for very minor mistakes" [3]. This suggests that his grading rubric is strict and may not allow for much flexibility or variation in student responses. | Relevant | Accurate |
| 5 | What teaching style do reviews describe for David Strimple? | Many students suggest that the profesor expects you to know a lot and doesn't teach. Instead, he reads from really bad slides and talks about his life. | The reviews describe David Strimple's teaching style as difficult to follow, with many errors in his lectures [2]. He is said to rely heavily on pre-recorded videos from the previous year [2] and reads from "really bad slides" [3]. | Relevant | Accurate |

**Retrieval quality:** Relevant / Partially relevant / Off-target  
**Response accuracy:** Accurate / Partially accurate / Inaccurate

---

## Failure Case Analysis

**Question that failed:**
"Do students recommend taking Swamy's class?"

**What the system returned:**
The answer was directionally right but it asserted a specific statistic that stated "the overall rating is 4.3/5 and 86% of students would take the class again [5]" - and attributed it to source **[5]** which was **Lina Kloub's** review chunk not Swamy's. The number is real but the model had no grounded source for it in the context that was given.

**Root cause (tied to a specific pipeline stage):**
This is a **retrieval cutoff** failure, not a generation failure. Swamy's stats are stored in a separate chunk `Overall rating: 4.3/5 | Would take again (%): 86% | ...` which reads not as a conversational, recommendation-style language of the query. It was ranked #8 with a similarity of 0.357 while the top 4 are Swamy's review chunks. #5 was taken by a Lina Kloub review that out-scored Swamy's own stats chunk. The wrong profesor chunk leaked in caused by near-identical language and the embedding model simply scores natural-language reviews closer to a natural-language question.

**What you would change to fix it:**
1. **Guarantee the stats chunk for single-professor questions.** 
When the query clearly targets one profesor, always inject that profesor's "overall" chunk into the context regardless of distance rank. 
2. **Modestly raise top-k (e.g. 5 → 8).** 
At k=8 the stats chunk is included but the tradeoff is more noise in context.

---

## Spec Reflection

**One way the spec helped you during implementation:**
Writing the fixed 230 token chunks with 20 token overlap and tools into planning.md before coding
meant the implementation could be built almost directly from the spec instead of plain guessing.
The Retrieval Approach with the top-k=5 and embedding model being all-MiniLM-L6-v2 and the
Architecture diagram mapped each pipeline stage to a specific library are important. Since
every stage already has a target value, the code has clear parameters to hit.

**One way your implementation diverged from the spec, and why:**
The AI diverged from the spec as during the implementation, it added two retrieval safeguards that
weren't in the spec which included a per-professor metadata filter and a `MAX_DISTANCE` low-relevance
cutoff that refuses in code before any LLM call when no chunk is similar enough. The top-k search
from the spec wasn't enough to keep answers grounded in the right profesor's reviews.

---

## AI Usage

<!-- Describe at least 2 specific instances where you used an AI tool during this project.
     For each: what did you give the AI as input, what did it produce, and what did you
     change, override, or direct differently?

     "I used Claude to help me code" is not sufficient.
     "I gave Claude my Chunking Strategy section from planning.md and asked it to implement
     chunk_text(). It returned a function using a fixed character split. I overrode the
     chunk size from 500 to 200 because my documents are short reviews, not long guides." -->

**Instance 1**

- *What I gave the AI:* My Documents and Chunking Strategy sections in my `planning.md` (the 10 RateMyProfesors
  pages, 230-token chunk size, 20-token overlap recursive chunking decision) and asked Claude Code to turn the 
  raw profesor pages into clean template so I can manually input the reviews onto.
- *What it produced:* An ingestion script that strips the per-review rating, joins hard-wrapped 
  lines into clean prose, and splits each professor's reviews into chunks with metadata 
  (`professor`, `section`, `source_file`, `url`, `tokens`) that the rest of the pipeline relies on.
- *What I changed or overrode:* I held the chunk size to 230 tokens specifically because
  all-MiniLM-L6-v2 truncates anything past 256 tokens, and I had it split each professor 
  into a separate "overall" stats chunk plus individual review chunks rather than
  one massive chunk.

**Instance 2**

- *What I gave the AI:* My Grounded Generation requirements and the Architecture diagram
  and asked Claude Code to wire the existing `retrieve()` function to the LLM with guaranteed
  source attribution. I also asked Claude to use the tools that's given such as Groq 
  `llama-3.3-70b-versatile`, a Gradio interface, and retrieved chunks.
- *What it produced:* A `generate.py` with a system prompt and context template that instructs
  the model to answer only from the retrieved chunks, plus an `app.py` Gradio UI showing 
  the answer and a sources panel.
- *What I changed or overrode:* I directed two things that the first prompt didn't do. First, I
  required the source list to be built in Python from the actually-retrieved chunks rather
  than parsed from the model's text, so a citation can never be invented. Second, I added 
  the `MAX_DISTANCE` low-relevance cutoff that refuses in code before the LLM is ever called.
