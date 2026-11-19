# Agentic LLM Service for WiFi Connectivity Triage

An intelligent, agentic system that recreates the LogiQ tool's capability to "constantly determine tasks and dynamically create/call agents/LLMs to complete these tasks" for WiFi connectivity issue analysis.

## Architecture Overview

### Core Principles

1. **Dynamic Task Determination**: The Orchestrator analyzes inputs and determines which agents to spawn based on:
   - Anomaly type (DISCONNECT, DATA_STALL, BEACON_STUCK, FAIL_TO_CONNECT)
   - Available data (hostapd logs present vs absent)
   - Workflow priorities (hostapd-first approach)

2. **Agent Specialization**: Each agent has a focused responsibility and uses LLM calls via the preserved `generate_llm_response()` method

3. **Blackboard Pattern**: Agents communicate through a shared context, reading and writing findings

4. **Iterative Refinement**: The Orchestrator supports multiple rounds where agents can refine findings

5. **Workflow Adherence**: Follows the 9-step workflow with hostapd-first, KB/DB-first classification, and stats verification

## Components

### 1. Orchestrator (Master Agent)
**File**: `orchestrator.py`

The brain of the system that:
- Detects anomaly type from fd_logs
- Determines which agents to spawn dynamically
- Coordinates agent execution following workflow
- Supports refinement rounds for low-confidence results

**Key Methods**:
- `analyze()`: Main entry point
- `_determine_agent_plan()`: Dynamic task determination logic
- `_execute_workflow()`: Spawns and runs agents
- `_needs_refinement()`: Checks if refinement needed

### 2. Shared Context (Blackboard)
**File**: `shared_context.py`

Thread-safe storage for:
- **Findings**: Results from each agent
- **Cache**: Parsed logs, KB matches, stats to avoid redundant processing
- **Metadata**: Anomaly type, MAC address, etc.
- **Agent Status**: Track which agents are running/completed/failed

### 3. Specialized Agents

All agents inherit from `BaseAgent` which provides:
- `call_llm()`: Calls LLM via preserved `generate_llm_response()`
- `add_finding()`: Adds findings to shared context
- `run()`: Executes with retry logic (3 attempts)

#### HostapdParserAgent
**File**: `agents/hostapd_parser.py`

Extracts control-plane events:
- Authentication (SAE, Open, etc.)
- Association
- Deauthentication/Disassociation with reason codes
- EAPOL (4-way handshake)
- MLO link transitions
- SA Query

**Output**: Parsed events with timestamps, MAC addresses, event types, details

#### TimelineBuilderAgent
**File**: `agents/timeline_builder.py`

Creates chronological timeline:
- Sorts events by timestamp
- Calculates time deltas between events
- Identifies timing patterns (e.g., consistent ~1 second disconnects)

**Output**: Timeline with precise timestamps and deltas

#### KBMatcherAgent
**File**: `agents/kb_matcher.py`

Matches against knowledge base:
- Hostapd-first: Matches based on hostapd events, reason codes
- Searches KB for patterns matching anomaly type
- Uses LLM for deeper KB analysis

**Output**: Ranked KB matches with relevance scores

#### StatsAnalyzerAgent
**File**: `agents/stats_analyzer.py`

Analyzes wifistats:
- Parses wifistats sections
- Classifies stats as RAW vs rate-of-change using `RAW_STATS` set
- Identifies anomalies (high failure rates, retries, drops, poor RSSI)
- Uses LLM to analyze stats in context

**Output**: Parsed stats, classified stats, anomalies

#### RootCauseAgent
**File**: `agents/root_cause.py`

Formulates hypotheses:
- Synthesizes findings from all previous agents
- Uses LLM to formulate primary and secondary hypotheses
- Provides evidence for each hypothesis

**Output**: Root cause hypotheses with confidence levels

#### EvidenceCollectorAgent
**File**: `agents/evidence_collector.py`

Gathers supporting evidence:
- Collects evidence from timeline, KB matches, stats
- Organizes by root cause
- Provides file references and line numbers

**Output**: Evidence collection with sources

#### ConfidenceScorerAgent
**File**: `agents/confidence_scorer.py`

Assigns confidence levels based on workflow rules:
- **HIGH**: Hostapd + KB + Stats all present and aligned
- **MEDIUM**: Partial alignment (2 of 3 components)
- **LOW**: Missing critical components or contradictions

**Output**: Confidence scores with reasoning

#### MitigationAgent
**File**: `agents/mitigation.py`

Suggests actions:
- Immediate actions (low-risk)
- Verification steps (to confirm diagnosis)
- Escalation path (if issue persists)

**Output**: Prioritized mitigation recommendations

#### ReportGeneratorAgent
**File**: `agents/report_generator.py`

Produces final report in LogiQ format:
- Executive Summary
- Timeline Analysis
- Critical Findings
- Configuration Details
- Root Cause Hypothesis
- Recommended Actions
- Evidence Summary Table

**Output**: Formatted triage report

## Workflow

The system follows a 9-step workflow:

1. **Ingest logs** → Orchestrator loads inputs
2. **Cross-reference KB** → KBMatcher searches knowledge base
3. **Symptom summary** → TimelineBuilder creates event sequence
4. **Root cause** → RootCauseAgent formulates hypotheses
5. **Why it fits** → EvidenceCollector gathers supporting data
6. **Mitigation** → MitigationAgent suggests actions
7. **Open questions** → Identify missing data
8. **References** → Cite KB entries and log files
9. **Confidence** → ConfidenceScorer applies rules

