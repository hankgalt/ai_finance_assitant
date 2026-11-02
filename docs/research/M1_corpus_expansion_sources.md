# M1 Finance and Tax Education corpus-expansion source research

Status: M1 maintenance source review; collection activation remains gated by extraction and retrieval evaluation  
Reviewed: 2026-10-31  
Scope: PR-007, PR-008; ADR-005, ADR-012, ADR-016, ADR-017

This note evaluates a bounded expansion of the Finance Education and Tax Education knowledge bases using only first-party source and rights statements. It is engineering research, not legal advice. The owning milestone remains [M1](../04_implementation_plan.md#m1--persistent-qdrant-and-offline-knowledge-ingestion). Any adopted source must still pass registry review, bounded acquisition, extraction review, change detection, candidate build, fixed-qrels retrieval evaluation, and explicit activation. Activation outcomes are recorded in the [M1 delivery report](../M1_delivery_report.md); the later 13-publication closure review is detailed separately in [M1_irs_publication_expansion_2025.md](M1_irs_publication_expansion_2025.md).

## Recommendation

Table dispositions use `approve`, `pending`, or `reject`. `Approve` means the source is recommended for per-edition SourceRegistry approval after the stated human review; it does not enable ingestion or activate a collection. `Pending` means keep `ingestion_enabled: false` until the named blocker is resolved.

- Keep all Bogleheads® Wiki candidates at `pending_review` with `ingestion_enabled: false`. The Wiki's [copyright page](https://www.bogleheads.org/wiki/Bogleheads:Copyrights) applies CC BY-SA 4.0 and expressly permits commercial sharing and adaptation, but its [general disclaimer](https://www.bogleheads.org/wiki/Bogleheads%C2%AE:General_disclaimer) says the site's materials are for information, education, and noncommercial purposes only. The repository should not decide the precedence or legal effect of those first-party statements. Obtain written clarification from the site/rightsholder or a qualified rights review before ingestion.
- Use individually reviewed SEC/Investor.gov pages for the active Finance Education expansion while the Bogleheads rights issue remains unresolved. Twelve first-party pages cover product selection, goals, diversification, risk tolerance, brokerage accounts, annuities, bonds, ETFs, index funds, money-market funds, mutual funds, and stocks without importing third-party community content.
- Even if that ambiguity is resolved, do not approve Bogleheads content until the product can propagate page/revision attribution, the CC BY-SA 4.0 license link, a modification notice, and any applicable ShareAlike notice to every redistributed excerpt or adaptation. The current `EvidenceReference` carries title, publisher, URL, and anchor, but no license, revision, modification, or output-license fields.
- Treat the IRS set as the preferred near-term Tax Education expansion. IRS-authored text is generally reusable, but each edition still needs review for third-party inclusions, exact tax-year metadata, credit, and non-endorsement. The original review prioritized 18 Tier A rows and required qrel justification for five Tier B rows. The subsequent explicit closure review approved Publications 525, 544, and 970 and added seven requested publications after source-specific review and fixed-qrel coverage; Forms 4952 and 8815 remain pending.
- Correct the Publication 505 rollover before the next refresh. The existing registry entry is `irs-p505-2025`, but its mutable current URL now serves Publication 505 (2026). Preserve the 2025 entry at the [immutable prior-year PDF](https://www.irs.gov/pub/irs-prior/p505--2025.pdf) and create a separate 2026 source. Never let a mutable current URL silently change the tax year attached to an existing source ID.

## Repository fit and registry conventions

The [requirements](../01_requirements_specification.md#61-logical-knowledge-bases) place supplementary permitted sources such as Bogleheads in Finance Education and prioritize IRS publications, forms, and official guidance for year-specific U.S. federal Tax Education. The [system design](../03_system_design.md#7-offline-knowledge-ingestion-and-activation) requires authority, canonical URL, use notes, logical KB, review cadence, jurisdiction, tax years, hashes, and status before fetch or embedding. Accepted ADR-012 treats all retrieved content as untrusted data; ADR-017 requires immutable candidate versions and explicit activation.

The current registry contract supports lowercase stable source IDs, `html` or `pdf`, one logical KB, explicit Tax years, status, permitted-use booleans/notes, reviewer/date, and an ingestion flag. Only `approved` sources may be enabled. Two gaps matter for this proposal:

1. `SourceDefinition` and the Qdrant payload do not preserve a source license identifier, attribution text, upstream revision ID/permalink, contributor-history URL, or a third-party-content review result.
2. `Evidence` and `EvidenceReference` do not carry license, upstream revision, change notice, or ShareAlike information to the response surface.

Those gaps do not block IRS attribution because the application already returns title, publisher, canonical URL, and anchor, and the repository can make credit a policy requirement. They do block a defensible claim that CC BY-SA output obligations are satisfied.

## SEC/Investor.gov Finance expansion

The active substitute set below was verified from the first-party [Investor.gov investment-products index](https://www.investor.gov/introduction-investing/investing-basics/investment-products) and [Save and Invest index](https://www.investor.gov/introduction-investing/investing-basics/save-and-invest) on 2026-10-31. The existing SEC permitted-use policy applies: attribute the SEC/Investor.gov page, exclude marks, logos, stock art, and linked third-party material, preserve staff-view/no-legal-force limitations where stated, and do not imply endorsement or individualized advice.

| Source ID | First-party page | Retrieval purpose |
| --- | --- | --- |
| `investor-investment-products` | [Investment Products](https://www.investor.gov/introduction-investing/investing-basics/investment-products) | Cross-product comparison factors |
| `investor-define-goals` | [Define Your Goals](https://www.investor.gov/introduction-investing/investing-basics/save-and-invest/define-your-goals) | Goals and time horizon |
| `investor-diversify-investments` | [Diversify Your Investments](https://www.investor.gov/introduction-investing/investing-basics/save-and-invest/diversify-your-investments) | Diversification and its limits |
| `investor-risk-tolerance` | [Gauge Your Risk Tolerance](https://www.investor.gov/introduction-investing/investing-basics/save-and-invest/gauge-your-risk-tolerance) | Risk-tolerance definition |
| `investor-brokerage-accounts` | [Brokerage Accounts](https://www.investor.gov/introduction-investing/investing-basics/investment-accounts/brokerage-accounts) | Cash and margin accounts |
| `investor-annuities` | [Annuities](https://www.investor.gov/introduction-investing/investing-basics/investment-products/annuities) | Annuity types, risks, and costs |
| `investor-bonds` | [Bonds — FAQs](https://www.investor.gov/introduction-investing/investing-basics/investment-products/bonds-or-fixed-income-products/bonds) | Bond mechanics and risks |
| `investor-etfs` | [Exchange-Traded Funds](https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-2) | ETF structure and trading |
| `investor-index-funds` | [Index Funds](https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-4) | Index-tracking concepts |
| `investor-money-market-funds` | [Money Market Funds](https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-5) | Short-term fund holdings and risks |
| `investor-mutual-funds` | [Mutual Funds](https://www.investor.gov/introduction-investing/investing-basics/investment-products/mutual-funds-and-exchange-traded-funds-etfs/mutual-funds) | Pooled-fund structure and NAV |
| `investor-stocks` | [Stocks — FAQs](https://www.investor.gov/introduction-investing/investing-basics/investment-products/stocks) | Equity ownership and risks |

## Bogleheads rights and revision findings

The first-party [Bogleheads copyrights page](https://www.bogleheads.org/wiki/Bogleheads:Copyrights) ([fixed revision 79574](https://www.bogleheads.org/w/index.php?title=Bogleheads:Copyrights&oldid=79574)) says the Wiki uses the [Creative Commons Attribution-ShareAlike 4.0 International license](https://creativecommons.org/licenses/by-sa/4.0/). That license permits sharing and adaptation, including commercially, subject to appropriate credit, a license link, indication of changes, ShareAlike for adapted material, no additional restrictions/effective technological measures, and no implied endorsement. The legal code also says trademark rights are not licensed and a licensor can grant only rights it has authority to grant.

The first-party [general disclaimer](https://www.bogleheads.org/wiki/Bogleheads%C2%AE:General_disclaimer) ([fixed revision 52884](https://www.bogleheads.org/w/index.php?title=Bogleheads%C2%AE:General_disclaimer&oldid=52884)), however, says site materials are for noncommercial purposes only, disclaims accuracy and individualized financial/tax advice, and identifies Bogleheads® as a registered service mark. This unresolved conflict is the primary rights blocker.

The site's [namespace page](https://www.bogleheads.org/wiki/Bogleheads:Namespace) and [main-namespace page](https://www.bogleheads.org/wiki/Bogleheads:Main_namespace) define namespace 0 as the knowledge-base article namespace. Candidate discovery should require `ns=0`, resolve redirects, and reject `Talk:`, `User:`, `Bogleheads:`, `File:`, `Template:`, `Help:`, `Category:`, `Special:`, forum, blog, policy, and service pages. The candidates below were verified through the first-party MediaWiki API as namespace 0, non-missing pages on 2026-10-31.

Wiki pages are mutable and collaboratively authored. Before any candidate build, capture the exact MediaWiki `oldid`, permanent revision URL, revision timestamp, contributor-history URL, canonical current URL, and normalized-content hash. Attribute the exact revision, not an undated current page. A changed `oldid` creates a new document version and candidate collection under ADR-017. [Help:Getting started](https://www.bogleheads.org/wiki/Help:Getting_started) specifically says page moves must preserve edit history because it is needed for copyright attribution.

Many articles contain quotations, images, tables, trademarks, linked material, or text imported from third parties. CC BY-SA covers only material the licensor has authority to license. The current generic HTML normalizer collects paragraph and list text, including reference lists and paragraphs nested in quotations; it is not sufficient for these pages. Approval requires a source-specific extraction profile or reviewed manifest that excludes block quotations, images/captions, reference and further-reading sections, embedded calculators/data, forum excerpts, and other separately credited material.

Use these restriction codes in the candidate table:

- **BH-1:** resolve the CC BY-SA/noncommercial-statement ambiguity in writing before approval.
- **BH-2:** record exact `oldid`, permanent revision link, revision timestamp, contributor history, canonical URL, and content hash.
- **BH-3:** surface reasonable attribution, CC BY-SA 4.0 link, and modification notice; apply ShareAlike to redistributed adapted material where required; impose no incompatible downstream restriction.
- **BH-4:** exclude or separately clear third-party quotations, images, tables/data, trademarks, reference-list text, forum excerpts, and linked material.
- **BH-5:** use Bogleheads® only for factual attribution; do not copy logos or imply affiliation, sponsorship, or endorsement.
- **BH-6:** preserve the educational/no-warranty posture; never route these pages into Tax Education or present them as authoritative tax rules, individualized advice, or guaranteed outcomes.

### Bogleheads main-namespace candidates

All 14 rows are Finance Education candidates and remain pending. Tier A is the smallest coherent principles set; Tier B is more product-specific or dependent on time-sensitive/section-level review. Revision IDs are evidence of the pages verified on 2026-10-31, not permission to skip a fresh pre-ingestion review. In this table, “Same” means the CC BY-SA 4.0 basis subject to the same unresolved first-party noncommercial statement shown in the first row.

| Logical KB | Suggested source ID | Title | Canonical URL | Tax year | Rights basis | Restrictions | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Finance Education | `bogleheads-investment-philosophy` | Bogleheads® investment philosophy | [Source](https://www.bogleheads.org/wiki/Bogleheads%C2%AE_investment_philosophy) | n/a | CC BY-SA 4.0, subject to unresolved first-party noncommercial statement | BH-1–BH-6; oldid 93090 | Pending; Tier A overview after all BH gates |
| Finance Education | `bogleheads-importance-saving-early` | Importance of saving early | [Source](https://www.bogleheads.org/wiki/Importance_of_saving_early) | n/a | Same | BH-1–BH-6; oldid 93088 | Pending; Tier A compounding/saving concepts, no return guarantee |
| Finance Education | `bogleheads-risk-tolerance` | Risk tolerance | [Source](https://www.bogleheads.org/wiki/Risk_tolerance) | n/a | Same | BH-1–BH-6; oldid 93082 | Pending; Tier A, no personalized suitability inference |
| Finance Education | `bogleheads-risk-and-return` | Risk and return | [Source](https://www.bogleheads.org/wiki/Risk_and_return) | n/a | Same | BH-1–BH-6; oldid 92410 | Pending; Tier A general education, preserve uncertainty |
| Finance Education | `bogleheads-asset-allocation` | Asset allocation | [Source](https://www.bogleheads.org/wiki/Asset_allocation) | n/a | Same | BH-1–BH-6; oldid 92803 | Pending; Tier A, no personalized allocation recommendation |
| Finance Education | `bogleheads-index-fund` | Index fund | [Source](https://www.bogleheads.org/wiki/Index_fund) | n/a | Same | BH-1–BH-6; oldid 93087 | Pending; Tier A, exclude mutable provider/fee examples unless separately reviewed |
| Finance Education | `bogleheads-mutual-fund` | Mutual fund | [Source](https://www.bogleheads.org/wiki/Mutual_fund) | n/a | Same | BH-1–BH-6; oldid 93084 | Pending; Tier A product concept; deduplicate against SEC content |
| Finance Education | `bogleheads-exchange-traded-fund` | Exchange-traded fund | [Source](https://www.bogleheads.org/wiki/Exchange-traded_fund) | n/a | Same | BH-1–BH-6; oldid 92343 | Pending; Tier A product concept; deduplicate against SEC content |
| Finance Education | `bogleheads-mutual-funds-fees` | Mutual funds and fees | [Source](https://www.bogleheads.org/wiki/Mutual_funds_and_fees) | n/a | Same | BH-1–BH-6; oldid 93279 | Pending; Tier A concepts only; exclude mutable fund-specific figures |
| Finance Education | `bogleheads-investment-policy-statement` | Investment policy statement | [Source](https://www.bogleheads.org/wiki/Investment_policy_statement) | n/a | Same | BH-1–BH-6; oldid 93085 | Pending; Tier A, exclude quoted examples and external/forum material |
| Finance Education | `bogleheads-rebalancing` | Rebalancing | [Source](https://www.bogleheads.org/wiki/Rebalancing) | n/a | Same | BH-1–BH-6; oldid 92513 | Pending; Tier A concept/examples, not a trade instruction |
| Finance Education | `bogleheads-behavioral-pitfalls` | Behavioral pitfalls | [Source](https://www.bogleheads.org/wiki/Behavioral_pitfalls) | n/a | Same | BH-1–BH-6; oldid 93091 | Pending; Tier A after removing book quotations and third-party excerpts |
| Finance Education | `bogleheads-lazy-portfolios` | Lazy portfolios | [Source](https://www.bogleheads.org/wiki/Lazy_portfolios) | n/a | Same | BH-1–BH-6; oldid 92158 | Pending; Tier B, exclude named portfolio/provider performance material |
| Finance Education | `bogleheads-three-fund-portfolio` | Three-fund portfolio | [Source](https://www.bogleheads.org/wiki/Three-fund_portfolio) | n/a | Same | BH-1–BH-6; oldid 93079 | Pending; Tier B, exclude tickers/provider tables and avoid personal advice |

`Diversification` is not proposed because the first-party page currently carries a disputed-neutrality banner and is short. `Tax-efficient fund placement` is also excluded from this Finance set: it contains change-sensitive U.S. tax claims and should not become Tax Education evidence without a separate year-specific authoritative-source review.

Suggested attribution, if the rights blocker is cleared: “*Title*, Bogleheads Wiki contributors, revision *oldid*, CC BY-SA 4.0; excerpted/chunked for retrieval; changes indicated,” with links to the permanent revision, history, and license.

## IRS reuse and versioning findings

The IRS [Use of content from IRS.gov](https://www.irs.gov/about-irs/use-of-content-from-irsgov) page says content created or maintained by federal employees in their duties is not copyrighted and may be freely copied; it requests credit. It also says copyrighted material appearing on or reached through the site requires consulting the copyright holder. [IRM 1.17.8.6](https://www.irs.gov/irm/part1/irm_01-017-008#idm140092329605072) confirms that official-duty government publications without copyrighted inclusions are not subject to copyright and describes permission/notice requirements for included copyrighted material. The same public content policy prohibits use of Treasury/IRS names, seals, symbols, or imitations in a way that could imply approval, endorsement, sponsorship, authorization, or association.

The repository should treat credit as required policy even though the IRS asks rather than imposes it: publisher, exact title/edition, canonical or immutable URL, source anchor/page, and tax year should remain visible. Do not copy seals, logos, decorative art, or photographs. Review each edition for third-party material; for example, Publication 571 says missing-child photographs selected by the National Center for Missing & Exploited Children may appear on otherwise blank pages.

Current `/publications/p...`, `/instructions/i...`, and `/pub/irs-pdf/...` URLs are mutable. IRS provides [current-product search](https://www.irs.gov/forms-instructions) and [prior-year search](https://www.irs.gov/forms-pubs/prior-year). During intake, record the edition printed inside the document. When IRS rolls the current URL to another year, preserve the prior source at the immutable `/pub/irs-prior/<product>--<year>.pdf` URL, create a new source ID for the new edition, and rebuild/evaluate a candidate rather than changing an active document's tax-year meaning in place. Monitor each product's future-developments/corrections page in addition to monthly hash checks.

Use these restriction codes in the table:

- **IRS-1:** credit the IRS and preserve exact product title/number, edition/revision, tax year(s), jurisdiction, canonical/immutable URL, page/section anchor, and content hash.
- **IRS-2:** review each edition and exclude seals, logos, photographs, decorative art, and any third-party copyrighted inclusion or linked material not separately cleared.
- **IRS-3:** factual attribution only; do not imply Treasury/IRS approval, sponsorship, endorsement, authorization, or association.
- **IRS-4:** pin annual/revised content by edition; on rollover, move the older edition to its immutable prior-year PDF and create a new source/version. Do not infer applicability to an unlisted year.
- **IRS-5:** retain the publication's limits: educational guidance is not every situation and does not replace controlling law; monitor future developments, corrections, and legislation.

### IRS publication and form-instruction candidates

The table contains 30 candidates: the original 23-source review plus seven publications added by the explicit closure review. “Existing” means the source ID is already in `source-registry.v1.json`; it is not a new approval. In this table, “Same” means the IRS employee-created official-work basis shown in the first row: freely copy, with credit requested, subject to per-edition third-party-content review.

| Logical KB | Suggested source ID | Title | Canonical URL | Tax year | Rights basis | Restrictions | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tax Education | `irs-p17-2025` | Publication 17 (2025), Your Federal Income Tax | [Source](https://www.irs.gov/publications/p17) | 2025 | IRS employee-created official work; freely copy; credit requested | IRS-1–IRS-5 | `approve` — Tier A; retain existing source, then pin its prior PDF when the current page rolls |
| Tax Education | `irs-p501-2025` | Publication 501 (2025), Dependents, Standard Deduction, and Filing Information | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p501--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — closure review; dependent, filing-requirement, and standard-deduction qrel |
| Tax Education | `irs-p505-2026` | Publication 505 (2026), Tax Withholding and Estimated Tax | [Source](https://www.irs.gov/publications/p505) | 2026 | Same | IRS-1–IRS-5 | `approve` — Tier A; add separately and repoint existing 2025 ID to [2025 prior PDF](https://www.irs.gov/pub/irs-prior/p505--2025.pdf) |
| Tax Education | `irs-p550-2025` | Publication 550 (2025), Investment Income and Expenses | [Source](https://www.irs.gov/publications/p550) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; retain existing primary investment-tax source |
| Tax Education | `irs-p560-2025` | Publication 560 (2025), Retirement Plans for Small Business | [Source](https://www.irs.gov/publications/p560) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; retain existing SEP/small-business retirement source |
| Tax Education | `irs-p590a-2025` | Publication 590-A (2025), Contributions to Individual Retirement Arrangements (IRAs) | [Source](https://www.irs.gov/publications/p590a) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; retain existing IRA-contribution source |
| Tax Education | `irs-p590b-2025` | Publication 590-B (2025), Distributions from Individual Retirement Arrangements (IRAs) | [Source](https://www.irs.gov/publications/p590b) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; retain existing IRA-distribution source |
| Tax Education | `irs-p514-2025` | Publication 514 (2025), Foreign Tax Credit for Individuals | [Source](https://www.irs.gov/publications/p514) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add for foreign-tax credit on dividends and investment income |
| Tax Education | `irs-p523-2025` | Publication 523 (2025), Selling Your Home | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p523--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; fixed home-sale qrel exposed a direct-source gap when Publication 17 referred users to Publication 523 without supplying it as evidence |
| Tax Education | `irs-p551-rev-2025-12` | Publication 551 (12/2025), Basis of Assets | [Source](https://www.irs.gov/publications/p551) | 2025 edition; applicability review required | Same | IRS-1–IRS-5 | `approve` — Tier A after human mapping of revision date to supported tax-year filters |
| Tax Education | `irs-p554-2025` | Publication 554 (2025), Tax Guide for Seniors | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p554--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — closure review; senior filing and additional-deduction qrel |
| Tax Education | `irs-p571-rev-2026-01` | Publication 571 (Rev. January 2026), Tax-Sheltered Annuity Plans (403(b) Plans) | [Source](https://www.irs.gov/publications/p571) | 2025, 2026 | Same | IRS-1–IRS-5; explicitly exclude third-party photographs | `approve` — Tier A; add for 403(b) education with both applicability years recorded |
| Tax Education | `irs-p575-2025` | Publication 575 (2025), Pension and Annuity Income | [Source](https://www.irs.gov/publications/p575) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add for qualified-plan and annuity distributions |
| Tax Education | `irs-p721-2025` | Publication 721 (2025), Tax Guide to U.S. Civil Service Retirement Benefits | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p721--2025.pdf) | 2025 | Same | IRS-1–IRS-5; linked OPM/SSA/TSP content requires separate intake | `approve` — closure review; CSRS/FERS annuity qrel |
| Tax Education | `irs-p915-2025` | Publication 915 (2025), Social Security and Equivalent Railroad Retirement Benefits | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p915--2025.pdf) | 2025 | Joint IRS/SSA/RRB government provenance | IRS-1–IRS-5 | `approve` — closure review; Social Security taxability qrel |
| Tax Education | `irs-p925-2025` | Publication 925 (2025), Passive Activity and At-Risk Rules | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p925--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — closure review; loss-limitation ordering qrel |
| Tax Education | `irs-p936-2025` | Publication 936 (2025), Home Mortgage Interest Deduction | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p936--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — closure review; home-equity interest qrel |
| Tax Education | `irs-i1040sb-2025` | Instructions for Schedule B (Form 1040) (2025), Interest and Ordinary Dividends | [Source](https://www.irs.gov/instructions/i1040sb) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add exact interest/dividend reporting terminology |
| Tax Education | `irs-i1040sd-2025` | Instructions for Schedule D (Form 1040) (2025), Capital Gains and Losses | [Source](https://www.irs.gov/instructions/i1040sd) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add capital-gain/loss reporting and carryover context |
| Tax Education | `irs-i8949-2025` | Instructions for Form 8949 (2025), Sales and Other Dispositions of Capital Assets | [Source](https://www.irs.gov/instructions/i8949) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add transaction reconciliation and basis-adjustment codes |
| Tax Education | `irs-i8606-2025` | Instructions for Form 8606 (2025), Nondeductible IRAs | [Source](https://www.irs.gov/instructions/i8606) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add basis, nondeductible contributions, conversions, and distributions |
| Tax Education | `irs-i5329-2025` | Instructions for Form 5329 (2025), Additional Taxes on Qualified Plans (Including IRAs) and Other Tax-Favored Accounts | [Source](https://www.irs.gov/instructions/i5329) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add early-distribution and excess-contribution education |
| Tax Education | `irs-i1116-2025` | Instructions for Form 1116 (2025), Foreign Tax Credit (Individual, Estate, or Trust) | [Source](https://www.irs.gov/instructions/i1116) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; pair with Publication 514 for qualified-dividend/capital-gain adjustments |
| Tax Education | `irs-i8960-2025` | Instructions for Form 8960 (2025), Net Investment Income Tax—Individuals, Estates, and Trusts | [Source](https://www.irs.gov/instructions/i8960) | 2025 | Same | IRS-1–IRS-5 | `approve` — Tier A; add NIIT definitions and investment-income interactions |
| Tax Education | `irs-p525-2025` | Publication 525 (2025), Taxable and Nontaxable Income | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p525--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — closure review resolved the Tier B gap with an exact publication qrel |
| Tax Education | `irs-p544-2025` | Publication 544 (2025), Sales and Other Dispositions of Assets | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p544--2025.pdf) | 2025 | Same | IRS-1–IRS-5 | `approve` — closure review adds depreciable-property disposition coverage distinct from P550/Schedule D/8949 |
| Tax Education | `irs-p970-2025` | Publication 970 (2025), Tax Benefits for Education | [Immutable 2025 PDF](https://www.irs.gov/pub/irs-prior/p970--2025.pdf) | 2025 | Same | IRS-1–IRS-5; 2026 preview language is not 2026 corpus authority | `approve` — closure review; education-benefit coordination qrel |
| Tax Education | `irs-p1212-rev-2025-12` | Publication 1212 (Rev. December 2025), Guide to Original Issue Discount (OID) Instruments | [Immutable December 2025 PDF](https://www.irs.gov/pub/irs-prior/p1212--2025.pdf) | Revision mapped to 2025 after human applicability review | Same | IRS-1–IRS-5; exclude separate issuer/financial-publication OID tables | `approve` — closure review; acquisition-premium qrel covers only the IRS-authored narrative |
| Tax Education | `irs-f4952-2025` | Form 4952 (2025), Investment Interest Expense Deduction, with instructions | [Source](https://www.irs.gov/pub/irs-pdf/f4952.pdf) | 2025 | Same | IRS-1–IRS-5 | `pending` — Tier B; narrow and substantially covered by P550; add only for exact-form qrels |
| Tax Education | `irs-f8815-2025` | Form 8815 (2025), Exclusion of Interest From Series EE and I U.S. Savings Bonds Issued After 1989, with instructions | [Source](https://www.irs.gov/pub/irs-pdf/f8815.pdf) | 2025 | Same | IRS-1–IRS-5 | `pending` — Tier B; narrow and covered by P550/P970; add only for savings-bond qrels |

Not selected for this slice: rental-real-estate, business-return, estate-return, HSA, and payer-side information-return instructions. Some are legitimate future Tax Education sources, but adding them now would broaden the product or duplicate selected publications without a fixed retrieval need.

## Intake and evaluation plan

1. Resolve the Bogleheads rights ambiguity and design license-aware attribution/output handling before changing any Bogleheads registry status. If clarification is not obtained, keep the candidates pending and build the Finance expansion from permitted government or independently authored sources instead.
2. Add IRS sources in a new registry review. First fix the P505 2025 mutable-URL mismatch. Record the exact edition found inside every document, not the year inferred from the URL or fetch date.
3. Preflight the repository's bounded fetcher. A failed or blocked fetch is quarantined; do not bypass access controls. For Bogleheads, capture revision-specific URLs on the same reviewed host and confirm that the allowed fetch path does not redirect to an unreviewed host.
4. Add extraction fixtures before corpus work. Bogleheads fixtures must prove removal of quotations, references, forum/blog content, media, and mutable provider/tax data. IRS fixtures must prove title/edition/year extraction, page anchors, and removal of artwork/blank-photo pages where present.
5. Run duplicate/overlap analysis against the six active SEC Finance documents and nine active IRS Tax documents. Prefer section-level exclusion over padding the corpus with repeated explanations.
6. Extend fixed qrels before activation: Finance principles/risk/allocation/cost/rebalancing/behavior cases; Tax interest/dividends, basis, capital dispositions, foreign tax, retirement contributions/distributions, penalties, NIIT, exact form numbers, and explicit 2025/2026/historical filters.
7. Build immutable candidate collections, compare dense/sparse/hybrid retrieval against the active baseline, review citation integrity and source mix, then activate only if all M1 gates pass. Keep the prior collection for rollback.

## Primary-source evidence index

- Bogleheads: [Copyrights](https://www.bogleheads.org/wiki/Bogleheads:Copyrights), [General disclaimer](https://www.bogleheads.org/wiki/Bogleheads%C2%AE:General_disclaimer), [Namespace](https://www.bogleheads.org/wiki/Bogleheads:Namespace), [Main namespace](https://www.bogleheads.org/wiki/Bogleheads:Main_namespace), [Help:Getting started](https://www.bogleheads.org/wiki/Help:Getting_started), and the 14 linked main-namespace candidates above.
- License terms: [CC BY-SA 4.0 deed](https://creativecommons.org/licenses/by-sa/4.0/) and [legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en).
- IRS: [Use of content from IRS.gov](https://www.irs.gov/about-irs/use-of-content-from-irsgov), [IRM 1.17.8.6](https://www.irs.gov/irm/part1/irm_01-017-008#idm140092329605072), [current forms/instructions/publications](https://www.irs.gov/forms-instructions), [prior-year products](https://www.irs.gov/forms-pubs/prior-year), and the 23 linked candidate documents above.
- Repository authority: [requirements §6](../01_requirements_specification.md#6-knowledge-requirements), [system design §7](../03_system_design.md#7-offline-knowledge-ingestion-and-activation), [M1 plan](../04_implementation_plan.md#m1--persistent-qdrant-and-offline-knowledge-ingestion), [M1 source-use research](M1_qdrant_models_sources.md), and [M1 delivery report](../M1_delivery_report.md).




