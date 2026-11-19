# EdgeAgent Tool Contract Validation

Validate that a selected EdgeAgent transport produces the expected MCP client
configuration and fails clearly before any configuration is written.

1. Start from the selected transport and obtain connection details at runtime.
2. Run `devrel-agent preview --transport <transport>` with the corresponding
   options. Inspect only the generated transport shape; redact endpoint and
   authentication values before saving it.
3. Run `devrel-agent connect-test <transport>` with the same runtime settings.
   It must return a non-zero result on a failed connection.
4. Run `python -m pytest tests/test_cli.py tests/test_connection.py -q` from
   `devrel_runtime` to validate local command and connection behavior.
5. Record the transport type, command versions, preview schema result,
   connection result, and test result.

This skill does not run `devrel-agent install`, modify settings files, start a
remote server, or publish credentials. A failed probe is evidence of a failed
transport, not permission to retry with altered network or security settings.
