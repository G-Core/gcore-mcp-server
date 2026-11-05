"""File uploads take a local path; only the kind of file the operation takes."""

from __future__ import annotations

import inspect
from pathlib import Path

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from gcore_mcp_server.catalog import uploads

from tests.helpers import BASE_URL, full_catalog

pytestmark = pytest.mark.anyio

WASM = b"\0asm\x01\0\0\0" + b"\0" * 64


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _entry():
    entry = full_catalog().resolve("fastedge.binaries.create")
    assert entry is not None
    return entry


def test_upload_takes_a_path_not_contents() -> None:
    entry = _entry()
    body = entry.input_schema["properties"]["body"]
    assert body["type"] == "string"
    assert "Path of a local file" in body["description"]
    assert "WebAssembly" in body["description"]


def test_every_file_parameter_has_an_upload_rule() -> None:
    """A new SDK upload must say what kind of file it takes before it works."""
    unlisted = []
    for entry in full_catalog().entries:
        params = entry.input_schema.get("properties", {})
        if (
            any(
                "Path of a local file" in str(p.get("description", ""))
                for p in params.values()
            )
            and entry.name not in uploads.UPLOADS
        ):
            unlisted.append(entry.name)
    assert not unlisted


async def test_wasm_file_is_uploaded_from_disk(tmp_path: Path) -> None:
    app = tmp_path / "app.wasm"
    app.write_bytes(WASM)
    with respx.mock(base_url=BASE_URL) as mock:
        route = mock.post("/fastedge/v1/binaries/raw").mock(
            return_value=httpx.Response(
                200, json={"id": 7, "api_type": "wasi-http", "status": 1}
            )
        )
        result = await _entry().adapter.validate_python({"body": str(app)})
    assert route.called
    assert route.calls[0].request.content == WASM
    assert result.id == 7


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"-----BEGIN OPENSSH PRIVATE KEY-----", "is not a compiled WebAssembly"),
        (b"", "is not a compiled WebAssembly"),
    ],
)
async def test_other_files_are_refused(
    tmp_path: Path, content: bytes, message: str
) -> None:
    secret = tmp_path / "id_ed25519"
    secret.write_bytes(content)
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as mock:
        route = mock.post("/fastedge/v1/binaries/raw")
        with pytest.raises(ToolError, match=message):
            await _entry().adapter.validate_python({"body": str(secret)})
    assert not route.called


async def test_contents_or_missing_paths_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="no such file"):
        uploads.open_upload("fastedge.binaries.create", "AGFzbQEAAAA=")
    with pytest.raises(ToolError, match="not a file"):
        uploads.open_upload("fastedge.binaries.create", str(tmp_path))
    with pytest.raises(ToolError, match="not its contents"):
        uploads.open_upload("fastedge.binaries.create", 123)


def test_size_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    app = tmp_path / "big.wasm"
    app.write_bytes(WASM)
    small = uploads.Upload("a compiled WebAssembly binary (.wasm)", b"\0asm", 16)
    monkeypatch.setitem(uploads.UPLOADS, "fastedge.binaries.create", small)
    with pytest.raises(ToolError, match="the limit is"):
        uploads.open_upload("fastedge.binaries.create", str(app))


def test_sdk_reads_the_path() -> None:
    """The SDK sends a PathLike body as the file's bytes."""
    from gcore.resources.fastedge.binaries import BinariesResource

    assert "os.PathLike" in inspect.getsource(BinariesResource.create)
