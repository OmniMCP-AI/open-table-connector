# CLI Option Inventory

Generated from `build_parser()`; includes every command, positional, flag,
choice, and parser default. Regenerate with
`uv run --all-packages python scripts/generate_reference_manuals.py`.

The [CLI manual](../user-guide/cli-manual.md) documents execution semantics and current
limitations. Parser acceptance alone does not mean an operation commits.

## otc

```text
usage: otc [-h] [--version]
           {list,inspect,read,convert,import,help,capabilities,spreadsheet,artifact}
           ...
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--version` | no | `-` |  | show program's version number and exit |

## otc list

```text
usage: otc list [-h] [--output-format {csv,json,jsonl,table}]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--output-format` | no | `'jsonl'` | csv, json, jsonl, table |  |

## otc inspect

```text
usage: otc inspect [-h] --from SOURCE [--to DESTINATION]
                   [--from-format {auto,csv,excel,json,jsonl,table}]
                   [--output-format {csv,json,jsonl,table}]
                   [--if-exists {append,replace,error}] [--limit LIMIT]
                   [--timeout TIMEOUT] [--sheet SHEET] [--range RANGE]
                   [--field-name FIELD_NAME] [--credential-key CREDENTIAL_KEY]
                   [--target TARGET]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--from` | yes | `None` |  |  |
| `--to` | no | `None` |  |  |
| `--from-format` | no | `None` | auto, csv, excel, json, jsonl, table |  |
| `--output-format` | no | `'jsonl'` | csv, json, jsonl, table |  |
| `--if-exists` | no | `'error'` | append, replace, error |  |
| `--limit` | no | `None` | int |  |
| `--timeout` | no | `None` | float |  |
| `--sheet` | no | `None` |  |  |
| `--range` | no | `None` |  |  |
| `--field-name` | no | `None` |  |  |
| `--credential-key` | no | `[]` |  |  |
| `--target` | no | `None` |  |  |

## otc read

```text
usage: otc read [-h] --from SOURCE [--to DESTINATION]
                [--from-format {auto,csv,excel,json,jsonl,table}]
                [--output-format {csv,json,jsonl,table}]
                [--if-exists {append,replace,error}] [--limit LIMIT]
                [--timeout TIMEOUT] [--sheet SHEET] [--range RANGE]
                [--field-name FIELD_NAME] [--credential-key CREDENTIAL_KEY]
                [--target TARGET]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--from` | yes | `None` |  |  |
| `--to` | no | `None` |  |  |
| `--from-format` | no | `None` | auto, csv, excel, json, jsonl, table |  |
| `--output-format` | no | `'jsonl'` | csv, json, jsonl, table |  |
| `--if-exists` | no | `'error'` | append, replace, error |  |
| `--limit` | no | `None` | int |  |
| `--timeout` | no | `None` | float |  |
| `--sheet` | no | `None` |  |  |
| `--range` | no | `None` |  |  |
| `--field-name` | no | `None` |  |  |
| `--credential-key` | no | `[]` |  |  |
| `--target` | no | `None` |  |  |

## otc convert

```text
usage: otc convert [-h] --from SOURCE --to DESTINATION
                   [--from-format {auto,csv,excel,json,jsonl,table}]
                   [--output-format {auto,csv,excel,json,jsonl,table}]
                   [--to-format {auto,csv,excel,json}]
                   [--if-exists {append,replace,error}] [--limit LIMIT]
                   [--timeout TIMEOUT] [--sheet SHEET] [--range RANGE]
                   [--field-name FIELD_NAME] [--credential-key CREDENTIAL_KEY]
                   [--target TARGET]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--from` | yes | `None` |  |  |
| `--to` | yes | `None` |  |  |
| `--from-format` | no | `None` | auto, csv, excel, json, jsonl, table |  |
| `--output-format` | no | `None` | auto, csv, excel, json, jsonl, table |  |
| `--to-format` | no | `None` | auto, csv, excel, json |  |
| `--if-exists` | no | `'error'` | append, replace, error |  |
| `--limit` | no | `None` | int |  |
| `--timeout` | no | `None` | float |  |
| `--sheet` | no | `None` |  |  |
| `--range` | no | `None` |  |  |
| `--field-name` | no | `None` |  |  |
| `--credential-key` | no | `[]` |  |  |
| `--target` | no | `None` |  |  |

## otc import

```text
usage: otc import [-h] --from SOURCE --to DESTINATION
                  [--from-format {auto,csv,excel,json,jsonl,table}]
                  [--output-format {csv,json,jsonl,table}]
                  [--if-exists {append,replace,error}] [--limit LIMIT]
                  [--timeout TIMEOUT] [--sheet SHEET] [--range RANGE]
                  [--field-name FIELD_NAME] [--credential-key CREDENTIAL_KEY]
                  [--target TARGET]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--from` | yes | `None` |  |  |
