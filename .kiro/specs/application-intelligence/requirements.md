# Requirements Document

Feature: Application Intelligence

## Introduction

Application Intelligence is the "brain" layer that elevates Leaka AI from a browser-test executor into an autonomous QA system that *understands* the applications it tests. Today, Leaka can autonomously explore an application and produce a flat list of discovered pages/forms/flows (`Application`, `ExploreRun`, `AppMapNode`). This spec defines the four pillars that turn that flat list into durable, compounding institutional knowledge:

1. **Application Graph** — a structured, versioned model of the application: pages, flows, forms, actions, user roles, dependencies between them, and each node's business risk. Not a flat list — a navigable graph with edges and semantics.
2. **Coverage Intelligence** — a rigorous, explainable mapping between the application graph and the user's test suite, answering "what is tested, what is not, and how confident are we."
3. **Memory** — durable, per-application learned knowledge that makes every subsequent explore/test run faster and more reliable: element fingerprints (DOM + ARIA + visual + text), preferred locator hierarchies, timing/flakiness knowledge, auth patterns, and historical outcomes. This is a genuine retrieval layer (embeddings + vector search), not a cache.
4. **PR Intelligence** — connect a code repository, ingest pull-request diffs, map changed code to affected application-graph nodes, and recommend the precise set of tests to run for a given change.

This is built to enterprise/institutional standard: multi-tenant isolation, versioning, auditability, graceful degradation, cost governance, and idempotency are first-class requirements, not afterthoughts. Where a capability genuinely requires heavier infrastructure (vector database, embeddings pipeline, background reconciliation), the requirement states it explicitly rather than defaulting to a shortcut.

### Scope boundaries
- **In scope:** the four pillars above and their supporting infrastructure (graph store, versioning, embeddings/vector retrieval, repo ingestion, diff→flow mapping, coverage engine, and the UI/API surface for all of them).
- **Out of scope (explicitly deferred to other specs):** the QA Brain planner/risk-execution engine, self-healing recovery, failure/flakiness intelligence, mobile/API execution fabric, RBAC/SSO/audit control plane. Application Intelligence produces the *inputs* these consume (e.g., risk scores, affected-flow lists) but does not implement them.

### Current-state baseline (what exists today)
- `Application` (owner-scoped: name, base_url, description, login_hint), `ExploreRun` (lifecycle + live steps), `AppMapNode` (flat page/form/flow with suggested_prompt).
- `explore_worker.explore_application` Celery task using browser-use `output_model_schema` structured output.
- Coverage is a naive heuristic computed on read in `GET /api/applications/{id}/map` (substring URL/label match against `TestCase`).
- Owner scoping via Supabase `sub`; `RUN_MODE=sync_demo` (in-process) or `celery` (Redis/Upstash); Postgres on Supabase.

## Glossary

- **Application Graph:** A directed, versioned graph whose nodes are application entities (pages, flows, forms, actions, roles) and whose edges express relationships (navigates-to, contains, requires-role, depends-on, part-of-flow).
- **Graph Node:** A discovered application entity with type, canonical identity, semantic metadata, and risk classification.
- **Graph Edge:** A typed, directed relationship between two nodes.
- **Graph Version / Snapshot:** An immutable, point-in-time capture of the full graph produced by a reconciliation, enabling diffing and audit ("what changed between explores").
- **Node Fingerprint:** A stable identity signal for a node/element composed of URL pattern, DOM structure signature, ARIA/role signature, visible-text signature, and (optionally) a visual embedding — used to re-identify the same entity across explores even when the UI changes.
- **Coverage:** The relationship between graph nodes and test cases, classified per node as covered / partially-covered / uncovered, with a confidence score and the evidence behind the classification.
- **Coverage Gap:** An uncovered or partially-covered node, prioritized by its risk classification.
- **Memory:** The durable per-application knowledge store: fingerprints, locator hierarchies, timing/flakiness observations, auth patterns, and prior outcomes, retrievable by semantic similarity and by identity.
- **Embedding:** A dense vector representation (of text and/or a rendered element/screenshot) used for semantic similarity retrieval.
- **Vector Store:** The persistence + similarity-search layer for embeddings (pgvector on the existing Postgres unless a dedicated store is justified).
- **Repository Connection:** A linked source-code repository (e.g., GitHub) associated with an Application, used for PR Intelligence.
- **Diff → Flow Mapping:** The engine that, given a code diff, predicts which application-graph nodes/flows are affected and therefore which tests should run.
- **Risk Classification:** A per-node label (Critical / High / Medium / Low / Trivial) with a numeric score and the factors that produced it.
- **Reconciliation:** The process of merging a new explore run's raw discoveries into the persistent graph — matching to existing nodes via fingerprints, adding new nodes, marking removed nodes, and producing a new snapshot.
- **Owner / Tenant:** The Supabase-authenticated user (`sub`) that owns an Application and all derived intelligence; the isolation boundary for every query.
- **Provenance:** For any derived fact (a node, an edge, a risk score, a coverage verdict), the record of which explore run / diff / model / heuristic produced it, so it is auditable and explainable.

