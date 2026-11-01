# M1 IRS publication expansion research for the 2025 Tax Education corpus

Status: M1 primary-source research; no SourceRegistry approval, ingestion, qrel freeze, collection build, or activation is claimed

Researched: 2026-10-31

Scope: PR-007/PR-008; QR-007/QR-008/QR-012/QR-015; ADR-005/ADR-012/ADR-016/ADR-017

This note verifies the requested 2025 editions of IRS Publications 501, 523, 525, 544, 551, 554, 575, 721, 915, 925, 936, 970, and 1212 using official IRS primary sources only. It is decision input for the [M1 offline-ingestion and retrieval-evaluation workflow](../04_implementation_plan.md#m1--persistent-qdrant-and-offline-knowledge-ingestion), not evidence that any new source has passed intake or activation gates.

## Findings and recommendation

- All 13 requested editions resolve at official IRS prior-year PDF URLs using the stable `/pub/irs-prior/<product>--2025.pdf` pattern. The IRS prior-year catalog identifies itself as the official place to find prior-year forms, instructions, publications, and notices. ([IRS prior-year catalog](https://www.irs.gov/prior-year-forms-and-instructions))
- Eleven covers say **“For use in preparing 2025 Returns”** and support `tax_years: [2025]`, `jurisdiction: US-Federal`: Publications 501, 523, 525, 544, 554, 575, 721, 915, 925, 936, and 970.
- Publication 551 and Publication 1212 are **revision-dated products**, not annual-return-labeled editions. Publication 551 is “Rev. December 2025” and contains an explicit rule for tax years beginning in 2025, plus a warning that Publication 551 may not be revised for later inflation adjustments. Publication 1212 is “Rev. December 2025”; its separate OID tables are described as updated annually, but the PDF does not say “For use in preparing 2025 Returns.”
- No requested product is shown as discontinued: every requested 2025 PDF resolves and every official IRS About page labels a **Current revision** as of the research date. Treat that as a current observation, not a guarantee of future status.
- Publications 523, 551, and 575 match the already-indexed registry identities, immutable URLs, and existing qrels. The other ten are candidates for new source records. The qrel matrix below covers all 13 so the existing and proposed cases can be reviewed together.
- Every requested PDF contains an IRS notice that photographs of missing children selected by the National Center for Missing & Exploited Children (NCMEC) may appear on otherwise blank pages. The corpus extraction profile must exclude any such photographs, captions, identifying text, NCMEC marks, and non-tax call-to-action material.
- **Publication 1212 decision:** approve the reviewed PDF's IRS-authored narrative for indexing as `irs-p1212-rev-2025-12`, with `revision_date: 2025-12`, `tax_years: [2025]`, and `jurisdiction: US-Federal`. This is a revision-year corpus mapping, not a claim that every evergreen OID rule began in 2025 or that the edition applies to another year. Its separately hosted OID tables contain information from issuers and financial publications that the IRS says is generally not verified as correct. The official 2025 table page currently exposes only Sections I-C, II, and III-A and says information about the remaining sections is forthcoming. Do not crawl or index those tables under this source record; they require separate rights, provenance, completeness, and source-use review. ([Publication 1212, pp. 1–2](https://www.irs.gov/pub/irs-prior/p1212--2025.pdf), [2025 OID table status](https://www.irs.gov/forms-pubs/original-issue-discount-oid-tables))

## Source-use and extraction policy

The IRS says federal-employee-created or maintained IRS.gov content is not copyrighted and may be freely copied, with credit requested. The same policy says that copyrighted material appearing on or reached through IRS.gov requires consultation with the copyright holder, and it restricts use of Treasury/IRS names, seals, and symbols where use could imply endorsement or association. ([IRS.gov content-use policy](https://www.irs.gov/about-irs/use-of-content-from-irsgov)) IRS publishing guidance likewise says official-duty government publications without copyrighted material are not subject to copyright, while previously published copyrighted inclusions require permission and documented restrictions. ([IRM 1.17.8.6](https://www.irs.gov/irm/part1/irm_01-017-008#idm140092329605072))

Apply this common profile to all 13 PDFs:

1. Preserve the exact product number, title, edition/revision, immutable URL, publisher, `US-Federal` jurisdiction, supported tax-year metadata, page/section anchor, fetch date, and content hash.
2. Attribute the Internal Revenue Service and do not imply Treasury/IRS approval, sponsorship, endorsement, authorization, or association.
3. Extract tax text, headings, tables, worksheets, and IRS-authored examples only. Exclude cover/decorative images, seals, logos, symbols, photograph-only pages, and image alternative text that does not carry tax meaning.
4. Exclude all NCMEC photographs, captions, identifying details, marks, missing-child reminder text, and related non-tax call-to-action text. The notice says photographs **may** appear; this research did not establish by visual page audit whether a photograph is actually embedded in every edition.
5. Do not traverse linked pages or import linked material under the PDF's approval. Every linked product needs its own source record and review.
6. Monitor each product's Future Developments/current-product page and create a new immutable document version when content, corrections, or applicability change.

## Edition and applicability matrix

Suggested IDs are repository-shaped recommendations. “Annual” means the cover explicitly says it is for preparing 2025 returns. “Revision-dated” means the cover supplies a month/year revision but no annual-return statement.

| Suggested source ID | Exact IRS title and immutable 2025 PDF | Cover date and applicability metadata | Cadence/discontinued status | Source-specific extraction note |
| --- | --- | --- | --- | --- |
| `irs-p501-2025` | [Publication 501 (2025), Dependents, Standard Deduction, and Filing Information](https://www.irs.gov/pub/irs-prior/p501--2025.pdf) | Cover dated 2026-02-04; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. |
| `irs-p523-2025` | [Publication 523 (2025), Selling Your Home](https://www.irs.gov/pub/irs-prior/p523--2025.pdf) | Cover dated 2026-02-26; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion; existing indexed source verified. |
| `irs-p525-2025` | [Publication 525 (2025), Taxable and Nontaxable Income](https://www.irs.gov/pub/irs-prior/p525--2025.pdf) | Cover dated 2026-02-25; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. Broad source; section scope should be justified by the proposed qrel and overlap review. |
| `irs-p544-2025` | [Publication 544 (2025), Sales and Other Dispositions of Assets](https://www.irs.gov/pub/irs-prior/p544--2025.pdf) | Cover dated 2026-02-06; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. Review overlap with Publication 550 and the 2025 Schedule D/Form 8949 instructions before activation. |
| `irs-p551-rev-2025-12` | [Publication 551 (Rev. December 2025), Basis of Assets](https://www.irs.gov/pub/irs-prior/p551--2025.pdf) | Cover dated 2025-12-02; revision-dated; explicit 2025 uniform-capitalization threshold; repository mapping `tax_years: [2025]`; `jurisdiction: US-Federal` | Active **nonannual/revision-dated** product; official history is sparse (Dec. 2025, 2024, 2022, 2018, and earlier), so there is no annual cadence assumption; no discontinuation found. ([revisions](https://www.irs.gov/prior-year-forms-and-instructions?find=Publ+551&items_per_page=200&order=prior_year_products_picklist_revision_date&sort=desc)) | Common NCMEC/image exclusion; existing indexed source verified. Do not infer post-2025 inflation-adjusted thresholds from this edition. |
| `irs-p554-2025` | [Publication 554 (2025), Tax Guide for Seniors](https://www.irs.gov/pub/irs-prior/p554--2025.pdf) | Cover dated 2026-01-16; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. |
| `irs-p575-2025` | [Publication 575 (2025), Pension and Annuity Income](https://www.irs.gov/pub/irs-prior/p575--2025.pdf) | Cover dated 2025-11-06; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion; existing indexed source verified. |
| `irs-p721-2025` | [Publication 721 (2025), Tax Guide to U.S. Civil Service Retirement Benefits](https://www.irs.gov/pub/irs-prior/p721--2025.pdf) | Cover dated 2026-02-11; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. Links to OPM/SSA/TSP material are not imported under this source record. |
| `irs-p915-2025` | [Publication 915 (2025), Social Security and Equivalent Railroad Retirement Benefits](https://www.irs.gov/pub/irs-prior/p915--2025.pdf) | Cover dated 2025-11-18; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. The introduction says it was prepared jointly by IRS, SSA, and the U.S. Railroad Retirement Board; preserve that government provenance. |
| `irs-p925-2025` | [Publication 925 (2025), Passive Activity and At-Risk Rules](https://www.irs.gov/pub/irs-prior/p925--2025.pdf) | Cover dated 2026-02-23; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. |
| `irs-p936-2025` | [Publication 936 (2025), Home Mortgage Interest Deduction](https://www.irs.gov/pub/irs-prior/p936--2025.pdf) | Cover dated 2025-10-28; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. |
| `irs-p970-2025` | [Publication 970 (2025), Tax Benefits for Education](https://www.irs.gov/pub/irs-prior/p970--2025.pdf) | Cover dated 2026-01-27; “For use in preparing 2025 Returns”; `tax_years: [2025]`; `jurisdiction: US-Federal` | Active annual edition; no discontinuation found | Common NCMEC/image exclusion. The cover also previews a 2026 identification change; keep the source filter at 2025 and do not use that preview as 2026 corpus authority. |
| `irs-p1212-rev-2025-12` | [Publication 1212 (Rev. December 2025), Guide to Original Issue Discount (OID) Instruments](https://www.irs.gov/pub/irs-prior/p1212--2025.pdf) | Cover dated 2026-01-26; revision-dated; no “For use in preparing 2025 Returns” statement; approved corpus mapping `revision_date: 2025-12`, `tax_years: [2025]`, `jurisdiction: US-Federal` | Active **revision-dated** product; revision history is annual-like from 2018 through 2025 but gives no future cadence guarantee; companion OID tables are described as updated annually; no discontinuation found. ([revisions](https://www.irs.gov/prior-year-forms-and-instructions?find=1212&items_per_page=200&order=prior_year_products_picklist_revision_date&sort=desc)) | Core IRS-authored narrative is approved for indexing under the IRS policy after common NCMEC/photo, cover/decorative-art, seal, logo, and symbol exclusions. Do not crawl or index separately linked OID tables or issuer/financial-publication data under this record; the IRS says the data are generally unverified, and the 2025 table set remains incomplete. |

## Verification of already-indexed publications

The existing three source identities are internally consistent with the official PDFs:

| Existing source ID | Verification result |
| --- | --- |
| `irs-p523-2025` | Exact title, annual 2025 applicability, and canonical prior-year URL match the IRS PDF. |
| `irs-p551-rev-2025-12` | Exact cover title is “Publication 551 (Rev. December 2025), Basis of Assets”; the canonical prior-year URL is correct. The existing `[2025]` filter is reasonable for this 2025 corpus because the edition contains explicit 2025 rules, but the source remains revision-dated rather than an annual-return publication. |
| `irs-p575-2025` | Exact title, annual 2025 applicability, and canonical prior-year URL match the IRS PDF. |

This verification does not re-prove extraction correctness, content hashes, chunk anchors, retrieval quality, or candidate activation.

## Natural-language retrieval qrels

This matrix supplies one qrel for every requested publication. The three `verified existing` rows reproduce an already-indexed case from `qrels.tax.v1.json`; they should not be added a second time. The ten `proposed new` rows are candidates, not frozen evaluation assets. Every row uses filters `{"logical_kb": "tax_education", "tax_year": 2025, "jurisdiction": "US-Federal"}` and still requires human review for overlap, answer-bearing chunk coverage, and independence.

| Case ID | Natural-language query | Expected document ID | Status |
| --- | --- | --- | --- |
| `tax-2025-dependent-standard-deduction` | For my 2025 federal return, how do I know whether someone qualifies as my dependent, and how does being a dependent affect the standard deduction? | `irs-p501-2025` | Proposed new |
| `tax-2025-home-sale` | Can you explain tax related things to consider when selling a home? | `irs-p523-2025` | Verified existing |
| `tax-2025-taxable-nontaxable-income` | Under Publication 525 for 2025, which types of income are taxable or nontaxable? | `irs-p525-2025` | Proposed new; wording selected after fixed-qrel overlap review |
| `tax-2025-depreciable-property-disposition` | For 2025, how is gain from selling depreciable business property treated, including any depreciation recapture? | `irs-p544-2025` | Proposed new |
| `tax-2025-basis-of-assets` | Under Publication 551 revised December 2025, how is the cost or adjusted basis of stocks, bonds, and other assets determined? | `irs-p551-rev-2025-12` | Verified existing |
| `tax-2025-senior-filing-deductions` | I was age 65 at the end of 2025; what filing threshold and additional deductions apply to me? | `irs-p554-2025` | Proposed new |
| `tax-2025-pension-annuity-natural-language` | Can you explain tax considerations for pension and annuity income? | `irs-p575-2025` | Verified existing |
| `tax-2025-civil-service-annuity` | How do I determine the taxable and tax-free parts of my CSRS or FERS annuity for 2025? | `irs-p721-2025` | Proposed new |
| `tax-2025-social-security-taxability` | For a joint 2025 return, how do I determine whether any of our Social Security benefits are taxable? | `irs-p915-2025` | Proposed new |
| `tax-2025-at-risk-passive-order` | For 2025, which loss limitation applies first: the at-risk rules or the passive activity rules? | `irs-p925-2025` | Proposed new |
| `tax-2025-home-equity-interest` | Can I deduct interest from a home equity loan on my 2025 return, and what use-of-proceeds rule applies? | `irs-p936-2025` | Proposed new |
| `tax-2025-education-benefit-coordination` | For 2025, can I use the same tuition expense for an education credit and a tax-free 529 plan distribution? | `irs-p970-2025` | Proposed new |
| `tax-2025-oid-acquisition-premium` | I bought a long-term OID bond after its issue date at an acquisition premium; how should I adjust the OID I report on my 2025 federal return? | `irs-p1212-rev-2025-12` | Proposed new |

## Limitations and required follow-up

1. **Publication 1212 version semantics:** This review approves the IRS-authored narrative with a 2025 revision-year mapping, but the PDF does not explicitly say “For use in preparing 2025 Returns.” Preserve `revision_date: 2025-12` alongside `tax_years: [2025]`, do not reuse the edition for another year, and do not represent the mapping as proof that every evergreen rule began in 2025.
2. **Publication 551 scope beyond 2025:** The PDF has explicit 2025 content and supports the repository's existing 2025 filter, but it is a general revision-dated reference. This research does not establish that every substantive rule in it first applies, or applies only, in 2025. Do not expose it for other years without section-level effective-date review.
3. **Actual embedded NCMEC pages:** All 13 PDFs contain the warning that missing-child photographs may appear. This review verified the warning in extracted official PDF text but did not visually inspect every page of every PDF to enumerate actual photographs or captions. Extraction must therefore use a deny-by-default image/photo-page rule plus a rendered-page QA sample before approval.
4. **Formal product-status field:** Resolving PDFs and current IRS product pages provides no evidence of discontinuation, but this review did not obtain a machine-readable IRS item-status record proving “active” for every product. Recheck the current-product and prior-year catalogs during intake.
5. **Publication 1212 companion OID tables:** The tables were deliberately not reviewed as corpus sources because they are separate data, sourced from issuers and financial publications, and described by the IRS as generally unverified. The official table page currently lists only Sections I-C, II, and III-A and says remaining sections are forthcoming. They remain incomplete, out of scope, and may not inherit this PDF's approval.
6. **Future developments and corrections:** This is a point-in-time review. Intake must recheck each IRS Future Developments/current-product page and PDF hash immediately before candidate build.

## Official IRS evidence index

- Source-use authority: [Use of content from IRS.gov](https://www.irs.gov/about-irs/use-of-content-from-irsgov) and [IRM 1.17.8.6, Copyright and Copyrighted Material](https://www.irs.gov/irm/part1/irm_01-017-008#idm140092329605072).
- Version discovery: [Prior year forms and instructions](https://www.irs.gov/prior-year-forms-and-instructions).
- Current-revision status: official About pages for Publications [501](https://www.irs.gov/forms-pubs/about-publication-501), [523](https://www.irs.gov/forms-pubs/about-publication-523), [525](https://www.irs.gov/forms-pubs/about-publication-525), [544](https://www.irs.gov/forms-pubs/about-publication-544), [551](https://www.irs.gov/forms-pubs/about-publication-551), [554](https://www.irs.gov/forms-pubs/about-publication-554), [575](https://www.irs.gov/forms-pubs/about-publication-575), [721](https://www.irs.gov/forms-pubs/about-publication-721), [915](https://www.irs.gov/forms-pubs/about-publication-915), [925](https://www.irs.gov/forms-pubs/about-publication-925), [936](https://www.irs.gov/forms-pubs/about-publication-936), [970](https://www.irs.gov/forms-pubs/about-publication-970), and [1212](https://www.irs.gov/forms-pubs/about-publication-1212).
- Revision/cadence evidence: [Publication 551 revisions](https://www.irs.gov/prior-year-forms-and-instructions?find=Publ+551&items_per_page=200&order=prior_year_products_picklist_revision_date&sort=desc), [Publication 1212 revisions](https://www.irs.gov/prior-year-forms-and-instructions?find=1212&items_per_page=200&order=prior_year_products_picklist_revision_date&sort=desc), and [2025 OID table status](https://www.irs.gov/forms-pubs/original-issue-discount-oid-tables).
- Edition evidence: the 13 immutable official IRS PDFs linked in the edition matrix.

