---
title: "The Materials Science and Engineering Knowledge Graph (MSE-KG): Apache Airflow–Orchestrated Construction Pipeline"
collection: publications
permalink: /publication/the-materials-science-and-engineering-knowledge-graph-m/
excerpt: 'The Materials Science and Engineering Knowledge Graph (MSE-KG) is a reproducible and modular pipeline for constructing domain-specific knowledge graphs within the context of the National Research Data Infrastructure for Materials Science and Engineering (NFDI-MatWerk). This work…'
date: 2026-04-09
venue: 'Zenodo (Presentation)'
paperurl: 'https://doi.org/10.5281/zenodo.19484380'
citation: 'Norouzi, Ebrahim, Beygi Nasrabadi, Hossein, Singh, Gunjan, Waitelonis, Jörg, Sack, Harald (2026). "The Materials Science and Engineering Knowledge Graph (MSE-KG): Apache Airflow–Orchestrated Construction Pipeline". Zenodo (Presentation).'
citation_count: 0
source: zenodo
zenodo_id: 19484380
---
The Materials Science and Engineering Knowledge Graph (MSE-KG) is a reproducible and modular pipeline for constructing domain-specific knowledge graphs within the context of the National Research Data Infrastructure for Materials Science and Engineering (NFDI-MatWerk). This work presents an Apache Airflow&ndash;orchestrated workflow that automates the end-to-end lifecycle of knowledge graph construction, including data acquisition, ontology population, reasoning, validation, and publication. The pipeline is implemented as a set of Directed Acyclic Graphs (DAGs), ensuring transparency, traceability, and reproducibility of each processing step. The system integrates semantic web technologies and tools such as ROBOT for ontology processing, Openllet for OWL reasoning, and SHACL/SPARQL for validation. It supports both template-driven ontology construction and harvester-based ingestion of external data sources such as Zenodo records and SPARQL endpoints. Each pipeline execution generates versioned outputs, including OWL modules, RDF graphs, validation reports, and logs, which are subsequently published to a triple store (e.g., Virtuoso) as named graphs. This enables consistent monitoring, debugging, and reuse of results. The presented workflow demonstrates how scalable and automated infrastructures can support FAIR data principles in knowledge graph engineering for materials science.

[View on Zenodo](https://doi.org/10.5281/zenodo.19484380){:target="_blank"}


Recommended citation: Norouzi, Ebrahim, Beygi Nasrabadi, Hossein, Singh, Gunjan, Waitelonis, Jörg, Sack, Harald (2026). "The Materials Science and Engineering Knowledge Graph (MSE-KG): Apache Airflow–Orchestrated Construction Pipeline". Zenodo (Presentation). https://doi.org/10.5281/zenodo.19484380
