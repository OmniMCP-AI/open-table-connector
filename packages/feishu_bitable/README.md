# Feishu Bitable connector

Reads and appends records through the Feishu Bitable Open API. Supply a
tenant access token and optionally an injected transport for testing.

Supported URIs are `feishu://APP_TOKEN/TABLE_ID` and
`feishu_bitable://APP_TOKEN/TABLE_ID`. Reads preserve Feishu record IDs as
`_record_id`; writes support append semantics.