## Dynamic Agent Spawning

### DISCONNECT Anomaly with Hostapd
```
HostapdParser → TimelineBuilder → KBMatcher → StatsAnalyzer → 
RootCause → EvidenceCollector → ConfidenceScorer → Mitigation → ReportGenerator
```

### DISCONNECT Anomaly without Hostapd
```
StatsAnalyzer → KBMatcher → RootCause → EvidenceCollector → 
ConfidenceScorer → Mitigation → ReportGenerator
```

### DATA_STALL or BEACON_STUCK
```
StatsAnalyzer → KBMatcher → RootCause → EvidenceCollector → 
ConfidenceScorer → Mitigation → ReportGenerator
```
(Adds HostapdParser + TimelineBuilder if hostapd available)

## Usage

### Basic Usage

```python
from agentic_service import Orchestrator

# Create orchestrator
orchestrator = Orchestrator(model="bedrock")

# Run analysis
report = orchestrator.analyze(
    fd_logs=fd_logs_content,
    hostapd_log=hostapd_content,  # Optional
    wifistats=wifistats_content,  # Optional
    knowledge_base=kb_content     # Optional
)

print(report)
```

### Command Line

```bash
cd agentic_service
python main.py
```

This will analyze the sample files and generate `triage_report.txt`.

## Input Files

1. **fd_logs** (Required): Fault detection notification file
   - Contains anomaly type, MAC address, iteration data
   - Example: `0_fd_logs.txt`

2. **hostapd_log** (Optional): Hostapd/syslog with control-plane events
   - Example: `syslog.txt`

3. **wifistats** (Optional): Rate-of-change wifistats
   - Example: `rate_of_change_wifistats.txt`

4. **knowledge_base** (Optional): WiFi connectivity knowledge base
   - Example: `knowledge_base.txt`

## Output

The system produces a structured triage report similar to LogiQ's output:

```
================================================================================
WiFi Connectivity Issue - Triage Report
Generated by Agentic LLM Service
Timestamp: 2026-02-04 16:42:00
================================================================================

1. Executive Summary
--------------------------------------------------------------------------------
Issue: STA fc:b3:bc:f0:b0:c2 is experiencing DISCONNECT on WiFi
Root Cause: Driver/firmware-initiated disconnections ~1 second after connection
Severity: High
Confidence: HIGH

2. Timeline Analysis
--------------------------------------------------------------------------------
[Timestamp] | [Delta] | [Event] | [Source]
...

3. Critical Findings
--------------------------------------------------------------------------------
Finding 1: Repeated Disconnection Events
  Multiple disconnect events observed...
  Evidence: Timeline shows 45 events

...

4. Root Cause Hypothesis
--------------------------------------------------------------------------------
Primary Hypothesis (HIGH):
  Firmware inactivity timer bug causing premature station removal
  Evidence: Consistent ~1 second timing, DEL_STATION before deauth...

...
```

## Key Features

### 1. Preserved Integration
- Uses existing `generate_llm_response()` from `model_calls.py`
- Uses existing `RAW_STATS` set for stat classification
- Compatible with existing infrastructure

### 2. Caching
- Parsed logs cached to avoid redundant processing
- KB matches cached for reuse
- Stats analysis cached

### 3. Error Handling
- Each agent retries up to 3 times on failure
- System continues even if individual agents fail
- Graceful degradation

### 4. Refinement
- Orchestrator detects low confidence results
- Re-runs KB matching and root cause analysis
- Supports up to 2 refinement rounds

## Comparison with LogiQ

| Feature | LogiQ | Agentic Service |
|---------|-------|-----------------|
| Dynamic task determination | ✓ | ✓ |
| Agent spawning | ✓ | ✓ |
| Workflow adherence | ✓ | ✓ |
| Hostapd-first approach | ✓ | ✓ |
| KB/DB-first classification | ✓ | ✓ |
| Stats verification | ✓ | ✓ |
| Confidence scoring | ✓ | ✓ |
| Structured output | ✓ | ✓ |
| Iterative refinement | ? | ✓ |

## Extension Points

### Adding New Agents

1. Create agent class inheriting from `BaseAgent`
2. Implement `analyze()` method
3. Add to `agents/__init__.py`
4. Update Orchestrator's `_determine_agent_plan()` and `_execute_workflow()`

### Adding New Anomaly Types

1. Update `_detect_anomaly_type()` in Orchestrator
2. Add agent plan in `_determine_agent_plan()`

### Customizing Workflow

Modify `_determine_agent_plan()` to change agent execution order or add conditional logic.

## Dependencies

- Python 3.8+
- Existing `model_calls.py` for LLM interface
- Threading support for shared context

## Future Enhancements

1. **Parallel Agent Execution**: Run independent agents concurrently
2. **Agent Communication**: Direct message passing between agents
3. **Learning**: Track which agent combinations work best for different anomaly types
4. **Visualization**: Generate timeline diagrams and flow charts
5. **API Interface**: REST API for integration with other systems

## License

Internal Qualcomm tool - Confidential
