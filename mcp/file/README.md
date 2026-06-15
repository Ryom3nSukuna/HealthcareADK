# mcp-file

MCP server that reads and writes project text files on behalf of HealthcareADK agents.

## Security model

- **Extension allowlist:** only `.sql`, `.tmdl`, `.csv`, `.json`, `.md`, `.py` are permitted.
- **Project root containment:** all paths are resolved under the project root; `..` traversal is blocked.

## Setup

```bash
pip install -r mcp/file/requirements.txt
```

## Tools

| Tool | Signature | Purpose |
| --- | --- | --- |
| `read_file` | `(path)` | Read a text file; path relative to project root |
| `write_file` | `(path, content)` | Write/overwrite a file; creates parent dirs as needed |
| `list_files` | `(directory=".", extension=None)` | List files recursively; optional extension filter |
| `append_file` | `(path, content)` | Append to a file; creates it if it doesn't exist |

All tools return `{"content"/"written"/"appended"/"files": ...}` on success, or `{"error": str}` on failure.

## Examples

```
read_file("sql/08_etl_stg_to_dw.sql")
write_file("powerbi/tmdl/tables/_Measures.tmdl", "<updated tmdl content>")
list_files("powerbi/tmdl", ".tmdl")
list_files("sql", ".sql")
append_file("landing_zone/claims/new_claims.csv", "row1,col2,...\n")
```

## Primary use cases

| Agent | Read | Write |
|---|---|---|
| ETLAgent | `sql/` stored procedures | Updated SP logic |
| ReportingAgent | `powerbi/tmdl/` TMDL files | Updated measures, columns |
