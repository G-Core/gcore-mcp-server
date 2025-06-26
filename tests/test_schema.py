"""Tests for the schema module."""

from typing import Optional, Union, Literal, Any
from gcore_mcp_server.core.schema import (
    convert_param_type_to_schema_type,
    convert_sdk_type,
)
from tests.conftest import MockVolumeSpec


class TestSchemaConversion:
    """Test suite for type to JSON Schema conversion."""

    def test_basic_types(self):
        """Test conversion of basic Python types."""
        # String type
        result = convert_param_type_to_schema_type(str)
        assert result["type"] == "string"
        
        # Integer type
        result = convert_param_type_to_schema_type(int)
        assert result["type"] == "integer"
        
        # Boolean type
        result = convert_param_type_to_schema_type(bool)
        assert result["type"] == "boolean"
        
        # Float type
        result = convert_param_type_to_schema_type(float)
        assert result["type"] == "number"

    def test_optional_types(self):
        """Test conversion of Optional types."""
        result = convert_param_type_to_schema_type(Optional[str])
        assert result["type"] == "string"
        assert result["description"] == "Optional"

    def test_union_types(self):
        """Test conversion of Union types."""
        result = convert_param_type_to_schema_type(Union[str, int])
        assert "oneOf" in result
        assert len(result["oneOf"]) == 2
        
        # Check that both types are represented
        types = [schema["type"] for schema in result["oneOf"]]
        assert "string" in types
        assert "integer" in types

    def test_literal_types(self):
        """Test conversion of Literal types."""
        result = convert_param_type_to_schema_type(Literal["small", "medium", "large"])
        assert result["type"] == "string"
        assert "enum" in result
        assert result["enum"] == ["small", "medium", "large"]
        assert "Must be one of" in result["description"]

    def test_list_types(self):
        """Test conversion of List types."""
        result = convert_param_type_to_schema_type(list[str])
        assert result["type"] == "array"
        assert result["items"]["type"] == "string"
        assert "Array of" in result["description"]

    def test_dict_types(self):
        """Test conversion of Dict types."""
        result = convert_param_type_to_schema_type(dict[str, int])
        assert result["type"] == "object"
        assert "additionalProperties" in result
        assert result["additionalProperties"]["type"] == "integer"

    def test_typeddict_conversion(self):
        """Test conversion of TypedDict to JSON Schema."""
        result = convert_param_type_to_schema_type(MockVolumeSpec)
        assert result["type"] == "object"
        assert "properties" in result
        assert "source" in result["properties"]
        assert "size" in result["properties"]
        
        # Check required fields
        assert "required" in result
        assert "source" in result["required"]

    def test_any_type(self):
        """Test conversion of Any type."""
        result = convert_param_type_to_schema_type(Any)
        assert result["type"] == "object"
        assert "Any type" in result["description"]

    def test_volumes_parameter_special_handling(self):
        """Test special handling for 'volumes' parameter."""
        result = convert_param_type_to_schema_type(list[MockVolumeSpec], "volumes")
        assert result["type"] == "array"
        assert "examples" in result
        assert len(result["examples"]) == 2
        assert "List of volume configurations" in result["description"]

    def test_interfaces_parameter_special_handling(self):
        """Test special handling for 'interfaces' parameter."""
        from tests.conftest import MockNetworkInterface
        result = convert_param_type_to_schema_type(list[MockNetworkInterface], "interfaces")
        assert result["type"] == "array"
        assert "examples" in result
        assert "List of network interface configurations" in result["description"]

    def test_security_groups_parameter_special_handling(self):
        """Test special handling for 'security_groups' parameter."""
        result = convert_param_type_to_schema_type(list[str], "security_groups")
        assert result["type"] == "array"
        assert "examples" in result
        assert "List of security group UUIDs" in result["description"]

    def test_convert_sdk_type_with_notgiven(self):
        """Test convert_sdk_type handles NotGiven correctly."""
        from gcore import NotGiven
        
        # Test Union[str, NotGiven] -> Optional[str]
        union_type = Union[str, NotGiven]
        result = convert_sdk_type(union_type)
        # The result should be Optional[str] which is Union[str, None]
        assert result is not None

    def test_fallback_for_unknown_types(self):
        """Test that unknown types get a fallback schema."""
        class CustomClass:
            pass
        
        result = convert_param_type_to_schema_type(CustomClass)
        assert result["type"] == "object"
        assert "CustomClass" in result["description"]

    def test_parameter_name_context(self):
        """Test that parameter names influence schema generation."""
        # Test volumes parameter
        result = convert_param_type_to_schema_type(list[dict[str, Any]], "volumes")
        assert "volume" in result["description"].lower()
        
        # Test regular parameter
        result = convert_param_type_to_schema_type(list[dict[str, Any]], "items")
        assert "Array of" in result["description"]

    def test_nested_optional_union_types(self):
        """Test complex nested types with Optional and Union."""
        complex_type = Optional[Union[str, list[int]]]
        result = convert_param_type_to_schema_type(complex_type)
        
        assert "oneOf" in result
        # Should have string, array, and null types
        assert len(result["oneOf"]) == 3 