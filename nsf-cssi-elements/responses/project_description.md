---
key: project_description
status: draft
title: Project Description
---

# Project Description

## 1. The Research Infrastructure Gap

### 1.1 The Need for Joint Tax-Benefit Modeling

Modern welfare states operate through two interacting systems: taxes that reduce disposable income and benefits that increase it. A single mother earning $25,000 might receive SNAP benefits, qualify for Medicaid, claim the EITC and CTC, and owe payroll taxes—all simultaneously. Whether she should work additional hours depends on how all these programs interact: the EITC phase-in increases incentives, but SNAP benefit reduction and potential Medicaid loss ("the cliff") decrease them.

Yet research infrastructure developed separately for taxes and benefits:

**Tax-focused infrastructure** (TAXSIM, tax microsimulation models) calculates income tax liabilities but ignores benefit programs. Decades of tax incidence research using these tools cannot capture how SNAP phase-outs or Medicaid eligibility affect the conclusions.

**Benefit-focused infrastructure** (TRIM3, state eligibility models) models benefit programs but typically ignores or simplifies tax treatment. Research on benefit adequacy or take-up rates misses tax interactions.

This fragmentation is not just inconvenient—it produces biased research. Studies of effective marginal tax rates that ignore benefits understate work disincentives for low-income households. Studies of benefit adequacy that ignore tax credits understate total support. Research on poverty measurement, labor supply, and optimal policy design all suffer when taxes and benefits are modeled separately.

### 1.2 Limitations of Existing Infrastructure

**NBER TAXSIM**: Created by Daniel Feenberg in 1993, TAXSIM has enabled foundational tax research with over 1,000 academic citations. Researchers submit household characteristics and receive calculated tax liabilities. But TAXSIM has fundamental limitations for next-generation research:

- *Taxes only*: No SNAP, Medicaid, TANF, SSI, or other benefit programs
- *Current law only*: Cannot model hypothetical reforms—only actual law for historical years
- *Closed source*: Researchers cannot inspect calculations or verify edge case handling
- *Individual records*: No integrated microsimulation on population samples
- *Legacy interface*: Web forms and batch files; no modern API

**TRIM3** (Transfer Income Model): The Urban Institute's microsimulation model includes both taxes and benefits but:

- *Not publicly available*: Analysis only through commissioned reports; model itself not accessible
- *No independent research*: Researchers cannot run their own analyses or test hypotheses
- *Not reproducible*: Proprietary code cannot be inspected or cited
- *No reform modeling*: Custom analysis requires contracting with Urban Institute

Similar limitations apply to other Urban Institute models (ATTIS for health, DynaSim for Social Security, HIPSM for health insurance)

**CBO and JCT Models**: Congressional budget offices have sophisticated internal models, but:

- *Not public*: Methodology papers exist but code does not
- *Institutional use only*: Not available for academic research
- *Current law focus*: Reform analysis is internal, not reproducible

**State-specific tools** exist for individual programs (SNAP calculators, Medicaid eligibility screeners) but are not research infrastructure—they lack reform capability, population-scale analysis, or integration with other programs.

### 1.3 Research Questions Requiring Integrated Infrastructure

Consider what becomes possible—and what currently cannot be done—with infrastructure modeling the joint tax-benefit system:

**Effective Marginal Tax Rate Research**: What is the true marginal tax rate facing households at different income levels? This requires summing income tax rates, payroll tax rates, SNAP benefit reduction rates, EITC phase-out rates, and potential Medicaid loss. Current estimates either ignore benefits (understating low-income rates) or use ad hoc combinations of separate models.

**Tax-Benefit Interaction Studies**: Decades of labor supply research estimates responses to income tax changes. But households respond to the full tax-benefit schedule. A study of EITC labor supply effects that ignores SNAP interactions may misattribute responses. Research on benefit cliffs requires modeling the full system.

**Optimal Policy Design**: What combination of tax rates, credit parameters, and benefit levels minimizes poverty while maintaining work incentives? This is a constrained optimization problem over a high-dimensional parameter space—intractable without integrated microsimulation that can evaluate thousands of policy combinations.

