# Funder rule packs

A **rule pack** is a declarative YAML file describing sourced rules and
metadata the engine can use to lint and scaffold a grant for one funder: its
sections and limits, formatting guidance (each with a citation), budget caps,
portal quirks, spelling locale, and review rubric. Some formatting guidance
requires generated-artifact or manual review rather than a Markdown check.
Packs live under `grantkit/data/funders/`; the stem
of the filename is the pack id (`nsf-pappg.yaml` → `nsf-pappg`).

## Packs that ship today

| Pack id | Funder | Notes |
|---------|--------|-------|
| `nsf-pappg` | National Science Foundation | PAPPG 24-1 machine-checkable content rules + merit-review rubric. |
| `nsf-pesose-26-506-track-2` | National Science Foundation | PESOSE Track 2; extends `nsf-pappg` with solicitation-specific sections, limits, attachments, and review criteria. |
| `nuffield-rda` | Nuffield Foundation | RDA full application; `en-GB`; plain-text portal. |
| `pbif` | Public Benefit Innovation Fund | Section list only; no limits are published. |

## Using a pack

`grantkit init --funder <id>` scaffolds from a pack. At runtime a grant is
matched to a pack by its `pack:` field, then by funder name.

## Schema

The full schema is documented in `grantkit/packs/schema.py`. Top-level keys:

| Key | Type | Notes |
|-----|------|-------|
| `id` | string, required | Matches the filename stem. |
| `name` | string, required | Funder name. |
| `extends` | string | Parent pack id. Mappings merge recursively; child scalars and lists replace inherited values. |
| `program` | string | Default program/solicitation. |
| `version` | string | Funder-guidance version (e.g. PAPPG `24-1`). |
| `source_url` | string | Canonical solicitation/policy URL. |
| `locale` | `en-US` \| `en-GB` | Spelling locale enforced by `check`. |
| `provenance` | string | How the pack's values were sourced. |
| `content_engine` | string \| null | A named programmatic content checker, such as `nsf_pappg` or `nsf_pesose_26_506_track_2`. |
| `sections` | list | `id`/`title`/`word_limit`/`char_limit`/`page_limit`/`required`/`description`/`file`. |
| `formatting_rules` | list | `id`/`description`/`severity`/`citation`/`url`/`quote`/`applies_to`. |
| `budget_rules` | mapping | `total_cap`/`annual_cap`/`indirect_rate_max`/`mtdc_excludes`/`currency`, plus an optional structured `preparation` contract. |
| `proposal_rules` | mapping | Proposal-wide `title_prefix`/`max_duration_months` constraints and their `citation`. |
| `attachment_groups` | list | File `glob` groups with `min_count`/`max_count`/`page_limit_each` and a `citation`. |
| `portal` | mapping | `accepts_markdown`/`plain_text_boxes`/`url`. |
| `review_rubric` | list | Assessment criteria for `grantkit review`. |

### Inheritance

Use `extends: <pack-id>` when a solicitation modifies a broader funder policy.
Mappings merge recursively. A value in the child wins; lists and scalars are
replaced, not appended. A program pack that supplies `sections` or
`review_rubric` must therefore include the complete program-specific list.
Inherited values are resolved and schema-validated when the pack is loaded.

`proposal_rules` enforce constraints on the proposal as a whole, currently a
required title prefix and maximum duration. `attachment_groups` enforce the
number of files matched by a project-relative glob and, for PDFs, an optional
per-file page limit. For example, the PESOSE Track 2 pack checks the exact
Track 2 title prefix, a 24-month maximum, and 3-5 collaboration letters of no
more than two pages each.

### PESOSE submission-readiness evidence

The PESOSE engine requires a `pesose.compliance` mapping in `grant.yaml`.
GrantKit derives prose and file facts itself where it can: actual letter files
and PDF page counts, the personnel table, DMSP fields, Senior/Key document
existence and Synergistic Activities page counts, and a declared Mentoring Plan
upload. It does not turn keyword matches into eligibility or substantive
compliance. Facts available only to the proposer or AOR must be explicit
attestations.

