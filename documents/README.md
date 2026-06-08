# Documents — RateMyProfessors review corpus

This folder holds the raw source text for the RAG pipeline. **One `.txt` file per professor.**

## Why manual copy (not scraping)

RateMyProfessors renders reviews with JavaScript and blocks plain `requests` +
BeautifulSoup, so a naive scrape returns empty pages. Copying the text by hand is
slower but reliable and is the recommended approach for this project.

## File naming

```
<lowercase_name>_<rmpID>.txt
```

The RMP ID in the filename is what the ingestion code uses to tag every chunk with
the correct professor, so retrieval can tell professors apart (see Anticipated
Challenge #1 in planning.md). **Do not rename the files.**

## File format

Each file has three parts:

```
PROFESSOR: <name>
RMP_ID: <id>
URL: <link>

=== OVERALL ===
Overall rating:
Would take again (%):
Level of difficulty (1-5):
Top tags:

=== REVIEWS ===
<one review per block, separated by a blank line>
```

## How to fill each file

1. Open the professor's RMP page in your browser.
2. Fill in the `=== OVERALL ===` numbers from the top of the page.
3. Under `=== REVIEWS ===`, paste each review as its own block, separated by a
   **blank line**. The blank line between reviews is what lets the chunker keep
   reviews from bleeding into each other.
4. Optionally start a review with its ratings/course on one line, e.g.
   `Quality 5.0 | Difficulty 3.0 | CSE2050`, then the review text underneath.
5. Delete the bracketed `[...]` instruction line once you start pasting.

## Checklist (10 professors)

- [ ] lina_kloub_2754387.txt
- [ ] olga_2963544.txt
- [ ] swamy_3044671.txt
- [ ] justin_3127655.txt
- [ ] david_strimple_2872422.txt
- [ ] derek_2460362.txt
- [ ] laurent_1135923.txt
- [ ] timothy_curry_2945690.txt
- [ ] zhije_1282131.txt
- [ ] alexander_russell_1691848.txt
