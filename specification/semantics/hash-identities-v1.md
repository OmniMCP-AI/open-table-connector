# v1 compatibility hash identities

The compatibility record uses `sha256:` followed by lowercase hexadecimal. Its
fixture manifest lists repository-relative UTF-8 paths one per line. Blank and
comment lines are ignored; the remaining paths are sorted lexically and must be
regular files below the repository root. Each entry contributes
`len(path):path + len(bytes):bytes` to one SHA-256 stream, where `path` is the
UTF-8 path and `bytes` are the file's unmodified bytes. The path list and file
bytes are therefore part of the v1 compatibility identity.

Provider evidence hashes are separate SHA-256 hashes of the raw JSON bytes for
the corresponding provider evidence document. Commit fields in the YAML record
identify source surfaces and are not included in either content hash.
