# F-27 — Framework relationship assessment, 2026-09-11

All 1,149 source associations have a bound assessment record or an explicit unresolved requirement. **762 have desk assessments; 387 remain not assessed. No human review or approval is recorded. F-27 remains open.**

This is a relationship review candidate. It does not grant a framework certification, legal conformity, publisher endorsement or Board approval. The original catalog strings are preserved; proposed narrowing and replacement are recorded separately for review.

## Results

| Relationship | Records | Meaning |
|---|---:|---|
| `informative_topic_association` | 105 | Publication context only; no clause-level claim. |
| `no_claim` | 52 | Proposed withdrawal or reassignment of this measurement relationship. |
| `not_assessed` | 387 | Edition, evidence or substantive examination still outstanding. |
| `partial_support` | 350 | Only a narrower facet or part of the compound reference is supported. |
| `supports_measurement_of` | 255 | The specific observation supports measurement within the cited element; no whole-element attainment. |

## Sources and scope

The desk assessments use the following published primary sources. Edition choices that were absent from a card are **selected review baselines**, not claims about the original author’s intended edition. Full source metadata and locators are in [framework-sources.yaml](../../catalog/framework-sources.yaml).

| Source | Assessment scope | Records |
|---|---|---:|
| [CIS Controls 8.1](https://www.cisecurity.org/controls/cis-controls-list) | Individually numbered Controls 1-18; v8.1 publisher page | 215 |
| [FAIR 2.0.1](https://publications.opengroup.org/c20a) | Open FAIR Risk Analysis (O-RA) Version 2.0.1, November 2021; public publication scope | 1 |
| [ISO/IEC 27004 2016](https://www.iso.org/standard/64120.html) | Public Abstract and General information (edition 2, December 2016) | 83 |
| [MITRE ATLAS 2026.08](https://raw.githubusercontent.com/mitre-atlas/atlas-data/41d4f5ca4112f0e492ffaa3ebff07dc80a75afa5/dist/v6/ATLAS-2026.08.yaml) | ATLAS 2026.08, technique AML.T0051 (LLM Prompt Injection) | 1 |
| [NIST SP 800-111 2007](https://csrc.nist.gov/pubs/sp/800/111/final) | Publication abstract; November 2007 | 1 |
| [NIST SP 800-115 2008](https://csrc.nist.gov/pubs/sp/800/115/final) | Publication abstract; September 2008 | 1 |
| [NIST SP 800-207 2020](https://csrc.nist.gov/pubs/sp/800/207/final) | Publication abstract; August 2020 | 1 |
| [NIST SP 800-50 1](https://csrc.nist.gov/pubs/sp/800/50/r1/final) | Publication abstract; September 2024 | 3 |
| [NIST SP 800-53 5](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-53r5.pdf) | Chapter 3, individually identified controls; September 2020 including December 10, 2020 updates | 36 |
| [NIST SP 800-61 3](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf) | Section 3, Tables 2 and 3, CSF category rows | 43 |
| [NIST SP 800-82 3](https://csrc.nist.gov/pubs/sp/800/82/r3/final) | Publication abstract; September 2023 | 1 |
| [NIST SP 800-92 2006](https://csrc.nist.gov/pubs/sp/800/92/final) | Publication abstract; September 2006 | 13 |
| [NIST AI RMF 1.0](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) | AI RMF 1.0 (2023), section 5: function tables and individually numbered outcomes | 10 |
| [NIST CSF 2.0](https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf) | Appendix A, printed pages 15-23; section 4 for informative relationships | 324 |
| [NIST PQC 2024](https://csrc.nist.gov/pubs/fips/203/final) | Final FIPS 203, 204 and 205; August 13, 2024; public algorithm scopes | 1 |
| [NIST Privacy Framework 1.0](https://www.nist.gov/privacy-framework/privacy-framework) | Privacy Framework Version 1.0 (January 2020), public publication scope | 1 |
| [OpenSSF Scorecard pinned revision](https://raw.githubusercontent.com/ossf/scorecard/09a80e3f20a6412cff5aecf1ca124c139e51f86a/docs/checks.md) | Pinned check documentation: Vulnerabilities, Branch-Protection, Code-Review, Signed-Releases, Token-Permissions and Maintained | 5 |
| [OWASP Top 10 for LLM Applications 2025](https://genai.owasp.org/llm-top-10/) | 2025 edition, LLM01: Prompt Injection | 1 |
| [OWASP SAMM 2.2.0](https://github.com/owaspsamm/core/releases/tag/v2.2.0) | Version 2.2.0: security practice descriptions, pinned source files | 14 |
| [OWASP secrets management pinned revision](https://raw.githubusercontent.com/OWASP/CheatSheetSeries/fcd8b68435a268ecaa1a4729c5ac68bb5fb08cc7/cheatsheets/Secrets_Management_Cheat_Sheet.md) | Secrets Management Cheat Sheet, sections 2.3, 2.6 and 2.7; pinned source revision | 1 |
| [SLSA 1.2](https://slsa.dev/spec/v1.2/) | Version 1.2, Build and Source tracks | 6 |

The ISO/IEC 27004:2016 entries are limited to the publisher’s public abstract. Its reference to an older ISO/IEC 27001 edition does not establish correspondence to ISO/IEC 27001:2022. Neither unseen clause text nor an unpublished successor has been evaluated.

## Examples that need correction in the mapping interpretation

| Card | Existing association | Proposed disposition |
|---|---|---|
| STD-034 | CSF DE/RS; CIS 8/10/13/17 | MFA coverage observes authentication, not detection, malware response or incident handling. Keep PR.AA and the applicable access-control facet. |
| SOC-002 | CSF RS/RC | Detection time does not measure response or recovery execution. The detection association is assessed separately. |
| STD-049 | CIS 1/2/3/4 | Effective cloud logging needs the logging-control relationship, not blanket inheritance of all asset, software, data and configuration controls. |
| LOG-008 | SP 800-53 AU-9/AU-10/AU-11 | Integrity controls support AU-9. Non-repudiation and retention require separate evidence. |
| APP-006 | SLSA | SBOM presence does not establish build provenance. No SLSA measurement claim retained in this candidate. |
| APP-013 / APP-014 | SLSA | Package health and runtime drift do not establish Source/Build track requirements. |

Additional assessments narrow OWASP SAMM to versioned practices and distinguish AI risk observations from benefits and treatment. CRY-001 migration readiness does not establish implementation of the three cited cryptographic algorithms. The FAIR entry is limited to the public scope of a historical, superseded publication; full method equivalence remains unproven.

All 52 no-claim dispositions below are proposals, not approved catalog removals. Lack of a direct measurement relationship does not mean the topic can never be relevant in an organization. Broad indirect relationships must be justified rather than inherited from a bundle.

## Outstanding substantive work

| Requirement | Records | Completion evidence |
|---|---:|---|
| `applicable_legal_or_guidance_scope_required` | 115 | Exact instrument/publication, applicable article/section and entity/activity scope; compare unmeasured obligations too. A regulator name is not an article reference. |
| `authorized_clause_evidence_required` | 180 | Authorized comparison of the exact published standard/part and clause. A bibliographic page cannot substantiate Annex A or other unseen requirements. |
| `edition_and_element_review_required` | 13 | Remaining primary-text assessment with selected edition, measured element and limits. This is still repository work; no claim that the user must supply all of it. |
| `identifiable_source_required` | 7 | Identifiable authorized publication or versioned local policy/contract locator; retain only necessary public information. |
| `versioned_object_or_dataset_required` | 72 | Pinned techniques, data components, check IDs, model/data version and applicability to the card observation. Dataset use must be distinguished from framework coverage. |

Each outstanding entry includes its card ID/version, source and card hashes, definition context, explicit blocker and next action in [framework-mapping-assessments.yaml](../../catalog/framework-mapping-assessments.yaml). Missing edition or clause work is not converted to approval by generating this report.

## Validation and review workflow

1. Read the exact card formula, population, evidence requirements and decision alongside the stated source reference.
2. Examine the proposed source edition and relationship, supported and unsupported elements, and any replacement outside the original citation. Independently evaluate the source text before accepting it.
3. Record the actual review decision, reviewer, date and rationale in a public OSMS issue or pull request. Add its URL and exact assessment hash to [framework-mapping-reviews.yaml](../../catalog/framework-mapping-reviews.yaml). These fields are currently empty; no real reviewer is impersonated.
4. Run the validator. Card content, source metadata, reference, edition and assessment changes invalidate dependent records. A metadata hash binds the reviewed source description; it is not a downloaded-document content hash or an automatic check for publisher updates.

```sh
python tools/framework_mappings.py --require-triaged --out framework-mapping-register.json
python -m unittest discover -s tests -p test_framework_mappings.py
# This must currently fail: actual reviews remain outstanding.
python tools/framework_mappings.py --require-reviewed --out framework-mapping-register.json

```
Generation, semantic assessment, actual review and approval have separate counters. `--require-triaged` checks accounting only and cannot satisfy the review-completion gate. The validator checks consistency of reviewer records, not the authenticity of a person or the truth of their evaluation.

## Source binding

Catalog baseline: `432ab0c3207b2a7693ac7ec7581d47db3567d46d`. Catalog SHA-256: `1b128973da1db2d71c9381e504eb9a328902fd2a7efae2491438a97aa453fe2c`. Card content and calculation semantics are unchanged in this mapping work. The generated register records hashes for every assessment/source/policy/validator input; GitHub CI supplies the checked commit and environment.

## Proposed no-claim dispositions

| Card | Existing reference | Proposed elements outside the citation |
|---|---|---|
| MET-006 | CIS Controls 18 | No replacement asserted |
| AIM-011 | NIST AI RMF: Manage | MEASURE.2.7 |
| AIM-012 | NIST AI RMF: Measure | MAP.3.1 |
| APP-006 | SLSA | No replacement asserted |
| APP-010 | OpenSSF Scorecard | No replacement asserted |
| APP-013 | SLSA | No replacement asserted |
| APP-014 | SLSA | No replacement asserted |
| STD-032 | NIST CSF 2.0: GV | ID.AM |
| STD-043 | NIST CSF 2.0: ID.AM, PR | ID.RA, GV.OV |
| STD-044 | NIST CSF 2.0: GV | PR.PS |
| STD-045 | CIS Controls v8.1: 1, 2, 3, 4 | 6 |
| STD-046 | CIS Controls v8.1: 1, 2, 3, 4 | 6 |
| STD-049 | CIS Controls v8.1: 1, 2, 3, 4 | 8 |
| STD-052 | NIST CSF 2.0: RS, RC | ID.RA, PR.AA |
| STD-052 | CIS Controls v8.1: 17 | 6 |
| STD-052 | CIS Controls v8.1: 1, 2, 3, 4 | 6 |
| CRY-001 | NIST PQC FIPS 203/204/205 | No replacement asserted |
| DET-015 | CIS Control 8 | 13 |
| STD-001a | NIST CSF 2.0: DE/RS | ID.RA |
| STD-034 | NIST CSF 2.0: DE, RS | PR.AA |
| STD-034 | CIS Controls v8.1: 8, 10, 13, 17 | 6 |
| STD-040 | CIS Controls v8.1: 1, 2, 3, 4 | 5, 6 |
| STD-041 | CIS Controls v8.1: 1, 2, 3, 4 | 6 |
| STD-067 | NIST CSF 2.0: RC | PR.DS |
| STD-068 | NIST CSF 2.0: RC | PR.DS |
| STD-069 | CIS Controls v8.1: 11 | 17 |
| STD-070 | CIS Controls v8.1: 11 | 15 |
| STD-072 | CIS Controls v8.1: 11 | 17 |
| LOG-016 | NIST CSF 2.0 GV.RM | GV.RR |
| LOG-016 | CIS Control 8 | No replacement asserted |
| SOC-001 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-002 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-004 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-005 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-006 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-007 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-008 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-010 | NIST CSF 2.0: RS, RC | DE.AE |
| SOC-011 | NIST CSF 2.0: RS, RC | DE.AE |
| SOC-013 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-014 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-016 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-018 | NIST CSF 2.0: DE, RS | PR.IR |
| SOC-018 | NIST CSF 2.0: RS, RC | PR.IR |
| SOC-019 | NIST CSF 2.0: RS, RC | DE.CM |
| SOC-020 | NIST CSF 2.0: RS, RC | GV.RR |
| SOC-020 | CIS Controls v8.1: 17 | No replacement asserted |
| SOC-023 | NIST CSF 2.0: DE.CM, RS.AN | DE.AE |
| SOC-032 | NIST CSF 2.0: RS, RC | GV.RR |
| SOC-032 | CIS Controls v8.1: 17 | No replacement asserted |
| SOC-078 | NIST CSF 2.0: ID.AM, PR | ID.RA, GV.RM |
| SOC-078 | CIS Controls v8.1: 1, 2, 3, 4 | No replacement asserted |

## Observed local verification

Python 3.12.14; pinned repository test dependencies. The complete regression suite passed **124 tests**. The final additional source records were also checked by the 16 focused mapping tests. Both command-line gates were exercised: `--require-triaged` returned 0; `--require-reviewed` returned 1 as required while actual reviews are absent. The board packet contains all 327 dossiers and the assessed mapping records, with zero structural errors. These automated results do not constitute a human mapping approval.
