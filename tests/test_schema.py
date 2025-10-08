"""Tests for the schema module."""

from typing import Optional, Union, Literal, Any, List, Iterable
from gcore_mcp_server.core.schema import normalize_sdk_type_for_mcp
from gcore import NotGiven, Omit


class TestNormalizeSDKTypeForMCP:
    """Test suite for normalize_sdk_type_for_mcp function."""

    def test_union_with_notgiven(self):
        """Test that Union[T, NotGiven] becomes T | None."""
        result = normalize_sdk_type_for_mcp(Union[str, NotGiven])
        # Result should be str | None
        assert result == (str | None)

    def test_union_with_omit(self):
        """Test that Union[T, Omit] becomes T | None."""
        result = normalize_sdk_type_for_mcp(Union[int, Omit])
        # Result should be int | None
        assert result == (int | None)

    def test_iterable_to_list(self):
        """Test that Iterable[T] becomes List[T]."""
        result = normalize_sdk_type_for_mcp(Iterable[int])
        # Result should be List[int]
        assert result == List[int]

    def test_union_iterable_with_omit(self):
        """Test that Union[Iterable[int], Omit] becomes List[int] | None."""
        result = normalize_sdk_type_for_mcp(Union[Iterable[int], Omit])
        # Result should be List[int] | None
        assert result == (List[int] | None)

    def test_complex_union_with_sdk_markers(self):
        """Test Union[str, int, NotGiven] becomes Union[str, int] | None."""
        result = normalize_sdk_type_for_mcp(Union[str, int, NotGiven])
        # Should be Union[str, int] | None
        from typing import get_origin, get_args

        assert get_origin(result) is Union
        args = get_args(result)
        # Should have Union[str, int] and None
        assert type(None) in args

    def test_simple_type_passthrough(self):
        """Test that simple types pass through unchanged."""
        assert normalize_sdk_type_for_mcp(str) is str
        assert normalize_sdk_type_for_mcp(int) is int
        assert normalize_sdk_type_for_mcp(bool) is bool

    def test_optional_type_preserved(self):
        """Test that Optional[T] is preserved."""
        result = normalize_sdk_type_for_mcp(Optional[str])
        assert result == Optional[str]

    def test_literal_type_preserved(self):
        """Test that Literal types pass through unchanged."""
        literal_type = Literal["a", "b", "c"]
        assert normalize_sdk_type_for_mcp(literal_type) == literal_type

    def test_list_type_preserved(self):
        """Test that List[T] passes through (may be normalized to list[T])."""
        from typing import get_origin, get_args

        list_type = List[str]
        result = normalize_sdk_type_for_mcp(list_type)
        # Should be a list type with str items
        assert get_origin(result) is list
        assert get_args(result) == (str,)

    def test_empty_union_with_sdk_markers(self):
        """Test Union with only SDK markers becomes Any | None."""
        result = normalize_sdk_type_for_mcp(Union[NotGiven, Omit])
        assert result == (Any | None)

    def test_io_type_normalized(self):
        """Test that IO[bytes] is normalized to str."""
        from typing import IO

        result = normalize_sdk_type_for_mcp(IO[bytes])
        assert result is str

    def test_pathlike_normalized(self):
        """Test that os.PathLike is normalized to str."""
        import os

        result = normalize_sdk_type_for_mcp(os.PathLike)
        assert result is str

    def test_union_with_io_normalized(self):
        """Test that Union[IO[bytes], bytes] is normalized properly."""
        from typing import IO, Union as TypingUnion

        result = normalize_sdk_type_for_mcp(TypingUnion[IO[bytes], bytes])
        # Should normalize IO[bytes] to str, keep bytes
        from typing import get_origin, get_args

        assert get_origin(result) is TypingUnion
        args = get_args(result)
        assert str in args
        assert bytes in args


class TestE2ESchemaGeneration:
    """E2E tests for actual schema generation through FastMCP."""

    def test_basic_types_schema_generation(self):
        """Test that basic types generate correct schemas through FastMCP."""
        from fastmcp.tools.tool import Tool
        from typing import Any

        async def test_func(
            str_param: str,
            int_param: int,
            bool_param: bool,
            optional_param: str | None = None,
        ) -> Any:
            """Test function."""
            pass

        tool = Tool.from_function(test_func, name="test", description="Test")
        schema = tool.to_mcp_tool().model_dump()
        props = schema["inputSchema"]["properties"]

        # Verify basic types
        assert props["str_param"]["type"] == "string"
        assert props["int_param"]["type"] == "integer"
        assert props["bool_param"]["type"] == "boolean"

        # Verify optional
        assert "anyOf" in props["optional_param"]

    def test_array_schema_generation(self):
        """Test that list types generate correct array schemas."""
        from fastmcp.tools.tool import Tool
        from typing import Any, List

        async def test_func(items: List[str]) -> Any:
            """Test function."""
            pass

        tool = Tool.from_function(test_func, name="test", description="Test")
        schema = tool.to_mcp_tool().model_dump()
        props = schema["inputSchema"]["properties"]

        assert props["items"]["type"] == "array"
        assert props["items"]["items"]["type"] == "string"

    def test_union_schema_generation(self):
        """Test that Union types generate correct schemas."""
        from fastmcp.tools.tool import Tool
        from typing import Any, Union

        async def test_func(param: Union[str, int]) -> Any:
            """Test function."""
            pass

        tool = Tool.from_function(test_func, name="test", description="Test")
        schema = tool.to_mcp_tool().model_dump()
        props = schema["inputSchema"]["properties"]

        assert "anyOf" in props["param"]

    def test_literal_schema_generation(self):
        """Test that Literal types generate correct enum schemas."""
        from fastmcp.tools.tool import Tool
        from typing import Any, Literal

        async def test_func(size: Literal["small", "medium", "large"]) -> Any:
            """Test function."""
            pass

        tool = Tool.from_function(test_func, name="test", description="Test")
        schema = tool.to_mcp_tool().model_dump()
        props = schema["inputSchema"]["properties"]

        assert props["size"]["enum"] == ["small", "medium", "large"]