| `--to` | yes | `None` |  |  |
| `--from-format` | no | `None` | auto, csv, excel, json, jsonl, table |  |
| `--output-format` | no | `'jsonl'` | csv, json, jsonl, table |  |
| `--if-exists` | no | `'error'` | append, replace, error |  |
| `--limit` | no | `None` | int |  |
| `--timeout` | no | `None` | float |  |
| `--sheet` | no | `None` |  |  |
| `--range` | no | `None` |  |  |
| `--field-name` | no | `None` |  |  |
| `--credential-key` | no | `[]` |  |  |
| `--target` | no | `None` |  |  |

## otc help

```text
usage: otc help [-h] [--output-format {json,table}] namespace [operation_id]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `namespace` | yes | `None` |  |  |
| `operation_id` | no | `None` |  |  |
| `--output-format` | no | `'table'` | json, table |  |

## otc capabilities

```text
usage: otc capabilities [-h] --uri URI [--sheet SHEET]
                        [--output-format {json,table}]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `--uri` | yes | `None` |  |  |
| `--sheet` | no | `None` |  |  |
| `--output-format` | no | `'table'` | json, table |  |

## otc spreadsheet

```text
usage: otc spreadsheet [-h] --uri URI [--commands COMMANDS]
                       [--operation OPERATION] [--arguments ARGUMENTS]
                       [--sheet SHEET] [--range RANGE] [--pattern PATTERN]
                       [--bold] [--no-bold] [--italic] [--no-italic]
                       [--values-file VALUES_FILE] [--values VALUES]
                       [--name NAME] [--fields FIELDS] [--rows ROWS]
                       [--columns COLUMNS] [--view-fields VIEW_FIELDS]
                       [--create]
                       [--profile {general/1.0,literal-artifact/1.0,rich-artifact/1.0}]
                       [--dry-run] [--allow-partial] [--expected EXPECTED]
                       [--expected-revision EXPECTED_REVISION]
                       [--idempotency-key IDEMPOTENCY_KEY]
                       [--failure-directory FAILURE_DIRECTORY]
                       [--selectors SELECTORS] [--spec SPEC]
                       [--allow-incomplete] [--credential-key CREDENTIAL_KEY]
                       {batch,operation,read,style-read,config-read,verify,inspect,style,format,write,worksheet,recipe,apply}
                       [{create,rename,delete,export}] [{export}]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `action` | yes | `None` | batch, operation, read, style-read, config-read, verify, inspect, style, format, write, worksheet, recipe, apply |  |
| `worksheet_action` | no | `None` | create, rename, delete, export |  |
| `recipe_action` | no | `None` | export |  |
| `--uri` | yes | `None` |  |  |
| `--commands` | no | `None` |  | version 1.0 JSON command file |
| `--operation` | no | `None` |  | existing spreadsheet operation verb |
| `--arguments` | no | `'{}'` |  | operation arguments as JSON |
| `--sheet` | no | `None` |  |  |
| `--range` | no | `None` |  |  |
| `--pattern` | no | `None` |  |  |
| `--bold` | no | `None` | boolean flag |  |
| `--no-bold` | no | `False` | boolean flag |  |
| `--italic` | no | `None` | boolean flag |  |
| `--no-italic` | no | `False` | boolean flag |  |
| `--values-file` | no | `None` |  |  |
| `--values` | no | `None` |  |  |
| `--name` | no | `None` |  |  |
| `--fields` | no | `None` |  | style fields as a JSON array |
| `--rows` | no | `None` |  | row numbers as a JSON array |
| `--columns` | no | `None` |  | column letters as a JSON array |
| `--view-fields` | no | `None` |  | view fields as a JSON array |
| `--create` | no | `False` | boolean flag |  |
| `--profile` | no | `None` | general/1.0, literal-artifact/1.0, rich-artifact/1.0 |  |
| `--dry-run` | no | `False` | boolean flag |  |
| `--allow-partial` | no | `False` | boolean flag |  |
| `--expected` | no | `None` |  | retained independent expected intent JSON file |
| `--expected-revision` | no | `None` |  |  |
| `--idempotency-key` | no | `None` |  |  |
| `--failure-directory` | no | `None` |  |  |
| `--selectors` | no | `None` |  |  |
| `--spec` | no | `None` |  |  |
| `--allow-incomplete` | no | `False` | boolean flag |  |
| `--credential-key` | no | `[]` |  |  |

## otc artifact

```text
usage: otc artifact [-h] [--from FROM_VALUE] [--to TO_VALUE]
                    [--mode {html,screenshot,text,outline,stats,issues}]
                    [--uri URI] [--session SESSION]
                    [--output-format {json,table}]
                    {export,view,watch} [{start,status,refresh,stop}]
```

| Argument | Required | Default | Choices/type | Help |
| --- | --- | --- | --- | --- |
| `-h, --help` | no | `-` |  | show this help message and exit |
| `action` | yes | `None` | export, view, watch |  |
| `watch_action` | no | `None` | start, status, refresh, stop |  |
| `--from` | no | `None` |  |  |
| `--to` | no | `None` |  |  |
| `--mode` | no | `None` | html, screenshot, text, outline, stats, issues |  |
| `--uri` | no | `None` |  |  |
| `--session` | no | `None` |  |  |
| `--output-format` | no | `'json'` | json, table |  |
