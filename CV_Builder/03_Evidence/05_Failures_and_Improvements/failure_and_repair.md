# Failures and Repairs

Every real bug hit while building this system, in the order encountered, with root
cause and fix. Design decisions and rejected alternatives (e.g. rule-based vs. LLM
extraction, TF-IDF vs. real embeddings) are recorded in
`03_Evidence/01_Prompts/prompt_record.md` instead — this file is specifically for
things that broke and had to be fixed.

## 1. GROQ model name didn't exist on this key

**Symptom:** `groq.NotFoundError: 404 — model 'llama-3.3-70b-versatile' does not exist
or you do not have access to it.`
**Root cause:** guessed a plausible-sounding model name instead of checking what the
key actually has access to.
**Fix:** called `client.models.list()`, found the real catalog, switched to
`openai/gpt-oss-20b`.

## 2. Reasoning model returned empty content under a small token budget

**Symptom:** a smoke-test call with `max_tokens=20` returned `''` (empty string).
**Root cause:** `openai/gpt-oss-20b` is a reasoning model — it spends tokens on hidden
reasoning before emitting the visible response, so a tight budget can be exhausted
before any visible content is produced.
**Fix:** raised `max_tokens` generously everywhere it's used (300–1024 for
extraction/follow-up/summary calls).

## 3. GROQ has no embeddings-capable model on this key

**Symptom:** `groq.BadRequestError: 400 — the model 'openai/gpt-oss-20b' does not
support embeddings.`
**Root cause:** GROQ doesn't serve a dedicated embedding model on this key at all
(confirmed by testing the `client.embeddings.create` endpoint directly).
**Fix:** job retrieval uses local `sentence-transformers` (`all-MiniLM-L6-v2`) instead
of a GROQ call — a separate design decision, not just a token-budget fix (see
`prompt_record.md` for the full reasoning/confirmation).

## 4. `.env` file saved with a hidden `.txt` extension

**Symptom:** `python-dotenv` silently found no `GROQ_API_KEY` even though the user had
just created the file.
**Root cause:** Notepad saved it as `.env.txt`, not `.env` — Windows hides known file
extensions by default, so the file looked correctly named in Explorer.
**Fix:** renamed the file; flagged the fix so the user knew what happened and why.

## 5. CV generation hit the max-token JSON-validation error under the longer prompt

**Symptom:** `groq.BadRequestError: 400 — Failed to generate JSON ... max completion
tokens reached before generating a valid document.`
**Root cause:** the V2 CV-generation prompt (with the added ordering instructions) is
longer and asks for a larger structured JSON output than earlier calls; combined with
issue #2's hidden reasoning-token cost, `max_tokens=2048` wasn't enough headroom.
**Fix:** raised to `max_tokens=4096` for the CV-generation call specifically.

## 6. Windows console crashed on a Unicode character in model output

**Symptom:** `UnicodeEncodeError: 'charmap' codec can't encode character '‑'`
when the CLI tried to print GROQ's generated text to the terminal.
**Root cause:** the model frequently generates a non-breaking hyphen (U+2011) in
phrases like "third‑year"; Windows' console codepage (cp1252) has no mapping for it.
**Fix:** reconfigured `sys.stdout` to UTF-8 with `errors="replace"` at the top of the
CLI scripts. This only affected the CLI's own console echo — PDF rendering was a
separate, later bug (#9).

## 7. Non-interactive test runs crashed on `input()` for unscripted fields

**Symptom:** `EOFError: EOF when reading a line` when running `export_cv.py` with
`--edits-json` supplying only some of the editable fields.
**Root cause:** `edit_cv_interactive` only checked whether a specific field had a
scripted edit; for any field it didn't, it fell through to a real `input()` call,
which fails immediately when there's no attached stdin (as in an automated run).
**Fix:** changed the semantics so that passing *any* `scripted_edits` dict (even a
partial one, even `{}`) puts the whole call into non-interactive mode: named fields
get their scripted value, everything else is left unchanged, and `input()` is never
called. Only a `None` (the true default, real interactive use) prompts.

## 8. Skills bullet list rendered with no gap between bullet and text

**Symptom:** PDF showed `●Python` instead of `● Python` for every skill.
**Root cause:** `reportlab.platypus.ListFlowable`'s bullet spacing didn't behave as
expected with the indent settings used.
**Fix:** dropped `ListFlowable` for the skills list; used plain `Paragraph(...,
bulletText="•")` with an explicit `leftIndent`, which renders a normal gap.

## 9. Non-breaking hyphen rendered as a solid black box in the PDF

**Symptom:** every instance of "third‑year", "hands‑on", "library‑booking" etc. in a
rendered PDF showed a filled black square (■) instead of a hyphen.
**Root cause:** reportlab's built-in `Helvetica` is a standard PDF Type 1 font using
WinAnsi encoding, which has no glyph for U+2011 (NON-BREAKING HYPHEN) — the character
the model keeps generating. Console output (#6) and PDF rendering are two separate
text pipelines with two separate encoding problems; fixing #6 did not fix this one.
**Fix:** added a `_clean()` sanitizer in `cv_pdf.py`, applied to every piece of
dynamic text before it reaches a `Paragraph`: XML-escapes `&`/`<`/`>` (Paragraph text
is parsed as mini-XML) and replaces U+2011/U+2010 with a plain ASCII hyphen.
Regenerated every previously-exported sample PDF afterward to confirm the fix.

## 10. Test-harness bug: scripted follow-up replies desynced from the questions actually asked

**Symptom:** the Devon Okafor test profile asked "target_roles" three times in a row
and hit the step-limit cap without ever confirming, despite a 6-item scripted-replies
list that looked like it covered every possible field.
**Root cause:** this was a bug in the *test I wrote*, not the agent: `scripted_replies`
is a flat FIFO list consumed strictly in the order questions are asked, not matched by
field name. I'd padded each incomplete persona's reply list with answers for all six
possible required fields as a "safety net," assuming unused ones would just be
skipped — but the very first field only some personas were actually missing meant every
reply after that ended up answering the *wrong* question (e.g. a "here's my degree"
reply landed on the "what roles are you targeting" question, which naturally didn't
extract a target role, so the agent kept re-asking).
**Fix:** for each incomplete persona, ran the initial extraction once in isolation to
see exactly which fields `missing_fields()` actually returned, then trimmed
`scripted_replies` to precisely those fields, in that order — no padding.

## 11. Cross-user isolation test's first leak-detection check produced a false positive

**Symptom:** `no_skill_leak: False` and `CV A contaminated by B: True` even though the
two users' profiles were provably built by two separate `ProfileTool` instances.
**Root cause:** the check used "no overlapping skill names between the two profiles"
as the leak signal — but Ethan Brooks and Devon Okafor both legitimately listed
"Python," which is not evidence of state leakage, just two unrelated people knowing
the same common language.
**Fix:** switched the leak-detection signal to project-title overlap instead (unique
per persona in this synthetic test data), which correctly reported no leakage while
still being a genuine, checkable signal rather than a hand-waved assumption.