**State Policy Natural Experiments**: The 50 states offer natural experiments in policy design. But research comparing state policies must model both state taxes (which vary) and state benefit administration (which also varies). No existing tool enables this.

**Distributional Analysis of Reform Packages**: Real policy proposals bundle tax and benefit changes. The Inflation Reduction Act combined energy tax credits with ACA subsidy extensions. Comprehensive analysis requires modeling both.

**Poverty Measurement**: The Supplemental Poverty Measure includes taxes and benefits in resources. Proper SPM analysis requires calculating both accurately—currently requiring multiple tools with inconsistent assumptions.

---

## 2. PolicyEngine: Integrated Tax-Benefit Infrastructure

### 2.1 Technical Architecture

PolicyEngine is open-source infrastructure built on three core components:

**Rules Engine (policyengine-core)**: A declarative policy specification language where tax and benefit rules are encoded as Python functions with embedded metadata. Variables specify their calculation logic, dependencies, and time periods. Parameters store policy values (tax rates, benefit amounts, thresholds) with temporal variation as law changes. The engine automatically resolves dependencies and calculates any variable for any time period.

**Policy Models (policyengine-us, policyengine-uk, etc.)**: Country-specific implementations encoding actual law. PolicyEngine-US includes:

- Federal income taxes: All IRC provisions affecting individual filers
- State income taxes: Complete models for all 50 states plus DC
- Payroll taxes: Social Security, Medicare, unemployment insurance
- Federal benefits: SNAP, Medicaid, TANF, SSI, WIC, CHIP, Section 8, LIHEAP, Lifeline, school meals, CCDF
- Tax credits: EITC, CTC, CDCTC, AOTC, LLC, energy credits, state equivalents
- State benefit variations: State supplements to federal programs

Every calculation traces to authoritative sources through 1,800+ structured citations to the U.S. Code, Code of Federal Regulations, and state statutes embedded directly in the codebase.

**Data Infrastructure (policyengine-us-data)**: Enhanced microdata for population-scale analysis. We calibrate the Current Population Survey to administrative totals, impute missing variables (using our MicroImpute library for wealth, consumption, and detailed income components), and construct sample weights reproducing known population distributions. The result is research-ready microdata for 150+ million U.S. tax units.

### 2.2 Reform Modeling Capability

Unlike current-law-only tools, PolicyEngine enables hypothetical reform analysis. Users specify parameter changes:

```python
from policyengine_us import Simulation

# Model CTC expansion to $3,600 with full refundability
reform = {
    "gov.irs.credits.ctc.amount.base[0].amount": 3600,
    "gov.irs.credits.ctc.refundable.fully_refundable": True
}

simulation = Simulation(
    situation=household,
    reform=Reform.from_dict(reform)
)
```

This enables:
- Policy design: Test parameter combinations to achieve objectives
- Comparative analysis: Compare reform alternatives
- Sensitivity analysis: How do outcomes change with parameter values?
- Budget scoring: Estimate fiscal costs of proposals

### 2.3 Demonstrated Adoption

**Government Users**:
- Joint Economic Committee uses PolicyEngine for federal tax proposal analysis
- UK Cabinet Office has integrated PolicyEngine UK; our CTO serves on secondment to HM Treasury
- New York State Senator Andrew Gounardes credited PolicyEngine for enabling independent child tax credit legislation design
- Congressional briefings at CBO, Congressional Research Service, Joint Economic Committee

**Research Users**:
- USC Center for Economic and Social Research: HHS-funded marginal tax rate research
- Curriculum discussions at Berkeley, Georgetown, Northwestern, Harvard
- Research collaborations with Atlanta Fed Policy Rules Database team

**Public Benefit**:
- MyFriendBen (Gates Foundation, $2.4M): $800M+ in unclaimed benefits identified in Colorado
- Amplifi's Benefit Navigator: $185M in benefits accessed for 17,000 California households
- Additional partners: Student Basic Needs Coalition, Mirza, Starlight
- Combined reach: 100,000+ individuals annually, $1B+ in benefits identified

