---
layout: single
title: "How I Built the MSE Knowledge Graph"
date: 2026-04-04
categories: blog
tags: knowledge-graphs, materials-science, ontology, FAIR, NFDI
excerpt: "A practical walkthrough of building a large-scale knowledge graph for materials science — from ontology design to SPARQL queries."
author_profile: true
toc: true
toc_label: "Contents"
toc_sticky: true
---

Building a knowledge graph for an entire scientific domain is a daunting task. In this post, I'll walk through how we built the **Materials Science and Engineering Knowledge Graph (MSE-KG)** as part of the NFDI-MatWerk project — the decisions we made, the tools we used, and the lessons we learned.

## Why a Knowledge Graph?

Materials science data is incredibly heterogeneous. You have:
- **Experimental data** from tensile tests, SEM images, XRD spectra
- **Simulation data** from DFT, molecular dynamics, FEM
- **Metadata** — who did what, when, with which equipment
- **Publications** linking all of these together

The problem? This data lives in different formats, different databases, and different institutions. A researcher at KIT can't easily find related experiments done at Fraunhofer, even if they're studying the same material.

A **knowledge graph** solves this by creating a unified semantic layer — every entity (a material, a person, an experiment, a publication) becomes a node, and relationships between them become edges. All queryable via SPARQL.

## Step 1: Choose Your Ontology Stack

The foundation of any knowledge graph is its ontology — the formal model that defines what types of things exist and how they relate.

We chose a layered approach:

```
BFO (Basic Formal Ontology)        ← Upper-level
  └── NFDIcore                     ← Mid-level (cross-domain NFDI)
       └── MWO (MatWerk Ontology)  ← Domain-level (materials science)
```

**Why BFO?** It's the most widely adopted upper-level ontology in science. Using BFO means our ontology is inherently interoperable with hundreds of others in biology, chemistry, and engineering.

**Why NFDIcore?** It provides shared classes for research infrastructure (datasets, persons, organizations, software) that are common across all NFDI consortia. This means our materials science data can interoperate with cultural heritage, chemistry, and data science data.

## Step 2: Model Your Domain

The hardest part isn't the technology — it's the **modeling decisions**. For materials science, we needed to represent:

- **Materials** with their composition, structure, and properties
- **Processes** — how a material is synthesized, tested, or simulated
- **Measurements** — what was measured, how, and what the results were
- **Provenance** — who did this work, at which institution, funded by whom

We used **Ontology Design Patterns (ODPs)** — modular, reusable modeling templates. For example, our "Process Pattern" captures:

```
Process → has_input → Material
Process → has_output → Material
Process → has_parameter → Parameter
Process → realized_by → Agent
```

This pattern works for everything from a tensile test to a DFT simulation.

## Step 3: Ingest Data

We integrated data from multiple sources:

| Source | What we extracted | Method |
|--------|------------------|--------|
| Semantic Scholar | Publications, authors, citations | API + Python scripts |
| ORCID | Researcher identifiers | API |
| ROR | Organization identifiers | API |
| DataCite | Dataset metadata | API |
| Wikidata | Material properties, identifiers | SPARQL federation |
| Institutional DBs | Experimental metadata | Custom ETL pipelines |

Each source required a custom **ETL (Extract, Transform, Load) pipeline**. We wrote these in Python, outputting RDF triples that conform to our ontology.

## Step 4: Quality Assurance

A knowledge graph is only useful if its data is correct. We implemented:

- **SHACL validation** — shape constraints that check if the data conforms to the ontology
- **Competency questions** — SPARQL queries that the KG must be able to answer (e.g., "Find all tensile test results for steel alloys published after 2020")
- **Cross-referencing** — checking that entity URIs resolve and that linked data is consistent

## Step 5: Deploy and Query

The MSE-KG is served via a **SPARQL endpoint** backed by a triplestore. Researchers can:

1. Run SPARQL queries directly
2. Use our web interface for guided exploration
3. Access the data via a REST API

Example query — find all publications by researchers at FIZ Karlsruhe about knowledge graphs:

```sparql
SELECT ?paper ?title ?author ?date WHERE {
  ?paper a nfdicore:Publication ;
         schema:name ?title ;
         schema:author ?author ;
         schema:datePublished ?date .
  ?author schema:affiliation ?org .
  ?org schema:name "FIZ Karlsruhe" .
  FILTER(CONTAINS(LCASE(?title), "knowledge graph"))
}
ORDER BY DESC(?date)
```

## Lessons Learned

1. **Start with competency questions, not the ontology.** Define what questions the KG needs to answer before modeling. This keeps you focused.

2. **Reuse before you create.** For every class or property you want to add, check if BFO, Dublin Core, Schema.org, or another standard already defines it.

3. **Ontology engineering is a social process.** The hardest part was getting domain experts and ontology engineers to agree on modeling decisions. Regular workshops and working examples helped enormously.

4. **Automate everything.** Data integration, validation, deployment — if it's manual, it won't scale and it won't be maintained.

5. **Ontology Design Patterns save time.** Instead of modeling from scratch, reusable patterns gave us a head start and ensured consistency.

## What's Next

We're working on:
- Expanding the KG with more institutional data sources
- Building LLM-powered interfaces for natural language querying
- Federated SPARQL queries across NFDI consortia
- Automated ontology alignment using machine learning

---

*If you're building a knowledge graph for your domain, feel free to [reach out](mailto:norouzi.iut@gmail.com). The MSE-KG tools and ontologies are all open source.*

*Explore the MSE-KG: [https://nfdi.fiz-karlsruhe.de/matwerk/](https://nfdi.fiz-karlsruhe.de/matwerk/){:target="_blank"}*
