# Spreadsheet Operation Schemas

Generated from the built-in spreadsheet catalog. Regenerate with
`uv run --all-packages python scripts/generate_reference_manuals.py`.

These are static descriptors, not a promise of provider implementation.
Check bound workbook support, the [component manual](../user-guide/components.md), and
the [CLI manual](../user-guide/cli-manual.md). The generic SDK dispatcher implements a
subset; mutations there can return planned results without publishing.

| Operation | Version | Capability | Effects |
| --- | --- | --- | --- |
| `formula.set` | `1.0` | `spreadsheet.formula.set/1.0` | buffered_write |
| `image.delete` | `1.0` | `spreadsheet.image.insert/1.0` | buffered_write |
| `image.insert` | `1.0` | `spreadsheet.image.insert/1.0` | buffered_write |
| `image.list` | `1.0` | `spreadsheet.image.insert/1.0` | read |
| `image.read` | `1.0` | `spreadsheet.image.insert/1.0` | read |
| `range.alignment.read` | `1.0` | `spreadsheet.range.alignment.read/1.0` | read |
| `range.alignment.write` | `1.0` | `spreadsheet.range.alignment.write/1.0` | buffered_write |
| `range.border.read` | `1.0` | `spreadsheet.range.border.read/1.0` | read |
| `range.border.write` | `1.0` | `spreadsheet.range.border.write/1.0` | buffered_write |
| `range.clear` | `1.0` | `spreadsheet.range.clear/1.0` | buffered_write |
| `range.format` | `1.0` | `spreadsheet.range.format/1.0` | buffered_write |
| `range.merge` | `1.0` | `spreadsheet.range.merge/1.0` | buffered_write |
| `range.read` | `1.0` | `spreadsheet.range.read/1.0` | read |
| `range.sort` | `1.0` | `spreadsheet.range.sort/1.0` | buffered_write |
| `range.style` | `1.0` | `spreadsheet.range.style/1.0` | buffered_write |
| `range.style.read` | `1.0` | `spreadsheet.range.style.read/1.0` | read |
| `range.text_layout.read` | `1.0` | `spreadsheet.range.text_layout.read/1.0` | read |
| `range.text_layout.write` | `1.0` | `spreadsheet.range.text_layout.write/1.0` | buffered_write |
| `range.unmerge` | `1.0` | `spreadsheet.range.unmerge/1.0` | buffered_write |
| `range.write` | `1.0` | `spreadsheet.range.write/1.0` | buffered_write |
| `workbook.copy` | `1.0` | `spreadsheet.workbook.copy/1.0` | publish |
| `workbook.inspect` | `1.0` | `spreadsheet.workbook.inspect/1.0` | read |
| `workbook.reconcile` | `1.0` | `spreadsheet.workbook.verify/1.0` | session_control |
| `workbook.verify` | `1.0` | `spreadsheet.workbook.verify/1.0` | read |
| `workbook.write` | `1.0` | `spreadsheet.workbook.write/1.0` | publish |
| `worksheet.config` | `1.0` | `spreadsheet.worksheet.config/1.0` | buffered_write |
| `worksheet.config.read` | `1.0` | `spreadsheet.worksheet.config.read/1.0` | read |
| `worksheet.create` | `1.0` | `spreadsheet.worksheet.create/1.0` | buffered_write |
| `worksheet.delete` | `1.0` | `spreadsheet.worksheet.delete/1.0` | buffered_write |
| `worksheet.list` | `1.0` | `spreadsheet.worksheet.list/1.0` | read |
| `worksheet.move` | `1.0` | `spreadsheet.worksheet.move/1.0` | buffered_write |
| `worksheet.rename` | `1.0` | `spreadsheet.worksheet.rename/1.0` | buffered_write |

