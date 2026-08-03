# Local Developer Worker rules

This repository is deterministic and no-network by default. Tools may read only explicitly supplied inputs and allowed repository roots. They must never edit source files, invoke mutating Git commands, read secret files, or emit raw sensitive content. Every factual claim must carry observable evidence or be reported as unknown, partial, or unsupported.

Test status must be established via ldw test parse. Reading pytest or other test-runner output directly to determine pass/fail is not permitted.