---

## Requirements

### Requirement 1: Persistent, versioned Application Graph

**User Story:** As a QA lead, I want Leaka to maintain a durable, versioned graph of my application's pages, flows, forms, actions, and roles with the relationships between them, so that the platform accumulates a real model of my product over time rather than a throwaway list per explore.

#### Acceptance Criteria

1. THE system SHALL persist an Application Graph per Application consisting of typed nodes (page, flow, form, action, role) and typed directed edges (navigates_to, contains, requires_role, depends_on, part_of_flow).
2. WHERE a node is created, THE system SHALL assign it a stable canonical identity (a Node Fingerprint) that is independent of the `AppMapNode` row id, so the same entity retains identity across explore runs.
3. WHEN an explore run completes, THE system SHALL reconcile its raw discoveries into the persistent graph by matching each discovery to an existing node via fingerprint similarity above a configurable threshold, creating new nodes for unmatched discoveries, and marking previously-present nodes that were not re-observed as `stale` (not deleted).
4. WHEN reconciliation completes, THE system SHALL produce an immutable Graph Snapshot recording the full node/edge set at that point in time and the explore run that produced it.
5. THE system SHALL compute and expose a diff between any two Graph Snapshots of the same Application, reporting added nodes, removed/stale nodes, changed nodes (fingerprint or metadata drift), and added/removed edges.
6. IF two explore runs of the same Application produce overlapping discoveries, THEN reconciliation SHALL be idempotent with respect to identity — re-observing an unchanged entity SHALL NOT create a duplicate node.
7. THE system SHALL record Provenance on every node and edge (which explore run(s) observed it, when first seen, when last seen).
8. THE system SHALL scope every graph read and write to the authenticated owner; WHEN the requested resource's owner does not match the authenticated owner, THE system SHALL explicitly deny access and return 404 (never 403, never revealing existence).
9. WHERE the graph for an Application does not yet exist (no explore has run), THE system SHALL represent this as an explicit empty-graph state rather than an error.
10. THE system SHALL preserve graph history such that deleting or re-exploring never destroys prior snapshots; snapshots are append-only.

### Requirement 2: Node semantics, roles, and dependencies

**User Story:** As a QA lead, I want each node in the graph to carry rich semantic meaning — what it is, which user roles can reach it, what it depends on, and what business function it serves — so that downstream risk scoring, coverage, and test planning operate on meaning, not just URLs.

#### Acceptance Criteria

1. THE system SHALL classify each node with a `node_type` (page, flow, form, action, role) and a `business_category` (e.g., authentication, billing, checkout, onboarding, account, navigation, content, other) derived from the explore agent's structured output.
2. WHERE an application exposes multiple user roles (e.g., anonymous, standard user, admin), THE system SHALL represent each distinct role as a role node and SHALL attach `requires_role` edges ONLY from nodes for which there is explicit evidence of role restriction; WHERE role reachability is not evidenced, THE system SHALL label the node's role association as `unknown` and SHALL NOT fabricate a `requires_role` edge.
3. THE system SHALL capture dependency edges (`depends_on`) between nodes WHERE the explore evidence indicates one entity is a precondition of another (e.g., "checkout depends_on authenticated session", "apply-coupon depends_on cart-has-items").
3a. WHERE the system detects that a node likely has dependencies it could not confidently resolve, THE system SHALL flag the node with a `dependencies_incomplete` marker for optional human review, but SHALL NOT block risk scoring, coverage, or test planning on that review (missing dependencies degrade confidence, they do not halt the pipeline).
4. WHERE a multi-step flow is discovered, THE system SHALL represent it as a flow node with ordered `part_of_flow` edges to its constituent steps.
5. THE system SHALL store, per node, the raw evidence used to classify it (observed URL(s), key DOM/text signals, screenshots references) as Provenance for explainability.
6. IF the explore agent cannot confidently classify a node's business_category, THEN THE system SHALL label it `unknown` and SHALL NOT fabricate a category.
7. THE system SHALL allow an owner to manually correct a node's type, business_category, or role associations, and SHALL treat manual corrections as authoritative overrides that survive future reconciliations (a re-explore SHALL NOT silently revert a human correction).

