# Authority boundary

The worker has no authority to edit code, choose architecture, diagnose root cause, mutate Git, deploy, or claim unobserved test success. Codex and the user retain those decisions.

There is no technical mechanism that prevents Codex from bypassing `ldw test parse` and reading pytest output directly: no hook, shell wrapper, or test-runner interception is installed or authorized. «гарантия advisory, действует только при вызове инструмента по промпту». The status-safety rules are architectural inside the worker once `ldw test parse` is invoked, but enforcing invocation itself requires a separate product decision by the user.
