---
key: data_management_plan
status: draft
title: Data Management Plan
---

# Data Management Plan

## 1. Types of Data Produced

This project produces primarily **software and validation data**, not research datasets:

### 1.1 Software Artifacts
- **PolicyEngine Core**: Python library implementing tax-benefit microsimulation
- **Validation Pipelines**: Automated testing infrastructure comparing against TAXSIM and Atlanta Fed PRD
- **Documentation**: Technical specifications, API references, tutorials

### 1.2 Validation Data
- **Test Cases**: Synthetic tax scenarios for validation (no real taxpayer data)
- **Accuracy Metrics**: Aggregated comparison statistics (e.g., "98% of test cases within $100 of TAXSIM")
- **Benchmark Results**: Performance measurements across different computation scales

### 1.3 No Personal Data
This project does not collect, use, or generate personally identifiable information. All test cases use synthetic scenarios. Microsimulation inputs are hypothetical tax situations, not real taxpayer records.

## 2. Data Standards and Formats

### 2.1 Software
- **Language**: Python 3.10+
- **Package Format**: Standard Python packaging (pyproject.toml, pip-installable)
- **Version Control**: Git with semantic versioning (major.minor.patch)
- **Documentation**: Sphinx-generated docs in reStructuredText/Markdown

### 2.2 Validation Data
- **Test Cases**: YAML format for human readability and version control
- **Metrics**: JSON format for programmatic access
- **Dashboards**: Web-accessible via standard HTTPS

### 2.3 Metadata
- **Code Documentation**: Docstrings following NumPy convention
- **Citation Metadata**: Structured references to U.S. Code, CFR, state statutes
- **Version Metadata**: Git tags, changelog entries, release notes

## 3. Data Access and Sharing

### 3.1 Open Access Policy

All project outputs are freely available:

| Output | Repository | License | Access |
|--------|------------|---------|--------|
| PolicyEngine Core | GitHub | AGPL-3.0 | Public |
| Validation pipelines | GitHub | MIT | Public |
| Documentation | GitHub Pages | CC-BY-4.0 | Public |
| Accuracy dashboard | Web | Open | Public |

### 3.2 Distribution Channels
- **Primary**: GitHub (github.com/PolicyEngine)
- **Package Distribution**: PyPI (pip install policyengine-us)
- **Documentation**: policyengine.github.io
- **Archival**: Zenodo (DOI assignment for major releases)

### 3.3 Timing
- Code changes: Continuous (public repository from day one)
- Releases: Semantic versioning, approximately monthly
- Documentation: Updated with each release
- Archival snapshots: Major version releases (annual)

## 4. Data Preservation

### 4.1 Repositories
- **Primary**: GitHub (active development, issue tracking)
- **Archival**: Zenodo (DOI-assigned snapshots, long-term preservation)
- **Backup**: Software Heritage (automatic archival of public GitHub repos)

### 4.2 Preservation Period
- GitHub: Indefinite (as long as GitHub exists)
- Zenodo: Minimum 20 years (CERN institutional commitment)
- Software Heritage: Permanent (UNESCO-supported mission)

### 4.3 Format Longevity
Python source code and standard data formats (YAML, JSON) are text-based and human-readable, ensuring accessibility regardless of future software evolution.

## 5. Roles and Responsibilities

| Role | Responsibility |
|------|----------------|
| PI (Ghenis) | Overall data management oversight, release decisions |
| Co-PI (Woodruff) | Technical implementation, repository management |
| Research Engineer | Day-to-day code management, documentation |

## 6. Privacy and Confidentiality

### 6.1 No Personal Data
This project does not handle personal data. All microsimulation inputs are:
- Synthetic test cases (hypothetical taxpayers)
- Published survey microdata (already de-identified by source agencies)
- User-specified scenarios (entered voluntarily by users)

### 6.2 Validation Data
Comparisons against TAXSIM use synthetic scenarios, not real tax returns. Aggregate accuracy metrics (e.g., percentage of cases matching) are published; individual test case details may be published for reproducibility.

### 6.3 No IRB Required
This project does not involve human subjects research. No IRB review is required.

## 7. Budget for Data Management

Data management activities require minimal dedicated budget:
- **Repository hosting**: GitHub (free for open source)
- **Archival**: Zenodo (free, CERN-supported)
- **Documentation hosting**: GitHub Pages (free)
- **Dashboard hosting**: Included in cloud computing budget ($4,000/year)

Personnel time for documentation and release management is included in the Research Software Engineer allocation.