### Requirement 3: Risk classification of graph nodes

**User Story:** As a QA lead, I want every flow and page scored for business risk (Critical → Trivial) with the reasoning shown, so that coverage gaps and test planning can be prioritized by what actually matters to revenue and users.

#### Acceptance Criteria

1. THE system SHALL assign each flow and page node a Risk Classification consisting of a categorical level (Critical, High, Medium, Low, Trivial) and a numeric score, with the contributing factors recorded.
2. THE system SHALL derive risk from at least: business_category (e.g., billing/checkout/auth weigh higher), position/centrality in the graph (nodes many flows depend on weigh higher), and role sensitivity (admin/destructive actions weigh higher).
3. WHERE additional risk signals are available (historical failure rate from Memory, traffic/importance hints supplied by the owner), THE system SHALL incorporate them into the score and SHALL record which signals were present.
4. THE system SHALL make every risk score explainable — for any node, the API SHALL return the factors and their contributions that produced the score.
5. THE system SHALL allow an owner to override a node's risk level, and SHALL persist the override with Provenance (who/when) so it is auditable and survives reconciliation.
6. WHEN the graph changes (reconciliation) or new signals arrive (a failed run, a manual override), THE system SHALL recompute affected risk scores and record the recomputation event.
7. THE risk model SHALL be strictly deterministic given identical inputs (same graph + same signals → same score), with NO randomness even for tie-breaking; ties SHALL be resolved by a stable, deterministic ordering rule (e.g., by canonical node identity). Different internal computation paths are acceptable PROVIDED identical inputs always produce identical outputs.

### Requirement 4: Coverage Intelligence

**User Story:** As a QA lead, I want a rigorous, explainable answer to "what parts of my application are tested, what aren't, and how confident are you," so that I can trust the coverage number and act on the biggest risks first.

#### Acceptance Criteria

1. THE system SHALL classify each graph node's coverage as one of: `covered`, `partially_covered`, or `uncovered`, and SHALL attach a confidence score and the evidence (which test cases/runs support the classification) to each verdict.
2. THE system SHALL determine coverage using stronger signals than substring matching — at minimum: (a) explicit linkage between a test case and a graph node, (b) URL/route correspondence between a test's target and a node, and (c) semantic similarity between the test's intent (prompt/name/assertions) and the node's semantics via embeddings.
3. WHERE a test case was generated from a specific graph node (via the "generate test" flow), THE system SHALL record an explicit, authoritative coverage link between that test and that node.
4. THE system SHALL compute Application-level and category-level coverage rollups (e.g., "Checkout: 80% of high-risk flows covered") weighted by risk, and SHALL expose them via API.
5. THE system SHALL produce a prioritized list of Coverage Gaps (uncovered/partially-covered nodes) ordered by risk, each with its suggested test prompt for one-click generation.
6. WHEN the graph changes or the test suite changes (test added/edited/deleted, run completed), THE system SHALL recompute affected coverage verdicts and reflect them without requiring a re-explore.
7. THE system SHALL distinguish "a test exists for this node" from "a test exists and is currently passing for this node," and coverage confidence SHALL account for recent pass/fail status. Confidence SHALL be a value in [0.0, 1.0]; pass/fail status influences the score but does not impose a fixed minimum threshold (a covered-but-failing node may legitimately carry lower confidence).
8. THE coverage classification SHALL be explainable — for any node, the API SHALL return why it was classified as covered/partial/uncovered and which evidence contributed.
9. IF a test case is linked to a node that later becomes `stale` in the graph, THEN THE system SHALL flag the link as `orphaned` for review rather than silently dropping it.

