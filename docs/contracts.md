# Service and API contracts

## Artifact envelope

All stages exchange immutable artifacts: `{id, uri, mediaType, sha256, producerVersion, sourceRefs, createdAt}`. Paths are relative to a run package or are secure object-store URIs. A revision binds an exact MotionSpec hash and exact source hashes. Generated outputs never mutate inputs.

The [local preview run](runs.md) now writes relative artifact paths and verifies hashes before reuse. The broader multi-worker envelope below is still a design contract.

## Job envelope

Input: `{jobId, projectId, revisionId, stage, inputArtifacts, options, idempotencyKey}`. Output: `{status, artifacts, issues, metrics, workerVersion}`. `status` is `queued`, `running`, `succeeded`, `failed`, or `needs_review`. Issues have `{code, severity, message, sourceRefs, retryable}`. Idempotency is keyed by revision, stage, and input hashes.

## Stages

| Stage | Input | Output |
|---|---|---|
| `ingest` | Source artifacts | Evidence records with page/sheet/line/timecode, thumbnails, extracted tables |
| `interpret` | Evidence and user direction | Draft MotionSpec, conflicts, confidence |
| `validate` | MotionSpec | JSON Schema errors, semantic errors, provenance report |
| `plan` | Valid MotionSpec and target registry | Frame-indexed scene graph, capability report, asset requests |
| `assets` | Approved requests | Versioned asset manifest and media |
| `build` | Plan and assets | Native project artifacts, dependency list, build logs |
| `render` | Build artifacts and profiles | Frames, audio mix, preview/master |
| `qa` | Plan, sources, outputs | Machine report and review contact sheet |
| `package` | Approved outputs | Portable archive with relative links and manifest |

## REST API (future multi-user service)

| Method | Path | Result |
|---|---|---|
| POST | `/v1/projects` | New project ID |
| POST | `/v1/projects/{id}/sources` | Immutable source ID and hash |
| POST | `/v1/projects/{id}/revisions` | Draft MotionSpec revision |
| PUT | `/v1/projects/{id}/revisions/{rev}/spec` | Validated new revision; `If-Match` required |
| POST | `/v1/projects/{id}/revisions/{rev}/approve` | Approval tied to hash |
| POST | `/v1/projects/{id}/revisions/{rev}/jobs` | Stage job ID |
| GET | `/v1/jobs/{id}` | Status, issues, artifacts |
| GET | `/v1/projects/{id}/revisions/{rev}/artifacts` | Manifest |

The CLI uses the same stage names: `motion-engine ingest`, `validate`, `plan`, `render`, `build`, `qa`, `package` when implemented. At present `ingest`, `validate`, `inspect`, `plan`, `freeze`, a deterministic visual `render`, and an initial [QA gate](qa.md) exist. `freeze` creates a verified [revision manifest](revisions.md); CLI renders bind to it. The renderer outputs silent MP4/PNG previews for its supported primitives; native Adobe `build`, audio, full QA, and `package` remain future work. Future multi-user deployments need authentication, access control, signed artifact URLs, audit logs, and server-side provider credentials.
