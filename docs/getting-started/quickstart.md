# Quickstart

This is the shortest path from a local CSV to a verified OTC result.

## 1. Create a source file

```console
cat > orders.csv <<'CSV'
order_id,customer,total
1001,ada,42.50
1002,grace,18.00
1003,linus,73.25
CSV
```

## 2. Inspect it

```console
otc inspect --from orders.csv --output-format json
```

Inspection reports the detected connector, schema, row count, source revision,
and credential-safe receipt facts.

## 3. Read it

```console
otc read --from csv://$(pwd)/orders.csv --output-format table
```

Use `csv://`, `excel://`, or `md://` when you want an explicit local format.
Use a bare path or `file://` when local format probing is desired.

## 4. Convert it

```console
otc convert \
  --from orders.csv \
  --to orders.jsonl \
  --output-format jsonl

otc read --from orders.jsonl --output-format json
```

`convert` reads the source once and writes a local destination. `import` is
the corresponding command for a writable connector destination.

## 5. Import it with an explicit conflict policy

```console
otc import \
  --from orders.csv \
  --to gsheets://SPREADSHEET_ID/Orders \
  --if-exists append
```

Provider credentials are resolved separately from the URI. See [Projects and
configuration](../user-guide/projects-and-config.md) before using a remote
connector.

## What happened

The CLI routed the source through the SDK when the installed provider supports
the normalized SDK surface. The result retained a physical receipt for the
source and, for a write, a destination receipt. Unsupported routes fail before
provider I/O where possible.

Continue with [First time series](first-timeseries.md) for the typed temporal
API, [OTC use cases](../user-guide/use-cases.md) for complete workflows, or
[CLI reference](../user-guide/cli.md) for all commands.
