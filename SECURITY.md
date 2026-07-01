# Security

AgentRunbook can run local commands only when all of these are true:

- The runbook contains an explicit `[tools.shell]` allowlist.
- The command head matches that allowlist.
- The user passes `--allow-shell`.

Without `--allow-shell`, shell steps are dry-run and still appear in the trace.

Do not run untrusted runbooks with `--allow-shell`. HTTP and model-provider steps can send data over the network, so review runbook context before using sensitive inputs.

To report a security issue, open a private advisory on GitHub or contact the repository owner.