**Technical Scale**:
- 146 GitHub repositories across the ecosystem
- 50,000+ commits, 30+ unique contributors, 620+ forks
- 9,034 encoded parameters and variables
- NSF POSE Phase I award (#2229069)

### 2.4 Validation Infrastructure

**TAXSIM Validation**: We maintain a formal MOU with NBER. Dan Feenberg—TAXSIM's creator—serves as technical advisor and I-Corps mentor. We compare PolicyEngine tax calculations against TAXSIM for federal and state income taxes, resolving discrepancies through code review or discussions with Feenberg.

**Atlanta Fed Policy Rules Database**: The PRD documents benefit program parameters across all states. We compare encoded parameters against PRD documentation, with an established feedback loop for corrections.

**IRS Statistics of Income**: We validate aggregate tax outcomes against published SOI tables.

**Administrative Benchmarks**: We compare benefit enrollment and payment totals against agency data (FNS for SNAP, CMS for Medicaid).

---

## 3. Infrastructure Gaps Requiring NSF Investment

Despite demonstrated adoption, PolicyEngine's infrastructure requires modernization to serve as foundational research cyberinfrastructure.

### 3.1 Continuous Validation Infrastructure

**Current State**: Validation against TAXSIM and PRD occurs through periodic manual comparison. When discrepancies are found, they are investigated and resolved.

**Problem**: This process is:
- *Reactive*: Issues discovered after release
- *Incomplete*: Validation covers a subset of scenarios
- *Unsustainable*: Manual effort doesn't scale with model complexity
- *Opaque*: No public accuracy metrics

**What's Needed**: Automated validation infrastructure that:
- Compares every code change against TAXSIM and PRD
- Identifies regressions before release
- Tracks accuracy metrics over time
- Provides public dashboards showing validation status

**Why NSF**: Building validation infrastructure is classic cyberinfrastructure work—essential for research quality but not fundable through application-specific grants.

### 3.2 Performance for Population-Scale Research

**Current State**: PolicyEngine performs well for household-level calculations (sub-second) and moderate-scale microsimulation (100,000 households in minutes). But population-scale analysis—150+ million U.S. tax units—requires hours of computation.

**Problem**: This limits:
- Real-time policy optimization (requires thousands of evaluations)
- Monte Carlo uncertainty quantification
- Interactive research workflows
- Large-scale behavioral microsimulation

**What's Needed**: Performance improvements through:
- Vectorization replacing Python conditionals
- Parallelization across CPU cores
- Memory optimization for large datasets
- Optional distributed computing backend

**Research Enabled**: Policy parameter optimization. Uncertainty quantification with proper confidence intervals. Behavioral microsimulation with heterogeneous responses.

### 3.3 R and Stata Interfaces

**Current State**: PolicyEngine is Python-native. Using it from R or Stata requires custom wrappers or API calls.

**Problem**: Economists predominantly work in R and Stata. Python-only access creates adoption barriers, particularly for:
- Researchers with existing Stata/R workflows
- Graduate students trained in these environments
- Replication of studies originally in Stata/R

**What's Needed**: Native packages for both environments:
- R package installable from CRAN with tidyverse-compatible interface
- Stata package installable from SSC with native syntax
- Documentation and vignettes for econometric workflows

**Why This Matters**: Infrastructure succeeds through adoption. TAXSIM's simple interface lowered barriers. PolicyEngine needs equivalent accessibility.

### 3.4 Memory-Efficient Branching and Cloud Infrastructure

**Current State**: PolicyEngine already implements scenario branching for provisions requiring multiple calculations—itemization vs. standard deduction elections, AMT comparisons, filing status optimization. However, branching multiplies memory requirements: each branch requires storing intermediate results for all households.

**Problem**: On standard researcher hardware (16-32GB RAM), memory constraints prevent:
- Full population microsimulation with branching enabled
- Complex reforms with multiple interacting branches
- Interactive research workflows requiring rapid iteration

Researchers must either use simplified models (disabling branches) or access high-memory cloud infrastructure themselves.

**What's Needed**: Two complementary solutions:
1. *Memory optimization*: Smart caching that reduces branch memory footprint through lazy evaluation, checkpoint/restart for memory-constrained environments, and streaming computation avoiding full materialization
2. *Cloud research infrastructure*: Easy pathways for researchers to run large simulations on cloud resources, including PolicyEngine's own cloud infrastructure with pre-configured environments

**Research Enabled**: Graduate students can run full population simulations from laptops by offloading to cloud. Researchers can iterate on complex branching reforms without memory errors. Workshops can provide cloud access for hands-on training.

---

## 4. Technical Approach

### 4.1 Continuous Validation Infrastructure

**TAXSIM Validation Pipeline**:

1. *Automated Test Generation*: Scripts generating diverse tax scenarios—random households, edge cases, state variations, historical years, high-income filers, multiple dependents, itemizers vs. standard deduction.

2. *CI Integration*: Every pull request triggers validation:
   - Submit scenarios to TAXSIM API
   - Calculate same scenarios in PolicyEngine
   - Compare results within tolerance ($100 for most cases)
   - Post comparison summary to PR

3. *Accuracy Dashboard*: Public dashboard showing:
   - Agreement rates by state, year, scenario type
   - Historical trends
   - Known discrepancy documentation
   - Regression alerts

4. *Regression Detection*: Block merges that degrade accuracy beyond thresholds.

**Atlanta Fed PRD Validation**:

1. *Parameter Cross-Reference*: Automated comparison of encoded parameters against PRD documentation.
2. *Benefit Program Validation*: Test scenarios for SNAP, TANF, Medicaid against PRD specifications.
3. *Bidirectional Feedback*: Workflow for reporting PRD documentation gaps alongside PolicyEngine corrections.

**Validation Targets**:

| Metric | Target |
|--------|--------|
| TAXSIM agreement (federal, ±$100) | >98% of scenarios |
| TAXSIM agreement (state, ±$100) | >95% of scenarios |
| PRD parameter coverage | >99% of documented parameters |
| Validation frequency | Every pull request |
| Public dashboard | Real-time accuracy metrics |

### 4.2 Performance Optimization

**Vectorization Strategy**:
- Identify calculation hotspots through profiling
- Replace Python conditionals with NumPy where/select
- Implement lazy evaluation (skip unused variables)
- Optimize data structures for cache efficiency

**Parallelization Strategy**:
- Chunk-based processing across CPU cores
- Thread-safe calculation graph
- Optional Dask backend for larger-than-memory datasets
- Experimental GPU acceleration for matrix operations

**Performance Targets**:

| Scenario | Current | Year 3 Target |
|----------|---------|---------------|
| Single household | 50ms | 20ms |
| 100K households | 3 min | 45 sec |
| Full population (150M) | 8 hours | 90 min |
| Policy optimization (1000 evals) | 6 days | 1 day |

### 4.3 R and Stata Interfaces

**R Package (policyengine)**:
- CRAN-compliant package structure
- Tidyverse-compatible interface (tibbles, pipe-friendly)
- Vignettes: microsimulation workflow, reform analysis, distributional analysis
- Integration with survey package for weighted analysis

```r
library(policyengine)

# Calculate household outcomes
household <- pe_household(
  adults = 2, children = 2,
  earnings = c(45000, 0),
  state = "CA"
)
calculate(household, "snap")  # SNAP benefit

# Model reform
reform <- pe_reform(ctc_amount = 3600)
compare_reforms(household, baseline = NULL, reform = reform)
```

**Stata Package (policyengine)**:
- SSC-installable ado files
- Native Stata syntax
- Integration with svyset for survey estimation
- Examples with common datasets (CPS, ACS)

```stata
* Calculate for dataset
policyengine using mydata.dta, ///
    earnings(earnings) state(state_fips) ///
    calculate(net_income snap eitc)

* Model reform
policyengine, reform(ctc_amount=3600) ///
    compare(baseline reform)
```

### 4.4 Memory-Efficient Branching and Cloud Infrastructure

**Memory Optimization Strategy**:

1. *Lazy Branch Evaluation*: Only compute branches when results are needed; skip branches that don't affect final outcomes for specific households
2. *Smart Caching*: Share intermediate results across branches where calculations are identical; evict cached values no longer needed
3. *Streaming Computation*: Process households in chunks, writing results to disk rather than holding full population in memory
4. *Checkpoint/Restart*: Enable long simulations to pause and resume, allowing use of spot instances and time-limited environments

**Cloud Research Infrastructure**:

1. *PolicyEngine Cloud API*: Hosted endpoint where researchers submit simulation specifications and receive results, abstracting infrastructure complexity
2. *Pre-configured Cloud Templates*: One-click deployment to AWS/GCP with appropriate instance sizing, enabling researchers to run their own infrastructure when needed
3. *Workshop Cloud Access*: Managed environments for training sessions where participants can run full population simulations without local resource constraints
4. *Hybrid Workflows*: Local development and testing on sample data, seamless scaling to cloud for full population runs

**Memory Targets**:

| Scenario | Current Memory | Target |
|----------|----------------|--------|
| 100K households, simple | 2GB | 1GB |
| 100K households, full branching | 8GB | 3GB |
| Full population, simple | 64GB | 24GB |
| Full population, full branching | 200GB+ (fails) | 64GB (cloud) |

---

## 5. Relationship to Existing NSF Investment

PolicyEngine is an active **NSF POSE Phase I awardee** (Award #2229069, through July 2026). POSE focuses on ecosystem development: governance structures, contributor pathways, community building, customer discovery.

This CSSI Elements proposal is **complementary and non-overlapping**:

| POSE Phase I (Ecosystem) | CSSI Elements (Infrastructure) |
|--------------------------|--------------------------------|
| Community governance | Validation pipelines |
| Contributor onboarding | Performance optimization |
| I-Corps customer discovery | R/Stata interfaces |
| Documentation standards | Memory optimization & cloud infrastructure |

POSE funds *how the community works together*; CSSI funds *the technical foundation they build on*. Neither duplicates the other.

---

## 6. Timeline and Milestones

### Year 1: Validation Foundation

**Q1-Q2**:
- Design validation pipeline architecture
- Establish baseline TAXSIM accuracy metrics
- Begin R package development
- Document current accuracy status

**Q3-Q4**:
- Deploy TAXSIM CI validation (federal taxes)
- Release R package alpha
- Begin Stata package development
- Launch accuracy dashboard (beta)

**Year 1 Deliverables**:
- TAXSIM CI validation for federal taxes
- R package alpha on GitHub
- Public accuracy dashboard (beta)
- Baseline accuracy report

### Year 2: Scale and Accessibility

**Q1-Q2**:
- Extend TAXSIM validation to all 50 states
- Implement Atlanta Fed PRD validation
- Submit R package to CRAN
- Begin performance optimization

**Q3-Q4**:
- Release Stata package to SSC
- Deploy production accuracy dashboard
- Achieve 2x performance improvement
- Document validation methodology

**Year 2 Deliverables**:
- Full 50-state TAXSIM validation
- R package on CRAN, Stata on SSC
- PRD validation pipeline
- 2x performance improvement
- Validation methodology paper

### Year 3: Production and Community

**Q1-Q2**:
- Production stability and edge cases
- Memory-efficient branching implementation
- Cloud research infrastructure deployment
- API finalization

**Q3-Q4**:
- Documentation and tutorials
- Workshop materials
- Community training
- Sustainability transition

**Year 3 Deliverables**:
- Memory-efficient branching in production
- Cloud research infrastructure live
- Complete documentation suite
- Workshop curriculum with cloud access
- Published methodology paper

---

## 7. Broader Impacts

### 7.1 Democratizing Policy Analysis

The most significant broader impact is expanding who can conduct rigorous policy analysis:

**Graduate Students**: Dissertation research on tax-benefit policy currently requires access to TRIM3 (expensive) or building custom tools (time-consuming). PolicyEngine enables any student to conduct publication-quality analysis with proper microsimulation.

**State and Local Government**: State fiscal offices often rely on simplified models or expensive consultants. A state legislator wanting to understand how a proposed earned income credit interacts with SNAP must currently wait weeks for analysis. Open infrastructure enables independent, immediate analysis.

**International Researchers**: Scholars outside the US face barriers studying American policy. TAXSIM requires US institutional affiliation for some features; TRIM3 requires licensing negotiations. Open-source tools remove these obstacles.

**Community Organizations**: Advocacy groups can independently verify claims about policy impacts rather than relying on analyses they cannot inspect.

### 7.2 Reproducible Research

Every PolicyEngine calculation is:
- **Version-controlled**: Tagged releases enable exact replication
- **Traceable**: Citations to statute embedded in code
- **Inspectable**: Open source enables verification
- **Testable**: Validation infrastructure ensures accuracy

Research using PolicyEngine can specify exact version, parameters, and data, enabling perfect reproducibility—a significant advance over citing proprietary models.

### 7.3 Research Training

We will develop:
- **Tutorial notebooks** replicating published research using PolicyEngine
- **Workshop curriculum** for graduate methods courses
- **Example datasets** demonstrating common research workflows
- **Video documentation** for self-paced learning

Curriculum discussions are underway at Berkeley, Georgetown, Northwestern, and Harvard.

### 7.4 Public Benefit

PolicyEngine powers benefit navigation tools reaching 100,000+ individuals annually, identifying over $1 billion in unclaimed benefits across multiple platforms—MyFriendBen ($800M+ in Colorado), Amplifi's Benefit Navigator ($185M in California), and partners including Student Basic Needs Coalition, Mirza, and Starlight. Improved accuracy and coverage directly translates to better benefit identification for those who need it most.

---

## 8. Team and Qualifications

**Max Ghenis, PI** (PolicyEngine CEO): Founded PolicyEngine in 2021. Led successful NSF POSE Phase I application. Former Google data scientist and researcher at the UBI Center. Economics background (MIT) with expertise in microsimulation and public policy analysis.

**Nikhil Woodruff, Co-PI** (PolicyEngine CTO): Lead architect of PolicyEngine Core and PolicyEngine-UK. Currently serving on secondment to UK Cabinet Office/HM Treasury, where PolicyEngine UK is integrated into policy analysis workflows. Computer science background with expertise in software architecture and open-source development.

**Dan Feenberg, Advisor** (NBER): Creator and maintainer of TAXSIM since 1993. Serving as I-Corps mentor for POSE Phase I. Provides direct access for TAXSIM validation comparisons and methodology consultation.

**John Sabelhaus, Advisor** (Former Federal Reserve): Led Social Security modeling at the Federal Reserve. Expert on longitudinal microsimulation and retirement policy. Provides guidance on microsimulation methodology and validation.

---

## 9. Sustainability

PolicyEngine's sustainability does not depend on perpetual grant funding:

**Commercial Revenue Streams**:
- Tax preparation software integration
- Financial planning tools
- Policy consulting for government and advocacy organizations
- Custom model development

**Government Contracts**:
- Custom implementations for state fiscal offices
- Integration projects for federal agencies
- Training and support services

**Community Maintenance**:
- 30+ contributors across the ecosystem
- 620+ forks indicating active community engagement
- Governance structures developed under POSE Phase I

**Open Source Economics**:
- Core infrastructure remains freely available
- Value-added services generate revenue
- Community contributions reduce maintenance burden

The goal is for PolicyEngine to become as foundational for tax-benefit research as TAXSIM has been for tax research—and to sustain itself through the value it creates for researchers, governments, and the public.
