---
key: delivery_metrics
status: draft
title: Delivery Mechanism and Community Usage Metrics
---

# Delivery Mechanism and Community Usage Metrics

## 1. Delivery Mechanisms

### 1.1 Software Releases

All deliverables will be released as open-source software under the MIT License through the PolicyEngine GitHub organization (github.com/PolicyEngine).

**Core Infrastructure Packages:**
- **policyengine-core**: Rules engine with scenario branching (PyPI, conda-forge)
- **policyengine-us**: U.S. tax-benefit model with enhanced validation (PyPI, conda-forge)
- **policyengine-us-data**: Calibrated microdata for population-scale analysis (PyPI)

**New Interface Packages:**
- **policyengine-r**: R/CRAN package for economists using R/Stata workflows
- **policyengine-api-client**: Simplified Python client for API access

**Release Schedule:**
- Quarterly releases aligned with tax year updates and legislative changes
- Semantic versioning with backward compatibility guarantees
- Automated release pipelines via GitHub Actions

### 1.2 API Access

The PolicyEngine API (api.policyengine.org) provides programmatic access:
- REST endpoints for household calculations and population-scale analysis
- Authentication via API keys for rate limiting and usage tracking
- Documentation at docs.policyengine.org

### 1.3 Web Interface

The PolicyEngine web application (policyengine.org) provides:
- Interactive household calculators for non-programmers
- Policy reform builders with real-time impact estimates
- Embeddable widgets for partner applications

### 1.4 Documentation and Training

- Comprehensive API documentation with examples
- Jupyter notebook tutorials for common research workflows
- Annual training webinars for new users
- Office hours for research community support

---

## 2. Community Usage Metrics

### 2.1 Current Baseline Metrics (2024)

| Metric | Current Value | Source |
|--------|---------------|--------|
| Web application users | 100,000+ annually | Google Analytics |
| API calls | 2M+ monthly | API logs |
| PyPI downloads | 50,000+ monthly | PyPI Stats |
| GitHub stars | 500+ | GitHub |
| Academic citations | 15+ | Google Scholar |
| Partner integrations | 5 active | Internal tracking |

### 2.2 Target Metrics (End of Year 3)

| Metric | Year 1 Target | Year 2 Target | Year 3 Target |
|--------|---------------|---------------|---------------|
| Monthly API calls | 3M | 5M | 10M |
| PyPI downloads (monthly) | 75,000 | 100,000 | 150,000 |
| Academic citations | 25 | 50 | 100 |
| R package downloads | 5,000 | 15,000 | 30,000 |
| Partner integrations | 8 | 12 | 20 |
| Research papers enabled | 5 | 15 | 30 |

### 2.3 Measurement Methods

**Software Usage:**
- PyPI and CRAN download statistics (public)
- API request logs with anonymized usage patterns
- GitHub clone/fork statistics

**Research Impact:**
- Google Scholar citations to PolicyEngine and papers using it
- Annual user survey to research community
- Tracking of published papers citing PolicyEngine

**Partner Adoption:**
- Active API keys with sustained usage
- Partner application integrations (MyFriendBen, Amplifi, etc.)
- Government and NGO deployments

### 2.4 Reporting

- Quarterly metrics reports published to project website
- Annual comprehensive impact report
- Metrics dashboard accessible to NSF program officers
