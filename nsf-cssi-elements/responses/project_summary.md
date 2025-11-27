---
key: project_summary
status: draft
title: Project Summary
---

# Project Summary

## Overview

Public economics research increasingly requires modeling the joint tax-benefit system—how income taxes, payroll taxes, and benefit programs like SNAP, Medicaid, and the EITC interact to shape household incentives and outcomes. Yet existing cyberinfrastructure was designed for an earlier era: TAXSIM models income taxes but not benefits; TRIM3 models benefits but is only accessible through commissioned reports; neither supports independent reform modeling. Researchers studying effective marginal tax rates, benefit cliffs, or optimal policy design must cobble together separate tools or build custom solutions.

PolicyEngine is open-source infrastructure that models the complete U.S. tax-benefit system—federal and state income taxes, payroll taxes, and major benefit programs—in a unified framework. Users can calculate current-law outcomes or model any hypothetical reform. Everything runs on calibrated microdata via modern Python APIs, and every calculation traces to 1,800+ statutory citations embedded in the codebase. We are validated against NBER's TAXSIM (MOU with NBER; Dan Feenberg serves as advisor) and the Atlanta Fed Policy Rules Database. Current users include the Joint Economic Committee, UK Treasury, and researchers at USC, Harvard, and Georgetown.

This project will modernize PolicyEngine's core infrastructure to support population-scale research. We will build **continuous validation infrastructure** that automatically compares every release against TAXSIM and Atlanta Fed benchmarks, ensuring accuracy as law changes annually. We will deliver **performance improvements** enabling microsimulation across 150+ million tax units for distributional research and policy optimization. We will create **R and Stata interfaces** to meet economists in their preferred environments. And we will optimize **memory-efficient branching** for complex tax provisions and provide **cloud research infrastructure** enabling population-scale analysis without high-end local hardware.

The research opportunity is substantial. Consider a researcher studying how proposed CTC expansions interact with SNAP phase-outs to affect labor supply—this requires modeling taxes and benefits together with reform capability at population scale. Or consider studying effective marginal tax rates across states—this requires 50-state tax and benefit models in a unified framework. PolicyEngine enables this research, but core infrastructure modernization is required to support it reliably at scale.

## Intellectual Merit

This project creates open-source cyberinfrastructure enabling research on the joint tax-benefit system at population scale. The intellectual contributions include: (1) continuous cross-model validation methodology establishing accuracy benchmarks for microsimulation; (2) performance architecture enabling real-time policy optimization over population samples; (3) technical approaches for modeling complex tax provisions with scenario branching; and (4) reproducible infrastructure where every calculation traces to authoritative sources.

Most significantly, the infrastructure enables research questions currently intractable with existing tools. How do SNAP benefit reductions interact with EITC phase-outs to affect labor supply? What policy combinations minimize poverty while maintaining work incentives? How do effective marginal tax rates vary across states due to benefit program differences? These questions require modeling taxes and benefits together at population scale—precisely what PolicyEngine provides.

## Broader Impacts

Open tax-benefit infrastructure democratizes policy analysis capabilities currently restricted to well-resourced institutions. Graduate students can conduct dissertation research without proprietary software licenses or restricted data access. State legislators can independently model policy alternatives rather than waiting weeks for external analysis. International researchers can study U.S. policy without institutional barriers.

The platform already demonstrates broader impact: partner applications have identified over $1 billion in unclaimed benefits for low-income families across platforms including MyFriendBen, Amplifi's Benefit Navigator, Student Basic Needs Coalition, Mirza, and Starlight. Every calculation is version-controlled and traceable to statute, enabling reproducible research. Commercial applications in tax preparation and financial planning provide sustainability pathways ensuring long-term maintenance without perpetual grant funding.

The goal is cyberinfrastructure as foundational for tax-benefit research as TAXSIM has been for tax research alone—but open, comprehensive, and designed for modern research workflows.

## Keywords

Tax-benefit microsimulation; open-source infrastructure; policy reform modeling; TAXSIM; effective marginal tax rates; SNAP; EITC; computational economics; reproducible research; rules as code
