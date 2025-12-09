## Our Perspective on RAF's Concepts

### The Core Insight

The RFI seeks tools that "scan a state's statutory codes for sources of burden." Text scanning can find keywords, but statutes and regulations are inherently computational—they define inputs, conditions, and outputs. A regulation that says "if income exceeds 130% of the federal poverty level, benefits shall be reduced by 30 cents for each dollar above that threshold" is describing an algorithm.

By compiling legal text into executable logic, you can analyze it mathematically: identify circular dependencies, find where two provisions require conflicting inputs, detect where regulations add requirements not present in authorizing statutes, and compare how different states implement the same federal program.

**This is what we do for tax-benefit programs.** We haven't yet applied it to RAF's diagnostic use case—scanning for procedural burden like wet signature requirements or excessive approval steps—but our infrastructure provides a foundation.

### How Our Infrastructure Applies to Each Concept

**Concept 1 & 2 (Diagnostic tools for statutes, regulations, and guidance):**
Our dependency graphs already trace how each rule connects to others. Extending this to flag conflicts, duplications, and gaps between regulations and authorizing statutes is architecturally feasible. We would need to expand our encoding scope beyond benefit calculations to include procedural requirements (signature requirements, reporting mandates, approval processes).

**Concept 3 (Rewriting tools):**
Our platform generates plain-language explanations of how policies affect applicants. We have not built tools to rewrite regulatory text itself, but the underlying capability—translating between legal language and structured logic—is similar.

**Concept 4 (Models trained on procedural burden):**
Our API customers (MyFriendBen, Amplifi, etc.) encounter real friction when helping applicants. We don't currently aggregate this systematically, but their experience could inform what provisions cause actual burden versus theoretical burden.

**Concept 5 (Cross-state comparison and regulatory cleanup):**
**This is our core strength.** We encode the same programs across all 50 states. Today we can answer: "How does State X's SNAP eligibility compare to State Y's?" Extending this to generate model legislation or reform packages that simplify rules while preserving policy intent is a natural next step.

### What We Would Deliver

For a pilot state, we would:

1. **Expand encoding scope** to include procedural requirements (approval processes, signature requirements, reporting mandates) beyond benefit calculations
2. **Build diagnostic queries** on our dependency graphs to surface conflicts, redundancies, and regulation-statute gaps
3. **Generate cross-state comparison reports** showing where the pilot state's procedures exceed peer states
4. **Trace findings to citations** so reviewers can verify each flagged provision against source text
5. **Simulate reform impacts** using our microsimulation engine—estimate how many applicants would be affected by removing an asset test or simplifying an approval process
