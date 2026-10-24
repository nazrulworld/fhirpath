# FHIR search – missing features task list

Gap analysis of `src/fhirpath/search/` against FHIR R5 search (STU3/R4/R4B differences per
`.claude/skills/fhir-search/references/versions.md`). Snapshot 2026-10-25.

## A. Correctness bugs / SHALL violations

- [x] Paging links unusable: `BundleWrapper.attach_links` emits `search-offset`/`search-id`, but
      `Search.prepare_params` only understands `page`, so following `next` raises `ValidationError`.
- [x] Unsupported modifiers silently ignored (e.g. `code:in=…` runs as plain match); spec: SHALL reject (400).
      Validate modifier against parameter type (and `SearchParameter.modifier` where defined).
- [x] Escaping only handles `\,`; add `\$`, `\|`, `\\`, reject lone `\x`.
- [x] `self` link echoes the request URL instead of the parameters actually applied.
- [x] `resolve() is X` / reference type restrictions only logged, not enforced.

Done (2026-10-25): paging links use `page`/`_count`; modifiers outside `SUPPORTED_MODIFIERS`
(per type), non-target `[type]` modifiers, modifiers on composites and modifiers not in a definition's
`modifier` list are rejected (`ValidationError`); `\,` `\$` `\|` `\\` escapes (lone `\x` rejected),
unescaped at the leaf terms; `self` link built from the applied (non-empty) parameters; plain reference
ids narrowed to `X/id` by `where(resolve() is X)`. Tests: `tests/search/test_spec_conformance.py`.

## B. Matching semantics vs spec

- [ ] String default = ES `match` with `fuzziness: AUTO`; spec: case/accent-insensitive starts-with.
- [ ] Token `|code` matches any system; spec: code with **no** system.
- [ ] Token matching analyzer-dependent; should be exact/case-sensitive.
- [ ] No implicit precision ranges for number/date `eq` (`100` → [99.5,100.5), `2013-01` → whole month).
- [ ] `ap` prefix only for Period; missing for number/date/quantity.
- [ ] `:below`/`:above` mapped to string prefix/suffix; spec: subsumption (token), hierarchy (reference),
      path segments (uri), version (canonical).
- [ ] Reference equivalence: absolute URL of local refs ≡ `Type/id`; optionally reject ambiguous plain `id`
      (plain `id` is now searched as `Type/id` for every target).
- [ ] `:missing=true` should treat extension-only elements as missing.
- [ ] Composite: OR across tuples, same-repetition matching, `combo-*` token params.
- [ ] Unsupported target types: Range, Timing, SampledData, Attachment, Narrative; non-path expression
      branches (`extension(url)`, computed `deceased`).

## C. Modifiers not implemented

- [ ] `:in` / `:not-in` (ValueSet expansion)
- [ ] `:of-type` (Identifier)
- [ ] `:code-text`, `:text-advanced` (R5)
- [x] `:[type]` on plain reference params (`subject:Patient=23` → `subject=Patient/23`)
- [ ] `:iterate` (`:recurse` in STU3) for `_include`/`_revinclude`

## D. Result parameters

- [ ] `_total` (parsed, unused)
- [ ] `_contained`, `_containedType` (parsed, unused)
- [ ] `_elements`: add mandatory + modifier elements, `SUBSETTED` tag
- [ ] `_summary`: `SUBSETTED` tag
- [ ] `_include`/`_revinclude`: `*` wildcard, per-page application, remove 100 cap
- [ ] `_count=0` ≡ `_summary=count`
- [ ] `_maxresults`, `_score`, `_graph`
- [ ] `_sort`: all expression paths, chained sort

## E. Search features not implemented

- [ ] `_filter` (grammar + operators)
- [ ] `_query` (named queries; unknown → refuse)
- [ ] `_text`, `_content`
- [ ] `_list`, `_in` (R5)
- [ ] Compartment search (`Patient/1/Observation`, `Patient/1/*`)
- [ ] System-level search: only common params unless `_type` given
- [ ] `near` (special)

## F. Errors / HTTP layer

- [x] Unknown params: ignore by default (drop from self link); raise only with `Prefer: handling=strict`
      (`Search(..., handling="strict")` / `fhir_search(..., handling=…)`, `handling_from_prefer(header)`;
      ignored names in `Search.ignored_params` for a future OperationOutcome)
- [ ] `OperationOutcome` entries (`search.mode=outcome`) for warnings
- [ ] CapabilityStatement search capability output
- [ ] `POST _search` (form body)

## G. Housekeeping

- [ ] Keep `.claude/skills/fhir-search/references/project-map.md` deviations table in sync
- [ ] Spec-example tests in `tests/search/` for each item