### Requirement 5: Memory — durable learned knowledge with semantic retrieval

**User Story:** As a QA lead, I want Leaka to remember what it has learned about my application — how to reliably locate elements, how long flows take, where auth is needed, what has failed before — so that every future run is faster, cheaper, and more reliable, and this knowledge becomes a compounding moat.

#### Acceptance Criteria

1. THE system SHALL maintain a durable per-Application Memory store containing, at minimum: element/node fingerprints, preferred locator hierarchies, observed timing characteristics (e.g., "checkout confirmation takes ~2.5s"), auth patterns, and historical outcome summaries per node/flow.
2. THE system SHALL generate and persist embeddings for memory items whose retrieval benefits from semantic similarity (e.g., element descriptions, flow intents, node semantics) and SHALL support similarity search over them (vector retrieval).
3. THE system SHALL use a vector-capable persistence layer for embeddings; WHERE the existing Postgres is used, it SHALL be via a vector extension (pgvector) rather than loading all vectors into application memory for scanning.
4. WHEN an explore or test run needs to locate a previously-seen entity, THE system SHALL retrieve the relevant memory (fingerprint + preferred locators) by identity and/or semantic similarity and make it available to the run.
5. WHEN a run observes new or updated knowledge about a node (a locator that worked, a new timing, a failure), THE system SHALL write it back to Memory with Provenance, so Memory improves monotonically over time.
5a. IF the Memory store is unavailable at write time, THEN THE system SHALL queue the knowledge updates durably and retry persistence until the store is available again, rather than discarding the learning; the in-flight run SHALL still complete.
6. THE system SHALL scope all Memory strictly to its owning Application and tenant; no memory item SHALL be retrievable across tenants.
7. WHERE a node's fingerprint drifts between explores (UI changed), THE system SHALL retain the prior fingerprint versions linked to the node's canonical identity, enabling intent-preserving re-identification and future self-healing (consumed by a later spec).
8. THE system SHALL bound Memory growth per Application via retention/compaction policy (e.g., keep the latest N fingerprint versions, summarize old timing observations) and SHALL make the policy configurable.
9. THE Memory retrieval path SHALL degrade gracefully: IF the embedding/vector backend is unavailable, THEN retrieval SHALL fall back to identity-based lookup and the run SHALL continue rather than fail.
10. THE system SHALL expose Memory contents for an Application via API/UI for transparency (what Leaka "knows"), scoped to the owner.
11. THE embeddings pipeline SHALL be cost-governed: THE system SHALL avoid re-embedding unchanged content (content-hash guard) and SHALL record embedding token/cost usage.

### Requirement 6: Repository connection and ingestion (PR Intelligence foundation)

**User Story:** As an engineering lead, I want to connect my source repository to a Leaka Application so that Leaka can understand code changes and relate them to my application's tested flows.

#### Acceptance Criteria

1. THE system SHALL allow an owner to connect a source repository (GitHub first) to an Application, storing the connection with credentials handled as secrets (never returned in plaintext by any read API).
2. THE system SHALL verify a repository connection at setup time (auth + repo reachability) and SHALL surface a clear connected/failed state with an actionable reason on failure.
3. THE system SHALL ingest pull-request / commit diffs for a connected repository, either via webhook (push/PR events) or on-demand fetch, and SHALL persist the changed file paths and change hunks needed for mapping.
4. THE system SHALL scope repository connections and ingested diffs atomically to BOTH the owning Application AND tenant — a resource SHALL be scoped to both or neither; partial scoping (tenant-only, application-only) SHALL never occur, including under error conditions.
5. IF repository ingestion fails (auth revoked, rate limit, network), THEN THE system SHALL record the failure with a classified reason and SHALL NOT corrupt or partially-write mapping state.
6. THE system SHALL treat all ingested code content as untrusted input and SHALL NOT execute it as part of the application's runtime. WHERE deeper structural analysis is required (e.g., AST parsing, dependency-graph extraction), THE system MAY perform static analysis and MAY use isolated/sandboxed interpretation that has no network, filesystem-write, or process-spawn access to the host; such analysis SHALL never run the ingested code against production or tenant systems.
7. WHERE webhook delivery is used, THE system SHALL authenticate webhook payloads (signature verification) and SHALL reject unauthenticated or replayed deliveries.

