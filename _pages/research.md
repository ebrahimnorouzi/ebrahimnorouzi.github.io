---
permalink: /research/
title: "Research"
author_profile: true
toc: true
toc_label: "Research Areas"
toc_sticky: true
---

My research focuses on making materials science data **FAIR** (Findable, Accessible, Interoperable, Reusable) through knowledge graphs, ontologies, and semantic technologies. I work at the intersection of **Knowledge Engineering**, **Materials Informatics**, and **AI**.

## The Big Picture

Materials science generates vast amounts of heterogeneous data — from lab experiments and simulations to published literature. But this data is often trapped in silos: proprietary databases, PDFs, unstructured spreadsheets, and disconnected repositories. My work aims to **bridge these silos** by creating a shared semantic layer that machines and humans can both understand.

## MSE Knowledge Graph (MSE-KG)

<div class="intro-highlight" markdown="1">
The **Materials Science and Engineering Knowledge Graph** is the central output of my PhD — a large-scale, FAIR-compliant knowledge graph that integrates metadata from materials science research.
</div>

The MSE-KG connects researchers, organizations, datasets, publications, and experimental workflows into a single queryable graph. It is built on top of the [NFDI-MatWerk Ontology (MWO)](https://github.com/nfdi-matwerk/mwo){:target="_blank"} and the [NFDIcore](https://nfdicore.2005.2s.2.2.2) ontology framework.

**Key contributions:**
- Centralized metadata management for the NFDI-MatWerk consortium
- SPARQL endpoint for querying across heterogeneous materials science data
- Integration with external sources (Wikidata, ORCID, ROR, DataCite)
- Won "Best Demo" at NFDI-MatWerk AHoD 2026

[MSE-KG Website](https://nfdi.fiz-karlsruhe.de/matwerk/){:target="_blank"} | [Publication](/publication/semantic-representation-of-processes-with-ontology-desi/){:target="_blank"}

## Ontology Design Patterns for Materials Science

Ontologies in materials science are often **complex and hard to reuse**. Ontology Design Patterns (ODPs) offer modular, reusable solutions — like design patterns in software engineering, but for knowledge modeling.

My work surveys existing ontologies, **extracts implicit design patterns** from their structures, and proposes standardized patterns for common modeling problems in MSE:

- Process and workflow representation
- Material composition and structure
- Measurement and characterization
- Provenance and experimental metadata

**Key contributions:**
- Comprehensive survey of MSE ontologies and their process modeling capabilities
- Baseline method for automatic ODP extraction from existing ontologies
- Open-source pattern catalog: [ODPs4MSE on GitHub](https://github.com/ISE-FIZKarlsruhe/odps4mse){:target="_blank"}

## NFDI-MatWerk Ontology (MWO)

The **MWO** is a BFO-compliant domain ontology I co-developed for research data management in materials science. It serves as the backbone for the MSE-KG and is designed to:

- Align with the Basic Formal Ontology (BFO) upper-level framework
- Provide domain-specific classes for materials, processes, and properties
- Enable interoperability across NFDI consortia (MatWerk, Culture, DS, Memory, Chem)

[MWO v3.0.0 on GitHub](https://github.com/nfdi-matwerk/mwo){:target="_blank"} | [Publication](/publications/){:target="_blank"}

## Chemotion Knowledge Graph

As part of the AI4DiTraRe project, I built a **BFO-compliant knowledge graph** from experimental chemistry data in the Chemotion electronic lab notebook system.

This KG enables:
- Cross-referencing experimental procedures with ontological concepts
- Provenance tracking from raw measurements to published results
- AI-driven discovery of related experiments and materials

[Chemotion-KG](https://ditrare.ise.fiz-karlsruhe.de/chemotion-kg/){:target="_blank"}

## LLMs for Knowledge Engineering

I'm also exploring how **Large Language Models** can assist with:
- Ontology alignment and matching (OAEI campaigns)
- Information extraction from scientific literature
- Automated knowledge graph construction
- Concept extraction using NLP pipelines (ConExion)

## Collaborations & Projects

| Project | Role | Description |
|---------|------|-------------|
| [NFDI-MatWerk](https://nfdi-matwerk.de/){:target="_blank"} | Researcher | National research data infrastructure for materials science |
| [AI4DiTraRe](https://ditrare.ise.fiz-karlsruhe.de/){:target="_blank"} | Researcher | AI for Digital Transformation in Research |
| [PMD](https://www.2.2materialdigital.de/){:target="_blank"} | Contributor | Platform MaterialDigital — core ontology (PMDco) |

---

*See my full [publication list](/publications/) or explore my [GitHub projects](/projects/) for code and datasets.*
