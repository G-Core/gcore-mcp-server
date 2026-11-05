"""Operations that upload a file: the model passes a local path, not the bytes.

The SDK takes file contents (``fastedge.binaries.create(body=...)``). Through a
tool call, that would mean the whole file as text in the model's context: an
11 MB Wasm app is ~15 MB of base64, which doesn't fit, so models went around
the server to upload it themselves. Here the parameter takes a path instead and
the server reads the file.

A path lets a model point at any file the server can read, so each upload
names the kind of file it takes and the file must start with that kind's
signature: a WebAssembly upload can only ever send a WebAssembly binary, never
a key or a config file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Union, get_args, get_origin

from fastmcp.exceptions import ToolError


@dataclass(frozen=True)
class Upload:
    kind: str
    magic: bytes
    max_bytes: int


MB = 1024 * 1024

# Operation -> what its file parameter takes. An SDK operation with a file
# parameter that isn't listed here can't be called (see test_catalog).
UPLOADS: Final[dict[str, Upload]] = {
    # The API's own limit is 100 MB.
    "fastedge.binaries.create": Upload(
        "a compiled WebAssembly binary (.wasm)", b"\0asm", 100 * MB
    ),
}


def is_file_param(annotation: Any) -> bool:
    """The SDK parameter takes file contents (``FileContent``: bytes, IO, path)."""
    if annotation is os.PathLike or get_origin(annotation) is os.PathLike:
        return True
    if get_origin(annotation) is Union or type(annotation).__name__ == "UnionType":
        return any(is_file_param(a) for a in get_args(annotation))
    return False


def describe(operation: str) -> str:
    upload = UPLOADS.get(operation)
    what = upload.kind if upload else "the file"
    return (
        f"Path of a local file: {what}. The server reads and uploads it, so its "
        "contents never pass through the conversation. Prefer an absolute path."
    )


def open_upload(operation: str, value: Any) -> Path:
    """Check ``value`` names a file this operation may upload; return its path."""
    upload = UPLOADS.get(operation)
    if upload is None:
        raise ToolError(f"{operation}: file uploads aren't supported for it here.")
    if not isinstance(value, str) or not value.strip():
        raise ToolError(
            f"{operation}: pass the path of a local file ({upload.kind}), "
            "not its contents."
        )
    path = Path(value.strip()).expanduser()
    try:
        path = path.resolve(strict=True)
    except OSError:
        raise ToolError(f"{operation}: no such file: {path}.") from None
    if not path.is_file():
        raise ToolError(f"{operation}: {path} is not a file.")
    size = path.stat().st_size
    if size > upload.max_bytes:
        raise ToolError(
            f"{operation}: {path} is {size / MB:.1f} MB; the limit is "
            f"{upload.max_bytes // MB} MB."
        )
    with path.open("rb") as f:
        head = f.read(len(upload.magic))
    if head != upload.magic:
        raise ToolError(
            f"{operation}: {path} is not {upload.kind}; only that kind of file "
            "can be uploaded with it."
        )
    return path