The mapping is organized into these evidence groups:

| Key | Evidence covered |
|-----|------------------|
| `proposal_submission_date` | Planned `YYYY-MM-DD` submission date used for the 12-month research-security-training window. If omitted or left blank, the proposal deadline is a warned fallback; an invalid nonblank date is an error. |
| `eligibility` | Proposer type, active UEI, lead/subaward structure, organization-specific eligibility, PI employment/residency/work authorization, funded-employee authorization, and conditional international-branch or federal/FFRDC routes. |
| `letters.manifest` | Three to five current independent third-party users/contributors, with writer, affiliation, relationship, contribution context, and declared page count reconciled to each actual PDF. |
| `letters.facilities_continuation` | Whether post-award continuation depends on facilities and, when it does, a separately modeled one- or two-page letter from the proposing organization or another provider. It may point to an existing third-party manifest entry; otherwise supply its own file, writer, affiliation, relationship, and page count. |
| `personnel` | A declared complete roster reconciled to the authoring table and every letter writer. The exact three-column table format is an NSF “should,” so deviations warn rather than hard-fail. |
| `senior_key` | Per-person SciENcv Biosketch and Current/Pending, COA, Synergistic Activities, MFTRP certification, research-security-training date, and actual file/page evidence. |
| `prior_nsf_support` | Applicability and manual review of every required Results from Prior NSF Support element. |
| `mentoring_plan` | Whether postdocs or graduate students receive support and, if so, one unified one-page upload. |
| `supplement_1` | Foreign-support records, AOR research-security/MFTRP certifications, conditional IHE RECR/Confucius rules, and conditional NSF-funded UAS procurement or operation. |
| `dmsp` | Up to four Research.gov product records and the publication-supporting-data timing/exception declarations. |
| `manual_review` | Four mandatory PESOSE content attestations and eight Track 2 review attestations: seven “should address” activity areas plus one Measure of Success; missing Track 2 review is a warning. |
| `award_conditions` | Manual review of the current federal person/entity-of-concern lists named by the NSF 26-506 VII.B TIP special award condition. GrantKit warns until reviewed but does not query or cache the dynamic lists. |
| `pappg_conditional_requirements_reviewed` | AOR review of conditional requirements GrantKit does not infer, including former-NSF negotiators, off-campus plans, human/animal research, DURC, historic places, and Tribal impacts. |

Place every declared letter PDF directly under `letters/`—the checker scans
`letters/*.pdf`, not nested directories—and key `letters.manifest` by the
project-relative path (for example, `letters/state-user.pdf`). A fresh PESOSE
scaffold includes copyable entry shapes plus `letters/README.md` and
`senior-key/README.md` with these file conventions.

Use the literal `not_applicable` only when the matching scope declaration makes
a field inapplicable. `false`, omission, and `not_applicable` are intentionally
different. Run `grantkit check` after adding the mapping; each finding names the
specific missing or contradictory declaration and cites its rule family.

### PESOSE budget-preparation evidence

