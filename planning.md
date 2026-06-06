# Project 1 Planning: The Unofficial Guide

> Write this document before you write any pipeline code.
> Your spec and architecture diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Update the Retrieval Approach and Chunking Strategy sections if you change your approach during implementation.
> Update this file before starting any stretch features.

---

## Domain

<!-- What domain did you choose? Why is this knowledge valuable and hard to find through official channels? -->

The domain I chose is Rate My Profesors. This knowledge is valuable because these 
are real reviews that students who have taken the class submitted.
---

## Documents

<!-- List your specific sources: URLs, subreddit names, forum threads, or file descriptions.
     Aim for at least 10 sources that together cover different subtopics or perspectives within your domain. -->

| # | Source | Description | URL or location |
|---|--------|-------------|-----------------|
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

<!-- How will you split documents into chunks?
     State your chunk size (in tokens or characters), overlap size, and explain why those
     numbers fit the structure of your documents.
     A review-heavy corpus warrants different chunking than a long FAQ. -->

**Chunk size:**
350 tokens

**Overlap:**
20 tokens

**Reasoning:**
Since each review is separate from each other, the overlap doesn't have to be as drastic since it will be searching
for key words only. Recursive chunking strategy is best for these documents.

---

## Retrieval Approach

<!-- Which embedding model are you using (e.g., all-MiniLM-L6-v2 via sentence-transformers)?
     How many chunks will you retrieve per query (top-k)?
     If you were deploying this for real users and cost wasn't a constraint, what tradeoffs
     would you weigh in choosing a different embedding model — context length, multilingual
     support, accuracy on domain-specific text, latency? -->

**Embedding model:**
All-MiniLM-L6-v2 via sentence-transformers

**Top-k:**
The top-k for our project is 3-5 but around 5 similar chunks is good.

**Production tradeoff reflection:**
I might use a larger hosted model like OpenAI text-embedding-3-large for better accuracy on heavier review texts with slang and higher retrieval quality. It would also weigh in multilingual spport if reviews span different languages.
---

## Evaluation Plan

<!-- List your 5 test questions with their expected correct answers.
     Questions should be specific enough that you can judge whether the system's response
     is right or wrong. "What are good dining halls?" is too vague.
     "What do students say about wait times at [dining hall name] during lunch?" is testable. -->

| # | Question | Expected answer |
|---|----------|-----------------|
| 1 | Are Lina Kloub's exams difficult? | Lina Kloub's exams might seem a bit difficult but fair since the material on the exams if everything she has shown. |
| 2 | Do students recommend taking Swamy's class? | 86% of students recommend taking Swamy's class with a lot of students saying he is caring. |
| 3 | Is attendance mandatory for Olga's class? | Attendance for Olga's class is not mandatory and lectures are often not helpful. |
| 4 | Is David Strimple's grading rubric harsh? | Many students suggest David Strimple is a tough grader and that you will have to learn everything yourself. |
| 5 | If you were to choose one profesor to take in terms of workload, would it be Lina Kloub or David Strimple? | Many students suggest Lina Kloub in terms of workload as David Strimple often doesn't teach well and gives lots of homework. |

---

## Anticipated Challenges

<!-- What could go wrong? Name at least two specific risks with reasoning.
     Consider: noisy or inconsistent documents, missing source attribution, off-topic
     retrieval, chunks that split key information across boundaries. -->

1. Off-topic and wrong-profesor retrieval since most of the RMP pages have similar or near identicial language. 

2. RMP reviews openly disagree and there is no ground truth.

---

## Architecture

<!-- Draw a diagram of your pipeline showing the five stages:
     Document Ingestion → Chunking → Embedding + Vector Store → Retrieval → Generation
     Label each stage with the tool or library you're using.
     You can use ASCII art, a Mermaid diagram, or embed a sketch as an image.
     You'll use this diagram as context when prompting AI tools to implement each stage. -->

---

## AI Tool Plan

<!-- For each part of the pipeline below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, which requirements)
     - What you expect it to produce
     - How you'll verify the output matches your spec

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Chunking Strategy section and ask it to implement chunk_text()
     with my specified chunk size and overlap" is a plan. -->

**Milestone 3 — Ingestion and chunking:**

**Milestone 4 — Embedding and retrieval:**

**Milestone 5 — Generation and interface:**
