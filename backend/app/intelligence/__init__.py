"""
Application Intelligence — pure, testable engines.

Modules in this package are deliberately I/O-free where possible (pure
functions: input data → output data). Workers and the API layer perform the
DB / LLM / network I/O and call these engines. This keeps the deterministic and
explainable requirements directly unit- and property-testable.

Package contents (built incrementally per the spec task list):
  - embeddings.py     : provider-agnostic embedding service + dedup cache
  - fingerprint.py    : node fingerprint / canonical identity  (Layer 1)
  - reconciliation.py : merge discoveries into the graph        (Layer 1)
  - risk.py           : deterministic risk scoring              (Layer 2)
  - coverage.py       : multi-signal coverage classification    (Layer 2)
  - mapping.py        : diff → affected-flow → recommended tests (Layer 4)
"""
