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

- [x] String default = ES `match` with `fuzziness: AUTO`; spec: case/accent-insensitive starts-with.
- [x] Token `|code` matches any system; spec: code with **no** system.
- [x] Token matching analyzer-dependent; should be exact/case-sensitive.
- [x] No implicit precision ranges for number/date `eq` (`100` → [99.5,100.5), `2013-01` → whole month).
- [x] `ap` prefix only for Period; missing for number/date/quantity.
- [x] `:below`/`:above` mapped to string prefix/suffix; spec: subsumption (token), hierarchy (reference),
      path segments (uri), version (canonical).
- [x] Reference equivalence: absolute URL of local refs ≡ `Type/id`; optionally reject ambiguous plain `id`
      (plain `id` is now searched as `Type/id` for every target).
- [x] `:missing=true` should treat extension-only elements as missing.
- [x] Composite: OR across tuples, same-repetition matching, `combo-*` token params.
- [x] Unsupported target types: Range, Timing, SampledData, Attachment, Narrative; non-path expression
      branches (`extension(url)`, computed `deceased`).

Done (2026-10-25): `ranges.py` (precision ranges, `ap`), match types per parameter type in
`Search.create_term`/`set_match_type`, `terminology.py` for token `:below`/`:above`, reference hierarchies
(`resolve_hierarchy`), uri path segments, `reference_variants`, `value_exists_term`, `CompositeTuple`,
Range/Timing/Attachment/Narrative/extension/`ComputedPresence` targets. SampledData deliberately never
matches a quantity; accent-insensitive strings need an `asciifolding` normalizer in the index.
Tests: `tests/search/test_matching.py`, `test_chaining.py`.

## C. Modifiers not implemented

- [x] `:in` / `:not-in` (ValueSet expansion)
- [x] `:of-type` (Identifier)
- [x] `:code-text`, `:text-advanced` (R5)
- [x] `:[type]` on plain reference params (`subject:Patient=23` → `subject=Patient/23`)
- [x] `:iterate` (`:recurse` in STU3) for `_include`/`_revinclude`

Done (2026-10-25): `InMemoryTerminology` (release value sets + registered resources; `engine.terminology`
for another service), `:of-type`, `:code-text`/`:text-advanced` (R5 only), modifiers per spec matrix and
release; `resolve_includes` with `:iterate`.

## D. Result parameters

- [x] `_total` (parsed, unused)
- [x] `_contained`, `_containedType` (parsed, unused) – validated; `true`/`both` cannot be searched
      (contained resources are not indexed): ignored with a warning, an error with strict handling
- [x] `_elements`: add mandatory + modifier elements, `SUBSETTED` tag
- [x] `_summary`: `SUBSETTED` tag
- [x] `_include`/`_revinclude`: `*` wildcard, per-page application, remove 100 cap
- [x] `_count=0` ≡ `_summary=count`
- [x] `_maxresults`, `_score`, `_graph`
- [x] `_sort`: all expression paths, chained sort

Done (2026-10-25): `Search.prepare_params` validates every result parameter; `page_window`, `response`
(`_total=none`, `_score`, `subset_results`), `subsetting_elements`, `sort_fields`/`sort_leaves`,
`chained_sort_page` (in memory), `graph.py`. Tests: `tests/search/test_results.py`.

## E. Search features not implemented

- [x] `_filter` (grammar + operators)
- [x] `_query` (named queries; unknown → refuse)
- [x] `_text`, `_content`
- [x] `_list`, `_in` (R5)
- [x] Compartment search (`Patient/1/Observation`, `Patient/1/*`)
- [x] System-level search: only common params unless `_type` given
- [x] `near` (special)

Done (2026-10-25): `filter.py`, `register_named_query`, `text_terms`, `membership_ids`, `compartment=` on
`Search`/`fhir_search` (`compartment_definitions` downloads the CompartmentDefinitions), `near_box` (a box,
not sorted by distance). Tests: `tests/search/test_search_features.py`.

## F. Errors / HTTP layer

- [x] Unknown params: ignore by default (drop from self link); raise only with `Prefer: handling=strict`
      (`Search(..., handling="strict")` / `fhir_search(..., handling=…)`, `handling_from_prefer(header)`;
      ignored names in `Search.ignored_params` for a future OperationOutcome)
- [x] `OperationOutcome` entries (`search.mode=outcome`) for warnings – ignored unknown params now;
      more warnings (unknown codes/ids) can be added via `Search.outcome_issues()`
- [x] CapabilityStatement search capability output
- [x] `POST _search` (form body) – `Search(..., form_body=…)` / `fhir_search(..., form_body=…)`

## G. Housekeeping

- [x] Keep `.claude/skills/fhir-search/references/project-map.md` deviations table in sync
- [x] Spec-example tests in `tests/search/` for each item
