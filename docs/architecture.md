# Architecture

The CLI dispatches a bounded command to a deterministic tool. Each tool returns a `ToolResult` envelope. Evidence packages preserve source hashes and ranges; reports only render facts present in evidence. Policy is loaded before dispatch and denied capabilities return `policy_blocked`.

Judge is `future / not scheduled`; Context Packer remains an experiment.
