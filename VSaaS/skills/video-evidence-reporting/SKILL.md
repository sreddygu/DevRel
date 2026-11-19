# VSaaS Video Evidence Reporting

Prepare a reviewable report from VSaaS event records without exporting raw video
or personally identifying content.

1. Identify the source database, event time range, target/backend context, and
   whether the data came from simulation, replay, or approved camera ingestion.
2. Use `python3 scripts/export_events_csv.py` only after approval to create a
   local CSV. Review it before sharing and remove camera identifiers, summaries,
   payloads, URLs, and any personal data not needed for the report.
3. If events must be replayed to a cloud API, run `python3 scripts/replay_events.py`
   only with explicit approval for the destination and data class.
4. Report commands, revision, environment, detector/backend, event count,
   exclusions, and redaction actions. Link to existing benchmark summaries
   rather than copying sensitive raw data.
5. Preserve provenance: label every claim as simulated, host-observed, or
   target-observed, and state any unobserved components as `unknown`.

This skill does not publish CSVs, upload event payloads, or generate reports
that expose video, credentials, private endpoints, or personal data.