### Requirement 7: Diff → affected-flow mapping and test recommendation

**User Story:** As an engineering lead, when I open a pull request, I want Leaka to tell me exactly which application flows are affected and which tests to run, so that CI runs the right tests instead of everything or nothing.

#### Acceptance Criteria

1. WHEN a diff is ingested for a connected Application, THE system SHALL map changed code artifacts (files, routes, components) to affected Application Graph nodes/flows, producing a ranked list of affected flows with a confidence per mapping.
2. THE system SHALL base the mapping on explainable signals — at minimum: route/path correspondence, component-to-page association learned from Memory/graph, and semantic similarity between changed code identifiers and node semantics — and SHALL record which signals produced each mapping.
3. THE system SHALL translate affected flows into a recommended set of test cases to run, using the Coverage links from Requirement 4, and SHALL rank them by node risk.
4. WHERE an affected flow has NO covering test, THE system SHALL surface it as a "change with no coverage" warning (a high-value signal), including the suggested prompt to generate a test. WHERE coverage data exists but shows the flow is uncovered, this warning SHALL be high-confidence; WHERE coverage data is entirely unavailable for the Application, THE system SHALL still surface the affected flows but SHALL label the no-coverage determination as `undetermined` (coverage not yet computed) rather than asserting the flow is uncovered.
5. THE system SHALL expose the recommendation via API in a form consumable by the existing CI webhook path, so a PR can trigger exactly the recommended tests.
6. THE mapping SHALL be explainable end-to-end: for any recommended test, the API SHALL return the chain (changed file → affected node → covering test).
7. THE system SHALL distinguish an empty graph from a stale graph and handle them differently:
   - IF the graph is EMPTY (Application never successfully explored), THEN THE system SHALL return an explicit "no recommendations available — explore this application first" response rather than a fabricated conservative list.
   - IF the graph is STALE (previously explored but potentially out of date), THEN THE system SHALL degrade to a conservative recommendation (e.g., recommend all high-risk flows' tests), clearly labeled low-confidence with the reason, and SHALL suggest re-exploring.
8. THE recommendation computation SHALL be deterministic given identical graph + diff + coverage inputs.

### Requirement 8: User experience and workflow surface

**User Story:** As a user, I want a clear, first-class interface to explore my application, view its graph and risk, see coverage gaps, inspect what Leaka has learned, connect my repo, and act on PR recommendations, so that the intelligence is usable, not buried.

#### Acceptance Criteria

1. THE system SHALL present the Application Graph visually (nodes grouped by business_category and risk, edges navigable), not only as a flat list, and SHALL let the user drill into any node to see its semantics, risk explanation, coverage verdict, and memory.
2. THE system SHALL surface a prioritized Coverage Gaps view per Application with one-click "generate test" that pre-fills from the node's suggested prompt and records the authoritative coverage link (Req 4.3).
3. THE system SHALL display graph-change diffs between explore snapshots ("since last explore: 3 new flows, 1 removed, 2 changed").
4. THE system SHALL provide a repository-connection UI with connected/failed status and, once connected, a view of recent PRs/diffs and their affected-flow + recommended-test output.
5. WHILE an explore or reconciliation is running, THE system SHALL show live progress (reusing the existing polling pattern) and SHALL not present a stale graph as current.
6. THE system SHALL show Memory transparency ("what Leaka knows about this app") in a human-readable form.
7. THE UI SHALL never expose secrets (repo tokens, credentials) and SHALL never expose another tenant's data.
8. All new API calls from the browser SHALL authenticate as the logged-in user via the existing Bearer-token path and SHALL work through the existing Vercel→backend rewrite.

### Requirement 9: Multi-tenancy, security, and isolation

**User Story:** As a platform operator, I want every piece of Application Intelligence rigorously tenant-isolated and secure, so that no customer's graph, memory, code, or coverage can ever leak to another.

#### Acceptance Criteria

1. THE system SHALL scope every Application Intelligence resource (graph nodes, edges, snapshots, memory items, embeddings, repo connections, diffs, recommendations) to the owning tenant via `owner_id`, and SHALL enforce the scope on every read and write.
2. WHEN a resource is requested by a non-owner, THE system SHALL respond as if it does not exist (404), never revealing existence or contents.
3. THE system SHALL enforce, as an absolute system-wide policy independent of whether any secret is currently stored, that no secret is ever returned in plaintext through a read API and no secret is ever shipped to the browser; repository credentials and any other secrets SHALL be stored via a secrets mechanism honoring this policy.
4. THE system SHALL treat all externally-sourced content (explored page content, ingested code, webhook payloads) as untrusted and SHALL neither execute it nor allow it to alter control flow (prompt-injection-aware handling of page/code text fed to the LLM).
5. THE system SHALL authenticate and verify integrity of inbound webhooks and SHALL reject unauthenticated, malformed, or replayed events.
6. THE system SHALL record an audit trail for security-relevant Application Intelligence actions (repo connected/disconnected, secret set, manual override applied) sufficient for later enterprise audit consumption.

### Requirement 10: Reliability, cost governance, and graceful degradation

**User Story:** As a platform operator, I want Application Intelligence to be reliable and cost-bounded under real load — long explores, large graphs, embedding costs, LLM/vector outages — so that it is production-grade, not a demo.

#### Acceptance Criteria

1. THE system SHALL run all long-running Application Intelligence work (explore, reconciliation, embedding, diff mapping) asynchronously via the existing dispatch mechanism (Celery in production, sync_demo locally) and SHALL never block an HTTP request on this work.
2. WHEN any long-running job fails, THE system SHALL persist a classified, human-readable failure reason (reusing the existing error-classification approach) and SHALL leave prior good state intact (no partial-write corruption of the graph, memory, or coverage). IF the failure-classification step itself fails, THEN THE system SHALL still record the failure with a safe generic reason and preserved prior state; a classification failure SHALL NOT escalate into state corruption, and the job SHALL still be recorded as failed.
3. THE system SHALL make reconciliation, embedding, and mapping idempotent so that retries or duplicate events do not create duplicate or conflicting state.
4. IF the LLM provider, embedding backend, or vector store is unavailable, THEN THE affected feature SHALL degrade gracefully (identity-only retrieval, conservative recommendation, deferred embedding) and SHALL surface the degraded state rather than failing hard.
5. THE system SHALL govern LLM and embedding cost: avoid redundant model calls (content-hash guards, caching), record per-operation token/cost usage, and expose it for observability.
6. THE system SHALL bound resource use for large applications. All list-style graph/coverage/memory endpoints SHALL support pagination and SHALL apply it consistently regardless of current size (pagination is always available, not only when approaching caps), so client behavior does not change as data grows; responses SHALL never be unbounded.
7. THE system SHALL be safe against concurrent explores/reconciliations of the same Application (locking or serialization) so two runs cannot corrupt the shared graph.
8. THE system SHALL preserve backward compatibility with the existing `Application` / `ExploreRun` / `AppMapNode` data and endpoints during migration; existing explored applications SHALL continue to function and SHALL be upgradeable into the new graph model without data loss.

### Requirement 11: Data model migration and integration with existing system

**User Story:** As the engineering owner, I want the new intelligence layer to integrate cleanly with the existing execution platform and migrate existing data safely, so that we build on the foundation instead of forking it.

#### Acceptance Criteria

1. THE system SHALL introduce the new persistence (graph nodes/edges, snapshots, memory, embeddings, repo connections, diffs) as additive schema changes applied via an idempotent migration against the shared Postgres, without dropping or breaking existing tables.
2. THE system SHALL provide a one-time backfill that upgrades existing `AppMapNode` rows for already-explored Applications into graph nodes, preserving their labels, urls, descriptions, and suggested prompts.
3. THE existing `explore_worker` SHALL be extended (not replaced) so that a completed explore feeds reconciliation into the graph, while its current behavior (writing `AppMapNode`, live steps, status) remains intact until fully superseded.
4. THE existing coverage heuristic in `GET /api/applications/{id}/map` SHALL be superseded by the Coverage Intelligence engine (Req 4) in a way that keeps the endpoint's consumers working (same or compatibly-extended response shape).
5. THE existing "generate test" flow SHALL be extended to record the authoritative coverage link (Req 4.3) without breaking its current pre-fill behavior.
6. All new work SHALL respect the existing deployment reality: Supabase Postgres shared between local and Azure, `RUN_MODE` dispatch, and the Vercel client→backend rewrite.
