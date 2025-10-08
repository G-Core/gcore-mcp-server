"""E2E smoke test for the MCP Gcore server."""

import pytest
from unittest.mock import Mock, patch
from typing import Any

from gcore import Gcore
from gcore_mcp_server.core.inspection import (
    inspect_sdk_methods,
    iter_sdk_methods,
    get_all_resources,
    clear_inspection_cache,
)
from gcore_mcp_server.core.schema import normalize_sdk_type_for_mcp
from gcore_mcp_server.config.settings import generate_short_tool_name
from gcore_mcp_server.server import make_wrapper
from fastmcp.tools.tool import Tool


class TestE2ESmoke:
    """E2E smoke tests for the entire MCP Gcore server functionality."""

    def setup_method(self):
        """Set up each test by clearing the inspection cache."""
        clear_inspection_cache()

    def test_gcore_import_and_basic_structure(self):
        """Test that Gcore can be imported and has expected basic structure."""
        # This should not raise any exceptions
        client = Gcore(api_key="empty")

        # Verify basic structure exists
        assert hasattr(client, "cloud"), "Gcore client should have 'cloud' attribute"
        assert client.cloud is not None, "Gcore client.cloud should not be None"

        # Verify we can access the cloud service without exceptions
        cloud_service = client.cloud
        assert cloud_service is not None

    @patch("inspect.getmodule")
    @patch("inspect.getmembers")
    def test_inspect_sdk_methods_traversal_no_exceptions(
        self, mock_getmembers: Mock, mock_getmodule: Mock
    ):
        """Test that inspect_sdk_methods can traverse the entire SDK without raising exceptions."""
        # Set up mock module
        mock_module = Mock()
        mock_module.__name__ = "gcore.something"
        mock_getmodule.return_value = mock_module

        # Create a mock method with proper signature
        def mock_method(param1: str, param2: int = 10) -> dict[str, Any]:
            """A sample method."""
            return {}

        # Set up mock cloud service with a resource that has methods
        mock_resource = Mock()
        mock_getmembers.side_effect = [
            [("mock_resource", mock_resource)],  # For cloud service attributes
            [("sample_method", mock_method)],  # For the resource's methods
            [],  # For the resource's attributes (for recursion)
            [],  # For the cloud service's own methods
            [],  # Final empty call
        ]

        # Mock client
        client = Mock(spec=Gcore)
        client.cloud = Mock()

        try:
            result = inspect_sdk_methods(client)
            assert isinstance(result, dict), "inspect_sdk_methods should return a dict"

            # Verify structure contains expected keys
            for resource_path, methods in result.items():
                assert isinstance(resource_path, str), "Resource path should be string"
                assert isinstance(methods, dict), "Methods should be dict"

                for method_name, method_info in methods.items():
                    assert isinstance(method_name, str), "Method name should be string"
                    assert isinstance(method_info, dict), "Method info should be dict"

                    # Verify expected keys in method info
                    expected_keys = {
                        "signature",
                        "docstring",
                        "param_types",
                        "return_type",
                        "method_obj",
                    }
                    assert all(key in method_info for key in expected_keys), (
                        f"Method info missing keys: {expected_keys - method_info.keys()}"
                    )

        except Exception as e:
            pytest.fail(f"inspect_sdk_methods raised an exception: {e}")

    @patch("inspect.getmodule")
    @patch("inspect.getmembers")
    def test_iter_sdk_methods_no_exceptions(
        self, mock_getmembers: Mock, mock_getmodule: Mock
    ):
        """Test that iter_sdk_methods can iterate through all methods without exceptions."""
        # Set up mock module
        mock_module = Mock()
        mock_module.__name__ = "gcore.something"
        mock_getmodule.return_value = mock_module

        # Create a mock method with proper signature
        def mock_method(param1: str, param2: int = 10) -> dict[str, Any]:
            """A sample method."""
            return {}

        # Set up mock cloud service with a resource that has methods
        mock_resource = Mock()
        mock_getmembers.side_effect = [
            [("mock_resource", mock_resource)],  # For cloud service attributes
            [("sample_method", mock_method)],  # For the resource's methods
            [],  # For the resource's attributes (for recursion)
            [],  # For the cloud service's own methods
            [],  # Final empty call
        ]

        # Mock client
        client = Mock(spec=Gcore)
        client.cloud = Mock()

        try:
            methods = list(iter_sdk_methods(client))
            assert isinstance(methods, list), "iter_sdk_methods should return a list"

            # Verify each item is a tuple with (name, callable)
            for full_name, method_obj in methods:
                assert isinstance(full_name, str), "Full name should be string"
                assert callable(method_obj), "Method object should be callable"
                assert "." in full_name, (
                    "Full name should contain dots (resource.method format)"
                )

        except Exception as e:
            pytest.fail(f"iter_sdk_methods raised an exception: {e}")

    @patch("inspect.getmodule")
    @patch("inspect.getmembers")
    def test_get_all_resources_no_exceptions(
        self, mock_getmembers: Mock, mock_getmodule: Mock
    ):
        """Test that get_all_resources returns resource paths without exceptions."""
        # Set up mock module
        mock_module = Mock()
        mock_module.__name__ = "gcore.something"
        mock_getmodule.return_value = mock_module

        # Set up mock cloud service
        mock_resource = Mock()
        # Provide enough side effects for all the calls
        mock_getmembers.side_effect = [
            [("mock_resource", mock_resource)],  # For cloud service
            [],  # For the resource (no methods)
            [],  # For attr inspection
            [],  # For any additional calls
        ]

        # Mock client
        client = Mock(spec=Gcore)
        client.cloud = Mock()

        try:
            resources = get_all_resources(client)
            assert isinstance(resources, list), "get_all_resources should return a list"

            # Verify each resource is a string
            for resource in resources:
                assert isinstance(resource, str), "Each resource should be a string"

        except Exception as e:
            pytest.fail(f"get_all_resources raised an exception: {e}")

    def test_normalize_sdk_type_for_mcp_no_exceptions(self):
        """Test that normalize_sdk_type_for_mcp handles various types without exceptions."""
        from gcore import NotGiven, Omit
        from typing import Union, Iterable

        test_types = [
            str,
            int,
            bool,
            float,
            list[str],
            dict[str, int],
            Any,
            Union[str, NotGiven],
            Union[int, Omit],
            Iterable[str],
        ]

        for test_type in test_types:
            try:
                result = normalize_sdk_type_for_mcp(test_type)
                # Should return some type without raising
                assert result is not None
            except Exception as e:
                pytest.fail(
                    f"normalize_sdk_type_for_mcp raised exception for {test_type}: {e}"
                )

    def test_generate_short_tool_name_no_exceptions(self):
        """Test that generate_short_tool_name handles various tool names without exceptions."""
        test_names = [
            "cloud.instances.create",
            "cloud.networks.subnets.list",
            "cloud.load_balancers.listeners.delete",
            "very.long.tool.name.with.many.segments.that.should.be.shortened",
        ]

        for test_name in test_names:
            try:
                result = generate_short_tool_name(test_name)
                assert isinstance(result, str), (
                    f"Result should be string for {test_name}"
                )
                assert len(result) <= 60, (
                    f"Result should be ≤60 chars for {test_name}, got {len(result)}"
                )

            except Exception as e:
                pytest.fail(
                    f"generate_short_tool_name raised exception for {test_name}: {e}"
                )

    def test_full_e2e_integration_smoke(self):
        """Full integration test from SDK to tool generation (smoke test)."""
        try:
            # Test basic Gcore client instantiation
            client = Gcore(api_key="test-key")
            assert client is not None, "Client should be created"

            # Clear cache for consistent test
            clear_inspection_cache()

            # Test resource listing
            resources = get_all_resources(client)
            assert isinstance(resources, list), "get_all_resources should return list"

            # Test SDK methods inspection
            methods_dict = inspect_sdk_methods(client)
            assert isinstance(methods_dict, dict), (
                "inspect_sdk_methods should return dict"
            )

            # Test SDK methods iteration (with limited scope)
            methods_list = list(iter_sdk_methods(client))
            assert isinstance(methods_list, list), "iter_sdk_methods should return list"

            # Test tool name shortening for a few methods
            for full_name, method_obj in methods_list[:5]:  # Test first 5 methods
                short_name = generate_short_tool_name(full_name)
                assert isinstance(short_name, str), "Short name should be string"
                assert callable(method_obj), "Method should be callable"

        except Exception as e:
            pytest.fail(f"Full E2E integration test failed: {e}")

    def test_caching_behavior_no_exceptions(self):
        """Test that caching works correctly and doesn't introduce errors."""
        try:
            client = Gcore(api_key="test-key")

            # Clear cache and get initial result
            clear_inspection_cache()

            # First call should populate cache
            result1 = inspect_sdk_methods(client)
            assert isinstance(result1, dict), "First call should return dict"

            # Second call should use cache (same result)
            result2 = inspect_sdk_methods(client)
            assert isinstance(result2, dict), "Second call should return dict"
            assert result1 is result2, "Second call should return same object (cached)"

            # Clear cache and verify new result is created
            clear_inspection_cache()

            # Third call should create new result
            result3 = inspect_sdk_methods(client)
            assert isinstance(result3, dict), "Third call should return dict"
            # Note: We don't assert it's different because the content should be the same,
            # but it should be a new object

        except Exception as e:
            pytest.fail(f"Caching behavior test failed: {e}")

    def test_cost_reports_schema_generation(self):
        """Test that cloud.cost_reports.get_aggregated generates correct array schema."""
        client = Gcore(api_key="test-key")

        # Find the cost_reports.get_aggregated method
        method = None
        for full_name, sdk_method in iter_sdk_methods(client):
            if (
                "cost_reports.get_aggregated" in full_name
                and "monthly" not in full_name
            ):
                method = sdk_method
                break

        assert method is not None, "cloud.cost_reports.get_aggregated not found"

        # Create wrapper and check annotations
        wrapper = make_wrapper(
            method, "cloud.cost_reports.get_aggregated", False, False
        )

        # Check that wrapper has proper type annotations
        annotations = wrapper.__annotations__
        assert "projects" in annotations
        assert "time_from" in annotations
        assert "time_to" in annotations

        # Create FastMCP tool and check schema
        tool = Tool.from_function(wrapper, name="test_cost_reports", description="Test")
        mcp_tool = tool.to_mcp_tool()
        schema = mcp_tool.model_dump()

        # Verify projects parameter schema
        projects_schema = schema["inputSchema"]["properties"]["projects"]

        # Should be anyOf with array and null (optional array)
        assert "anyOf" in projects_schema, (
            f"Expected anyOf in projects schema, got: {projects_schema}"
        )

        # Find the array type in anyOf
        array_schemas = [
            s for s in projects_schema["anyOf"] if s.get("type") == "array"
        ]
        assert len(array_schemas) >= 1, (
            f"Expected at least one array schema, got: {projects_schema}"
        )

        # Check array items are integers
        array_schema = array_schemas[0]
        assert "items" in array_schema, (
            f"Expected items in array schema, got: {array_schema}"
        )
        assert array_schema["items"]["type"] == "integer", (
            f"Expected integer items, got: {array_schema['items']}"
        )

    def test_wrapper_preserves_array_types(self):
        """Test that wrapper properly preserves array parameter types."""
        from typing import List, Union
        from gcore import Omit

        # Create a mock method with array parameter
        def mock_method(projects: Union[List[int], Omit] = Omit()) -> dict:
            """Mock method for testing."""
            return {"projects": projects}

        # Add type hints
        mock_method.__annotations__ = {
            "projects": Union[List[int], Omit],
            "return": dict,
        }

        # Create wrapper
        wrapper = make_wrapper(mock_method, "test.mock_method", False, False)

        # Check wrapper annotations
        annotations = wrapper.__annotations__
        assert "projects" in annotations

        # projects should be List[int] | None after normalization
        from typing import get_origin, get_args
        import types

        projects_type = annotations["projects"]
        # Handle both Union and UnionType (T | U syntax)
        assert get_origin(projects_type) in (Union, types.UnionType)

        # Should have List[int] and None
        args = get_args(projects_type)
        assert type(None) in args
        list_args = [arg for arg in args if arg is not type(None)]
        assert len(list_args) == 1
        assert get_origin(list_args[0]) is list
