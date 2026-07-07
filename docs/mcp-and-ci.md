# MCP server and CI for grants

GrantKit is designed to be driven by agents and by continuous integration.
Both surfaces use the same stateless engine and return the same JSON.

## MCP server

Expose the engine to an AI agent over the Model Context Protocol. Install the
`mcp` extra and run the console script (stdio transport):

```bash
pip install "grantkit[mcp]"
grantkit-mcp
```

### Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `grant_check` | `path` | The `checks` structure (`errors`, `warnings`, `items`). |
| `grant_status` | `path` | The full `status.json` document. |
| `grant_build` | `path`, `format` | Output paths plus the `status.json` document. |

Each `path` is a directory containing `grant.yaml`. The server makes no AI or
network calls.

### Registering with Claude Code

```json
{
  "mcpServers": {
    "grantkit": { "command": "grantkit-mcp" }
  }
}
```

## CI for grants

A composite GitHub Action lints every push and publishes the review page and
`status.json` as build artifacts:

```yaml
# .github/workflows/grant.yml
name: Grant
on: [push, pull_request]
jobs:
  grantkit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: GrantKit/grantkit@v0.2.0
        with:
          path: .          # directory containing grant.yaml
          strict: "false"  # set "true" to fail on warnings too
```

The action runs `check --json` (captured, non-fatal), `build --share`, and
`status --json`, uploads `assembled.html`, `status.json`, and `check.json`, and
then enforces the result — errors always fail the job; warnings fail it only
under `strict: "true"`.

## The status.json contract

Both surfaces produce the same artifact the CLI does. Its exact shape — the
stable contract other tools depend on — is documented in
[artifacts](artifacts.md).
