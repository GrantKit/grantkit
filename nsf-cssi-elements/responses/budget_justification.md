---
key: budget_justification
status: draft
title: Budget Justification
---

# Budget Justification

**Total Request: $594,578 over 3 years**

## A. Senior Personnel ($101,250)

**Max Ghenis, PI ($45,000)**: 1.0 summer month per year for 3 years at $180,000 base salary. As PI, Ghenis will oversee project direction, coordinate partnerships with NBER and Atlanta Fed, manage deliverables and reporting, and ensure alignment with PolicyEngine's broader mission. Ghenis founded PolicyEngine and led the successful POSE Phase I proposal.

**Nikhil Woodruff, Co-PI ($56,250)**: 1.5 summer months per year for 3 years at $150,000 base salary. As Technical Lead, Woodruff will design the branch operator architecture, oversee validation infrastructure development, guide performance optimization strategy, and lead R/Stata wrapper design. Woodruff is PolicyEngine's CTO and architect of the current core engine, currently serving on secondment to UK Cabinet Office/HM Treasury.

## B. Other Personnel ($273,000)

**Research Software Engineer ($273,000)**: 0.65 FTE for 3 years at $140,000 base salary. This position is the primary development resource for the project. Responsibilities include:
- Implementing the branch operator in PolicyEngine Core
- Building continuous validation pipelines for TAXSIM and Atlanta Fed PRD
- Developing performance optimizations (parallelization, vectorization)
- **Creating R and Stata wrappers** to extend PolicyEngine access to researchers in those ecosystems
- Writing tests, documentation, and researcher onboarding materials
- Maintaining code quality, release management, and multi-language CI

The 0.65 FTE allocation reflects the core infrastructure scope, with expert consulting from Dan Feenberg providing specialized TAXSIM validation guidance.

## C. Fringe Benefits ($112,275)

Fringe benefits are calculated at 30% of total salaries ($374,250). This rate covers:
- Health insurance contributions
- Retirement plan contributions (401k match)
- Payroll taxes (FICA, unemployment insurance)
- Workers' compensation insurance

## D. Equipment ($0)

No equipment is requested. Development work uses existing personal computers and cloud-based infrastructure. High-performance computing needs are met through cloud services budgeted under Other Direct Costs.

## E. Travel ($18,000)

**NSF CSSI PI Meetings ($6,000)**: Annual PI meeting attendance in the DC area for PI and Co-PI. Budget assumes $1,000/person (discounted airfare, 2 nights lodging at federal per diem) for 2 people across 3 years.

**Research Conferences ($6,000)**: Presentation of validation results and research community engagement at NBER Summer Institute and AEA Annual Meeting. Budget allows for one conference attendance per year at $2,000 (registration, travel, lodging).

**R/Stata Community Engagement ($6,000)**: Presentation of R and Stata wrappers at useR! Conference and Stata Conference to drive adoption among quantitative researchers who primarily work in those ecosystems. $2,000/year for 3 years.

## F. Participant Support ($0)

No participant support is requested. This project focuses on infrastructure development rather than training programs or workshops requiring participant funding.

## G. Other Direct Costs ($36,000)

**Cloud Computing ($18,000)**: AWS/GCP resources for:
- Continuous validation pipeline (running TAXSIM comparisons on every PR)
- Performance benchmarking infrastructure
- Public accuracy dashboard hosting
- Multi-language CI testing (Python, R, Stata wrapper builds)
- Development and staging environments

Estimated at $6,000/year for 3 years.

**Software and Tools ($6,000)**: Development infrastructure including:
- GitHub Actions CI/CD (beyond free tier for compute-intensive validation and multi-language builds)
- Monitoring and alerting services
- Collaboration tools (Slack, documentation hosting)
- Code quality tools (static analysis, security scanning)

Estimated at $2,000/year for 3 years.

**Consultant - Dan Feenberg, NBER ($12,000)**: Expert consulting from Dr. Daniel Feenberg, creator and maintainer of TAXSIM since 1993. Dr. Feenberg will provide:
- Guidance on validation methodology and accuracy benchmarks
- Documentation of undocumented TAXSIM behaviors and edge cases
- Review of validation pipeline design and implementation
- Resolution of discrepancies between PolicyEngine and TAXSIM calculations

Estimated at 20 hours/year at $200/hour for 3 years. Dr. Feenberg's expertise is essential for ensuring PolicyEngine validation meets academic standards for tax microsimulation research.

## H. Indirect Costs ($54,053)

Indirect costs are calculated at the 10% de minimis rate applied to Modified Total Direct Costs (MTDC) of $540,525. PSL Foundation, serving as fiscal sponsor for PolicyEngine, uses the federal de minimis rate as it does not have a negotiated indirect cost rate agreement with a federal agency.

## Budget Summary by Year

| Category | Year 1 | Year 2 | Year 3 | Total |
|----------|--------|--------|--------|-------|
| Senior Personnel | $33,750 | $33,750 | $33,750 | $101,250 |
| Other Personnel | $91,000 | $91,000 | $91,000 | $273,000 |
| Fringe Benefits | $37,425 | $37,425 | $37,425 | $112,275 |
| Travel | $6,000 | $6,000 | $6,000 | $18,000 |
| Other Direct | $12,000 | $12,000 | $12,000 | $36,000 |
| Indirect | $18,018 | $18,018 | $18,017 | $54,053 |
| **Total** | **$198,193** | **$198,193** | **$198,192** | **$594,578** |
