# Feishu Bitable connector

Reads and appends records through the Feishu Bitable Open API. Supply a
tenant access token and optionally an injected transport for testing.

Supported URIs are `feishu://APP_TOKEN/TABLE_ID` and
`feishu_bitable://APP_TOKEN/TABLE_ID`. Reads preserve Feishu record IDs as
`_record_id`; writes support append semantics.

## Formula fields

Feishu Bitable formula fields are customized computed columns, distinct from
sheet-mode cell formulas. They use Feishu's provider-native `feishu-bitable`
language and bind an existing formula field by stable field identity:

```python
from open_table_connector.formulas import FieldFormulaTarget, FieldRef, FormulaExpression

table = client.open("feishu://APP_TOKEN/TABLE_ID").require_value()
margin = client.formulas(
    FieldFormulaTarget(table, FieldRef(name="gross_margin"))
).require_value()
margin.set(FormulaExpression("revenue - cost", "feishu-bitable"))
```

Before binding, callers must create or convert `gross_margin` to a formula
field through Feishu's provider-native administration. That prerequisite is
outside this v1 API: the Formula Extension has no field-create or
field-convert operation. Formula `set()` changes only the expression, verifies
a fresh metadata readback, and never writes calculated values into records.

`read_values()` obtains fresh provider-calculated values and preserves Feishu's
stable record IDs as `_record_id`, so IDs—not row positions—remain valid across
pagination and subsequent reads. Values have provider-dynamic dependencies:
upstream fields, linked data, or other Feishu state may change outside OTC,
and OTC does not evaluate or translate the native expression. Feishu exposes
field read, set, and value-read capabilities, but no explicit Formula
recalculation capability; use Feishu's own provider behavior when a refresh is
needed.

Ordinary record appends remain value writes and do not activate formula fields.
