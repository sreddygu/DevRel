# VSaaS Synapse Skill Catalog

VSaaS turns private edge-video events into searchable insights. It uses the
shared `p3-device` profile; these skills cover ingestion, model validation, and
privacy-aware evidence reporting.

| Layer | ID | Use when | Default outcome |
| --- | --- | --- | --- |
| Domain | [`video-stream-ingestion`](video-stream-ingestion/SKILL.md) | Starting simulated or approved camera ingestion | A scoped event-ingestion record |
| Domain | [`vision-model-validation`](vision-model-validation/SKILL.md) | Checking ONNX/QNN vision behavior | A target-labeled detector validation result |
| Domain | [`video-evidence-reporting`](video-evidence-reporting/SKILL.md) | Preparing evidence from stored event records | A redacted, provenance-preserving report |

Never commit video, camera credentials, RTSP URLs, personal data, raw event
payloads, or private cloud endpoints as evidence.