The PESOSE Track 2 pack encodes NSF's [March 9, 2026 budget-preparation
update](https://www.nsf.gov/funding/opportunities/pesose-pathways-enable-secure-open-source-ecosystems/updates/120507)
under `budget_rules.preparation`. The pack owns the sourced values: the BLS
75th percentile, two-person-month, 10%, $50,000, and 15% thresholds; the
affected organization/payment types; and the Track 2 subaward rules. The
[August 12, 2026 I-Corps update](https://www.nsf.gov/funding/opportunities/pesose-pathways-enable-secure-open-source-ecosystems/updates/120938)
supplies manual-review context for the virtual format and expected maximum of
three training-team members.

For `grantkit check` to verify them, `budget.yaml` uses these evidence fields:

Every funded line must also provide `year_N` amounts (covering the applicable
years) or `funds_per_year`. Total-only sidecar fields such as `funding_amount`
do not participate in the legacy calculator's cap arithmetic and therefore
produce an error instead of a potentially false pass.

| Budget location | Evidence |
|-----------------|----------|
| top level | `years_in_budget` must be one or two. Declare a descriptive `organization_type`; it is not a closed eligibility list. `higher_education`, `state_government`, and `local_government` select the institutional salary route, while `nonprofit` and `for_profit` select the BLS route. Values such as Tribal Nation, Federal agency, or FFRDC remain valid declarations. |
| each `personnel.senior_key[]` and `personnel.other[]` item | Title/role, requested salary rate, responsibilities, per-year `calendar_months`, `total_requested_salary`, `employee_of_proposing_organization: true`, `calendar_months_reflect_requested_person_months: true`, and `budget_justification_includes_personnel_details: true`. An optional per-year `annual_salary_rate_by_year` enables arithmetic reconciliation of calendar months. Hourly calculations declare `salary_calculation_basis: hourly` and `hours_per_month: 173.33`; salary-based lines use `salary`. |
| cumulative NSF support for each Line A/B person | `cumulative_nsf_person_months` as a `year_N` mapping covering every budget year; and `over_two_months_justification` when any year exceeds two months. Omitting the mapping creates a manual-review warning. |
| existing IHE/state/local Line A/B person | `employment_status: existing`, `requested_rate_no_greater_than_current_attestation: true`, and `anticipated_institutional_escalation_rates`. GrantKit does not require disclosure of the person's numeric current salary. |
| new IHE/state/local Line A/B person | `employment_status: new`, `salary_rate_consistent_with_written_policy: true`, and `escalation_rates_consistent_with_written_policy: true`. |
| each nonprofit/for-profit Line A/B item | `soc_code`, `bls_url`, `requested_salary_rate` (or `base_salary`), `bls_percentile_rate`, `bls_benchmark_is_non_c_level: true`, `soc_responsibilities_match: true`, `work_location`, `bls_geographic_area`, and `bls_geography_matches_work_location: true`. An above-75th-percentile request also needs `above_bls_percentile_justification`. The non-C-level attestation describes the selected benchmark, not the person's job title. `grantkit check --urls` performs the network liveness test. |
| funded `fringe_benefits` | `rate`, `base`, `breakdown`, `salary_escalation_rates`, and `budget_justification_includes_fringe_details: true`. |
| each funded main-budget equipment item | `description`, `necessity`, and `budget_justification_includes_description_and_necessity: true`. |
| each funded trip | `description`, `necessity`, a non-empty structured `breakdown`, the applicable `cost_rule` (`48_cfr_31_205_46` for for-profits; `2_cfr_200_475` otherwise), and `budget_justification_includes_description_necessity_and_breakdown: true`. The Budget Justification response must contain a Markdown table, and `budget_justification_attestations.travel_breakdown_covers_each_trip` must be `true`. |
| materials and supplies over 10% of total budget | `budget_justification_attestations.materials_and_supplies_need_explained: true`. |
| every consultant | `time_commitment`, `consultant_rate`, `responsibilities`, `total_requested`, and `budget_justification_includes_consultant_details: true`. Above $50,000 for the award, also provide a readable project-relative PDF in `signed_statement.file` plus true attestations for `signed`, `confirms_availability`, `confirms_time_commitment`, `confirms_role`, and `confirms_rate`. |
| consultant, contractor, or subaward in `other_direct_costs[]` | `payee_is_owner_or_equity_holder: false`. |
| each Track 2 subaward in `other_direct_costs[]` | `purpose`, `key_tasks`, `requested_funding_amount`, `budget_justification_includes_subaward_details: true`; `subaward_pi_statement` attestations that the short PI statement is included in the Budget Justification, signed by the proposing institution's business office, confirms willingness, and describes responsibilities (a separate `file` is optional, but must be a readable project-relative PDF when supplied); a readable separate PDF of no more than five pages in `subaward_budget_justification.file` with main-format and line-letter/number attestations; `co_pi_listed_on_line_a: true` (manual review because NSF says “should”); description/necessity for any nested travel; a readable, executed project-relative PDF in `ip_rights_agreement.file`; and no non-empty equipment request. |
| Line G fee-for-service, subcontract, contractor, or other service | `services_description` and `budget_justification_includes_services_description: true`. |
| `indirect_costs` | `method: nicra` with `has_current_nicra: true`, `uses_negotiated_rate: true`, per-year `base_amount`, and `base_amount_verified_against_nicra: true`; or `method: de_minimis` with `has_current_nicra: false`, `rate: 0.15`, `base: mtdc`, per-year `base_amount`, and `base_amount_verified_as_mtdc: true`. The explicit base prevents the legacy calculator from silently omitting MTDC/NICRA exclusions. `method: none` with a zero rate records no indirect-cost request. |
| non-waived I-Corps budget | Requested costs use unique `id`, `icorps_amount`, and `icorps_cost_type`; their sum must equal `pesose.icorps_budget_amount` and cannot exceed $30,000. NSF states a maximum, not a positive minimum, so a zero request produces a manual-review warning. NSF also says the budget should include TL/EL salary support, so a missing positive salary-support line or `icorps_salary_support_is_sufficient: true` attestation is a warning rather than a compliance error. A requested TL/EL salary line attests `icorps_salary_rate_no_greater_than_current: true`. Also attest `icorps_budget_justification_includes_tagged_costs: true` and `icorps_training_format_acknowledged: virtual`. |
| non-waived I-Corps team | For planning, `icorps_team[]` can cover `technical_lead`, `entrepreneurial_lead`, and `industry_mentor`; named members can set `agreed_to_program_requirements: true`. Missing names, roles, or agreement attestations are manual-review warnings because NSF places designation and agreement in the post-award process, not proposal submission. More than three members is also a warning because the August expected maximum and March co-TL/co-EL language coexist. |
| I-Corps cost classification | The pack records NSF's example components (virtual tools, headsets/books, conference registration, domestic discovery travel, TL/EL salary, IM support, and fringe) and explicit prohibitions (interview gifts/certificates/meals/beverages, marketing/sales, survey tools, international travel, and conference booths). An unlisted type is a manual-review warning, not a closed-allowlist error. |

Document paths are checked for existence and cannot escape the grant directory.
Signature, execution, statement contents, employee status, salary-policy
compliance, current-rate comparisons, narrative inclusion, and ownership are
explicit attestations because GrantKit cannot establish those facts from the
budget arithmetic or narrative alone. Missing cumulative NSF-support data is a
manual-review warning; a declared over-threshold value without its required
explanation is an error. Financial values used in cap arithmetic must be finite
and non-negative.

## Contributing a pack

1. **Copy** an existing pack and rename it to `<funder>.yaml`.
2. **Only encode what you can source.** Leave a limit `null` if the funder does
   not publish one — never invent a number. Absence of a limit is *unknown*,
   not *unlimited*.
3. **Record provenance.** Add a `provenance:` field and inline comments citing
   where each value came from (URL, solicitation, or a reference application).
4. **Set the essentials:** `locale` and `portal.accepts_markdown` drive the
   spelling and plain-text checks.
5. **Cite formatting rules.** Every `formatting_rules` entry should carry a
   `citation` (and ideally a `url` and verbatim `quote`).
6. **Validate and test:**

   ```bash
   python -c "from grantkit.packs import load_pack; load_pack('your-pack')"
   ```

   `load_pack` validates against the schema and raises on any error. Add a case
   to `tests/test_packs.py` asserting your sourced values.

## Content engines

Most formatting rules are sourced pack guidance and cannot be verified from
Markdown (font size and margins are PDF-level). Builders and PDF validation
enforce or report the subset they can establish. A pack can opt into a
**content engine** — a named programmatic checker — via `content_engine`.
`nsf_pappg` runs the NSF-wide content checks; the
`nsf_pesose_26_506_track_2` engine adds Track 2 checks for summary keywords,
I-Corps waiver disclosure, personnel-list guidance, letters, eligibility,
supplementary documents, DMSP structure, and explicit human-review
attestations for substantive proposal coverage.
