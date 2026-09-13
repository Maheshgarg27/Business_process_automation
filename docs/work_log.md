# Work Log

## Day 1 — Dataset Understanding and Exploration

### Objective

Understand the structure of Dataset A and Dataset B and determine what information is available for business-process discovery and execution segmentation.

### Work Completed

- Inspected the directory structure of Dataset A and Dataset B.
- Analyzed sessions, chunks, events, and event layers.
- Examined event-type distributions in both datasets.
- Analyzed application usage and application transitions.
- Studied Dataset A ground-truth process executions.
- Analyzed process execution frequencies and variants.
- Analyzed execution durations.
- Examined executions that continue across recording chunks.
- Explored Dataset B session durations and event timing.
- Examined screenshot events and available screenshot files.
- Investigated extracted text availability in screenshot events.

### Key Findings

- Dataset A contains ground-truth information about process executions and variants.
- Dataset B does not contain ground-truth process labels.
- A session represents a continuous recording, while a chunk is a recording bucket and is not necessarily a business-process boundary.
- Dataset B therefore requires execution segmentation and process discovery from the raw activity logs.
- Event-to-event temporal gaps may provide a useful signal for identifying execution boundaries, but a time gap alone is not sufficient.
- Dataset A and Dataset B have the same general event-log structure but differ in the processes, departments, and applications represented.

### Initial Direction

Use Dataset A to study general behavioral signals associated with execution boundaries and validate the approach using its ground truth. The resulting general approach should then be applied to Dataset B, where executions and process labels must be discovered.

### Next Step

Investigate and develop an execution-segmentation approach using the ground truth available in Dataset A.