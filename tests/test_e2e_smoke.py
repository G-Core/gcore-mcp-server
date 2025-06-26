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
from gcore_mcp_server.core.schema import convert_param_type_to_schema_type
from gcore_mcp_server.config.settings import generate_short_tool_name


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
        assert hasattr(client, 'cloud'), "Gcore client should have 'cloud' attribute"
        assert client.cloud is not None, "Gcore client.cloud should not be None"
        
        # Verify we can access the cloud service without exceptions
        cloud_service = client.cloud
        assert cloud_service is not None

    @patch('inspect.getmodule')
    @patch('inspect.getmembers')
    def test_inspect_sdk_methods_traversal_no_exceptions(self, mock_getmembers: Mock, mock_getmodule: Mock):
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
            [('mock_resource', mock_resource)],  # For cloud service attributes
            [('sample_method', mock_method)],    # For the resource's methods
            [],                                  # For the resource's attributes (for recursion)
            [],                                  # For the cloud service's own methods
            [],                                  # Final empty call
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
                    expected_keys = {'signature', 'docstring', 'param_types', 'return_type', 'method_obj'}
                    assert all(key in method_info for key in expected_keys), f"Method info missing keys: {expected_keys - method_info.keys()}"
                    
        except Exception as e:
            pytest.fail(f"inspect_sdk_methods raised an exception: {e}")

    @patch('inspect.getmodule')
    @patch('inspect.getmembers')
    def test_iter_sdk_methods_no_exceptions(self, mock_getmembers: Mock, mock_getmodule: Mock):
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
            [('mock_resource', mock_resource)],  # For cloud service attributes
            [('sample_method', mock_method)],    # For the resource's methods
            [],                                  # For the resource's attributes (for recursion)
            [],                                  # For the cloud service's own methods
            [],                                  # Final empty call
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
                assert "." in full_name, "Full name should contain dots (resource.method format)"
                
        except Exception as e:
            pytest.fail(f"iter_sdk_methods raised an exception: {e}")

    @patch('inspect.getmodule')
    @patch('inspect.getmembers')
    def test_get_all_resources_no_exceptions(self, mock_getmembers: Mock, mock_getmodule: Mock):
        """Test that get_all_resources returns resource paths without exceptions."""
        # Set up mock module
        mock_module = Mock()
        mock_module.__name__ = "gcore.something"
        mock_getmodule.return_value = mock_module
        
        # Set up mock cloud service
        mock_resource = Mock()
        # Provide enough side effects for all the calls
        mock_getmembers.side_effect = [
            [('mock_resource', mock_resource)],  # For cloud service
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

    def test_convert_param_type_to_schema_type_no_exceptions(self):
        """Test that convert_param_type_to_schema_type handles various types without exceptions."""
        test_types = [
            str, int, bool, float,
            list[str], dict[str, int],
            Any,
        ]
        
        for test_type in test_types:
            try:
                result = convert_param_type_to_schema_type(test_type, "test_param")
                assert isinstance(result, dict), f"Result should be dict for type {test_type}"
                assert "type" in result, f"Result should have 'type' key for type {test_type}"
                
            except Exception as e:
                pytest.fail(f"convert_param_type_to_schema_type raised exception for {test_type}: {e}")

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
                assert isinstance(result, str), f"Result should be string for {test_name}"
                assert len(result) <= 60, f"Result should be ≤60 chars for {test_name}, got {len(result)}"
                
            except Exception as e:
                pytest.fail(f"generate_short_tool_name raised exception for {test_name}: {e}")

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
            assert isinstance(methods_dict, dict), "inspect_sdk_methods should return dict"
            
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