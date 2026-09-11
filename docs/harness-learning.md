# Learn from work, then prove the improvement

WorkspaceAlberta connects three repositories: [procurement tools](https://github.com/HarleyCoops/WorkspaceAlberta), [terminal setup](https://github.com/HarleyCoops/workspaceAlbertaSetup), and [the working harness](https://github.com/HarleyCoops/workspacealberta-harness). The harness already describes local trajectories and an evolution loop. Those mechanisms are distinct from updating model weights.

## An experiment worth running

Start with one recurring task: turn a company's stated capabilities into a short, sourced list of public opportunities worth reading. Keep the original prompt, permitted tools, model identifier, harness revision and a frozen public evidence fixture fixed. Compare the existing workflow with one change: a clearer tool description, repaired argument handling, a shorter retrieval step, or an approved skill.

Score whether references and closing times match the source, whether the assistant preserves missing-data warnings, whether it invents qualifications, whether the handoff is usable, and how much time and cost the task takes. Include failures: unavailable providers, an empty search, expired deadlines, malformed tool arguments, denied access and text inside a document that tries to instruct the agent. Prefer evidence checks and human review over a model grading itself.

Keep an evaluation set separate from the sessions used to develop the change. Split by company, tender and task family so near-duplicate material does not leak into both. Compare against the baseline before promoting a change; retain the prior version for rollback. Track a factual business outcome separately from a model-quality score.

## Trace contract for a future training export

This is a proposed export contract, not an automatic exporter or a running RL pipeline.

| Field | Purpose |
|---|---|
| `run_id`, `parent_run_id`, `step_id` | Link work and handoffs using opaque IDs |
| `harness_revision`, `tool_schema_revision`, `model`, `provider_route` | Reproduce the environment |
| `tool_name`, `tool_call_id`, `status`, `latency_ms` | Diagnose execution and result pairing |
| `evidence_refs`, `artifact_refs`, `observed_at` | Locate authorized evidence without copying it into telemetry |
| `permission_scope`, `dataset_consent`, `redaction_review` | Establish whether material can be reused |
| `human_correction`, `acceptance_result` | Record observable feedback in a reviewed dataset |
| `reward_components`, `rubric_version`, `split` | Explain an experimental training target |

Local session records can contain sensitive material. Review retention, access and deletion before collecting them for an experiment. Remove credentials, personal details, customer attachments and proprietary terms from exports unless a specific approved dataset purpose requires them. Do not collect hidden model reasoning; use visible actions, evidence, outputs and corrections. A redaction filter alone does not create permission to train.

The hosted MCP's PostHog telemetry records usage metadata; it is not a transcript collection or training dataset. Do not expand its payload to collect prompts, profiles or tender attachments. Use a separate, deliberately approved dataset for research.

## What RL would require

An eligible model and training route, rights to the data, a reproducible environment, an explicit reward, a held-out evaluation and a rollback plan. Model licensing and provider training support must be checked before a run. The aim is better grounded decisions and fewer failed actions, not longer conversations or more tool calls. No training job is launched by this documentation.

The 60-day commercial experiment measures delivery and attributable earnings under a written agreement. It is not an RL benchmark, and private financial evidence must not become a training reward dataset by default.