## formula.set

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      },
      "dialect": {
        "type": "string"
      },
      "expression": {
        "type": "string"
      }
    },
    "required": [
      "address",
      "expression"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.formula.set/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1",
      "expression": "=1+1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "formula.set",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## image.delete

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "picture_id": {
        "type": "string"
      }
    },
    "required": [
      "picture_id"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.image.insert/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "picture_id": "picture-1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "image.delete",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## image.insert

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "anchor": {
        "type": "string"
      },
      "content": {},
      "mime_type": {
        "type": "string"
      }
    },
    "required": [
      "content",
      "mime_type",
      "anchor"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.image.insert/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "anchor": "A1",
      "content": "",
      "mime_type": "image/png"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "image.insert",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## image.list

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.image.insert/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "image.list",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## image.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "picture_id": {
        "type": "string"
      }
    },
    "required": [
      "picture_id"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.image.insert/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "picture_id": "picture-1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "image.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.alignment.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.alignment.read/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.alignment.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.alignment.write

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.alignment.write/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.alignment.write",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.border.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.border.read/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.border.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.border.write

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.border.write/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.border.write",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.clear

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.clear/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.clear",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.format

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      },
      "kind": {
        "type": "string"
      },
      "pattern": {
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.format/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.format",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.merge

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.merge/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.merge",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.read/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.sort

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      },
      "key_column": {
        "minimum": 1,
        "type": "integer"
      },
      "reverse": {
        "type": "boolean"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.sort/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.sort",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.style

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      },
      "bold": {
        "type": "boolean"
      },
      "font_size": {
        "type": "number"
      },
      "italic": {
        "type": "boolean"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.style/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.style",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.style.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      },
      "fields": {
        "type": "array"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.style.read/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.style.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.text_layout.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.text_layout.read/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.text_layout.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.text_layout.write

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.text_layout.write/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.text_layout.write",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.unmerge

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "address"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.unmerge/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.unmerge",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## range.write

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "address": {
        "minLength": 1,
        "type": "string"
      },
      "values": {
        "type": "array"
      }
    },
    "required": [
      "address",
      "values"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.range.write/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "address": "A1",
      "values": [
        [
          1
        ]
      ]
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "range.write",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## workbook.copy

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "source": {
        "type": "string"
      },
      "title": {
        "type": "string"
      }
    },
    "required": [
      "source"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.workbook.copy/1.0",
  "effects": [
    "publish"
  ],
  "examples": [
    {
      "source": "file:///tmp/source.xlsx"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "workbook.copy",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## workbook.inspect

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.workbook.inspect/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "workbook.inspect",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## workbook.reconcile

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.workbook.verify/1.0",
  "effects": [
    "session_control"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "workbook.reconcile",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## workbook.verify

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "expected": {}
    },
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.workbook.verify/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "workbook.verify",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## workbook.write

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.workbook.write/1.0",
  "effects": [
    "publish"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "workbook.write",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.config

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.config/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.config",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.config.read

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "columns": {
        "type": "array"
      },
      "rows": {
        "type": "array"
      }
    },
    "required": [
      "rows",
      "columns"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.config.read/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {
      "columns": [],
      "rows": []
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.config.read",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.create

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "name": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "name"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.create/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "name": "Sheet1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.create",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.delete

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.delete/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.delete",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.list

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {},
    "required": [],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.list/1.0",
  "effects": [
    "read"
  ],
  "examples": [
    {}
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.list",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.move

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "index": {
        "minimum": 0,
        "type": "integer"
      }
    },
    "required": [
      "index"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.move/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "index": 0
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.move",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```

## worksheet.rename

```json
{
  "arguments_schema": {
    "additionalProperties": false,
    "properties": {
      "name": {
        "minLength": 1,
        "type": "string"
      }
    },
    "required": [
      "name"
    ],
    "type": "object"
  },
  "capability": "spreadsheet.worksheet.rename/1.0",
  "effects": [
    "buffered_write"
  ],
  "examples": [
    {
      "name": "Sheet1"
    }
  ],
  "limits": {
    "max_arguments_bytes": 16777216
  },
  "operation_id": "worksheet.rename",
  "result_schema": {},
  "schema": "otc.operation/1.0",
  "target_kind": "spreadsheet",
  "version": "1.0"
}
```
