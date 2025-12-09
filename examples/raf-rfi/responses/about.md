## About PolicyEngine

PolicyEngine builds open-source infrastructure for translating tax and benefit statutes and regulations into executable code. Our rules engine calculates how laws affect households—eligibility, benefits, taxes, and marginal rates—across all 50 states. API customers including MyFriendBen, Amplifi, and the Student Basic Needs Coalition use this to help applicants navigate benefits, together identifying over $1 billion in unclaimed support.

**What we have built:**

- **3,000+ rules, 9,000+ parameters** encoding federal and state tax-benefit programs (SNAP, Medicaid, EITC, income taxes, and dozens more)
- **All 50 states** with the same programs encoded consistently, enabling direct cross-state comparison
- **1,800+ legal citations** linking every calculation to U.S. Code, CFR, state statutes, and agency manuals
- **Dependency graphs** showing how each rule relates to others—which inputs feed which calculations
- **[policyengine-core](https://github.com/PolicyEngine/policyengine-core)**, derived from [OpenFisca](https://openfisca.org/)—the rules-as-code framework created and used by the French government

**Validation and users:**

- Validated against [NBER TAXSIM](https://taxsim.nber.org/) (MOU; Dan Feenberg advises) and [Atlanta Fed Policy Rules Database](https://www.atlantafed.org/economic-mobility-and-resilience/advancing-careers-for-low-income-families/policy-rules-database) (MOU)
- Used for policy analysis by the Joint Economic Committee, [Niskanen Center](https://policyengine.org/us/research/niskanen-center-analysis), UK Cabinet Office/HM Treasury, and NY State Legislature
- [NSF POSE Phase I awardee](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2229069) for open-source ecosystem development
- Public-facing at [policyengine.org](https://policyengine.org)—not restricted to government staff
