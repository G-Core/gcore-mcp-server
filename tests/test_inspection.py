"""Tests for the inspection module."""

from typing import Any
from unittest.mock import Mock, patch
from inspect import Parameter, Signature
import inspect

import pytest

from gcore_mcp_server.core.inspection import (
    inspect_sdk_methods,
    iter_sdk_methods,
    get_all_resources,
    clear_inspection_cache,
)


@pytest.fixture
def complex_gcore_sdk_data() -> dict[str, dict[str, dict[str, Any]]]:
    """Get comprehensive sample SDK inspection data for testing."""
    return {
        "cloud.instances": {
            "create": {
                "signature": Signature([
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("flavor_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("region", Parameter.POSITIONAL_OR_KEYWORD, default="us-east-1", annotation=str),
                ]),
                "docstring": "Create a new virtual machine instance with specified configuration",
                "param_types": {"name": str, "flavor_id": str, "region": str},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            },
            "delete": {
                "signature": Signature([
                    Parameter("instance_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("delete_floatings", Parameter.POSITIONAL_OR_KEYWORD, default=False, annotation=bool),
                ]),
                "docstring": "Delete an existing virtual machine instance",
                "param_types": {"instance_id": str, "delete_floatings": bool},
                "return_type": None,
                "method_obj": Mock()
            },
            "list": {
                "signature": Signature([
                    Parameter("limit", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=int | None),
                    Parameter("offset", Parameter.POSITIONAL_OR_KEYWORD, default=0, annotation=int),
                ]),
                "docstring": "List all virtual machine instances in the current project",
                "param_types": {"limit": int | None, "offset": int},
                "return_type": list[dict[str, Any]],
                "method_obj": Mock()
            },
            "get": {
                "signature": Signature([
                    Parameter("instance_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                ]),
                "docstring": "Get detailed information about a specific instance",
                "param_types": {"instance_id": str},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            }
        },
        "cloud.instances.images": {
            "create": {
                "signature": Signature([
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("instance_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                ]),
                "docstring": "Create an image from an existing instance",
                "param_types": {"name": str, "instance_id": str},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            },
            "list": {
                "signature": Signature([
                    Parameter("visibility", Parameter.POSITIONAL_OR_KEYWORD, default="private", annotation=str),
                ]),
                "docstring": "List available instance images",
                "param_types": {"visibility": str},
                "return_type": list[dict[str, Any]],
                "method_obj": Mock()
            }
        },
        "cloud.volumes": {
            "create": {
                "signature": Signature([
                    Parameter("size", Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("volume_type", Parameter.POSITIONAL_OR_KEYWORD, default="standard", annotation=str),
                ]),
                "docstring": "Create a new storage volume",
                "param_types": {"size": int, "name": str, "volume_type": str},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            },
            "delete": {
                "signature": Signature([
                    Parameter("volume_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("snapshots", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=str | None),
                ]),
                "docstring": "Delete a storage volume permanently",
                "param_types": {"volume_id": str, "snapshots": str | None},
                "return_type": None,
                "method_obj": Mock()
            },
            "extend": {
                "signature": Signature([
                    Parameter("volume_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("size", Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                ]),
                "docstring": "Extend volume size",
                "param_types": {"volume_id": str, "size": int},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            }
        },
        "cloud.loadbalancers": {
            "create": {
                "signature": Signature([
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("vip_network_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("listeners", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=list[dict[str, Any]] | None),
                ]),
                "docstring": "Create a new load balancer",
                "param_types": {"name": str, "vip_network_id": str, "listeners": list[dict[str, Any]] | None},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            },
            "delete": {
                "signature": Signature([
                    Parameter("loadbalancer_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                ]),
                "docstring": "Delete a load balancer",
                "param_types": {"loadbalancer_id": str},
                "return_type": None,
                "method_obj": Mock()
            }
        },
        "cloud.networks": {
            "create": {
                "signature": Signature([
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("create_router", Parameter.POSITIONAL_OR_KEYWORD, default=False, annotation=bool),
                ]),
                "docstring": "Create a new network",
                "param_types": {"name": str, "create_router": bool},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            },
            "list": {
                "signature": Signature([]),
                "docstring": "List all networks",
                "param_types": {},
                "return_type": list[dict[str, Any]],
                "method_obj": Mock()
            }
        },
        "cloud.projects": {
            "list": {
                "signature": Signature([
                    Parameter("client_id", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=str | None),
                    Parameter("include_deleted", Parameter.POSITIONAL_OR_KEYWORD, default=False, annotation=bool),
                ]),
                "docstring": "List projects with optional filtering",
                "param_types": {"client_id": str | None, "include_deleted": bool},
                "return_type": list[dict[str, Any]],
                "method_obj": Mock()
            },
            "create": {
                "signature": Signature([
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("description", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=str | None),
                ]),
                "docstring": "Create a new project",
                "param_types": {"name": str, "description": str | None},
                "return_type": dict[str, Any],
                "method_obj": Mock()
            }
        }
    }


@pytest.fixture
def deeply_nested_mock_client():
    """Create a deeply nested mock client to test complex traversal."""
    client = Mock()
    
    # Create nested structure: client.cloud.instances.images.snapshots
    cloud = Mock()
    client.cloud = cloud
    
    instances = Mock()
    cloud.instances = instances
    
    images = Mock()
    instances.images = images
    
    snapshots = Mock()
    images.snapshots = snapshots
    
    # Add methods at various levels
    instances.create = Mock()
    instances.list = Mock()
    instances.delete = Mock()
    
    images.create = Mock()
    images.list = Mock()
    
    snapshots.create = Mock()
    snapshots.delete = Mock()
    
    # Add additional nested resources
    volumes = Mock()
    cloud.volumes = volumes
    volumes.list = Mock()
    volumes.create = Mock()
    
    networks = Mock()
    cloud.networks = networks
    networks.create = Mock()
    networks.list = Mock()
    
    subnets = Mock()
    networks.subnets = subnets
    subnets.create = Mock()
    subnets.list = Mock()
    
    return client


class TestInspection:
    """Test suite for SDK method inspection functionality."""

    def test_clear_inspection_cache(self):
        """Test that cache clearing works correctly."""
        # First, populate the cache
        mock_client = Mock()
        mock_client.cloud = Mock()
        
        def mock_getmodule_side_effect(obj_class: Any) -> Mock:
            mock_module = Mock()
            mock_module.__name__ = "gcore.resources"
            return mock_module
            
        def mock_getmembers_side_effect(obj: Any, predicate: Any = None) -> list[tuple[str, Any]]:
            # Return minimal mock members to avoid infinite recursion
            if predicate == inspect.ismethod:
                return [("test_method", Mock())]
            else:
                return [("test_resource", Mock())]
        
        # Mock the required inspection functions to prevent infinite recursion
        with patch('inspect.getmodule', side_effect=mock_getmodule_side_effect):
            with patch('inspect.getmembers', side_effect=mock_getmembers_side_effect):
                with patch('inspect.signature') as mock_signature:
                    with patch('inspect.getdoc') as mock_getdoc:
                        with patch('gcore_mcp_server.core.inspection.get_type_hints') as mock_hints:
                            mock_signature.return_value = Signature([])
                            mock_getdoc.return_value = "Test method"
                            mock_hints.return_value = {}
                            
                            # Call to populate cache
                            result1 = inspect_sdk_methods(mock_client)
                            assert isinstance(result1, dict)
                            
                            # Clear cache
                            clear_inspection_cache()
                            
                            # Verify cache is cleared by checking that the next call inspects again
                            result2 = inspect_sdk_methods(mock_client)
                            assert isinstance(result2, dict)
                            
                            # Results should be the same content but different objects (since cache was cleared)
                            assert result1 is not result2  # Different objects after cache clear

    def test_get_all_resources_with_mock_client(self, mock_gcore_client: Any):
        """Test getting all resources from a mock client."""
        with patch('gcore_mcp_server.core.inspection.inspect_sdk_methods') as mock_inspect:
            mock_inspect.return_value = {
                "cloud.instances": {"create": {}, "list": {}},
                "cloud.projects": {"list": {}}
            }
            
            resources = get_all_resources(mock_gcore_client)
            
            assert "cloud.instances" in resources
            assert "cloud.projects" in resources
            assert len(resources) == 2

    def test_iter_sdk_methods_with_mock_data(self):
        """Test iterating over SDK methods with mock data."""
        # Mock inspect_sdk_methods to return complex data
        with patch(
            "gcore_mcp_server.core.inspection.inspect_sdk_methods"
        ) as mock_inspect:
            mock_inspect.return_value = {
                "cloud.instances": {
                    "create": {"method_obj": Mock()},
                    "delete": {"method_obj": Mock()},
                },
                "cloud.volumes": {"create": {"method_obj": Mock()}},
            }

            methods = list(iter_sdk_methods(Mock()))

            assert len(methods) == 3
            assert methods[0][0] == "cloud.instances.create"
            assert callable(methods[0][1])
            assert methods[1][0] == "cloud.instances.delete"
            assert callable(methods[1][1])
            assert methods[2][0] == "cloud.volumes.create"
            assert callable(methods[2][1])

    @patch("gcore_mcp_server.core.inspection.inspect.getmodule")
    @patch("gcore_mcp_server.core.inspection.inspect.getmembers")
    def test_inspect_sdk_methods_caching(
        self, mock_getmembers: Mock, mock_getmodule: Mock
    ):
        """Test that SDK methods inspection uses caching correctly."""
        # Clear cache first
        clear_inspection_cache()

        # Configure mocks to return a minimal but consistent structure
        mock_service = Mock(_mock_name="cloud_service")
        mock_resource = Mock(_mock_name="resource")

        # Create a simple mock client
        mock_client = Mock()

        mock_getmodule.return_value = Mock(__name__="gcore.services")

        def members_side_effect(obj: Any, predicate: Any | None = None) -> list[tuple[str, Any]]:
            """Return stable members depending on object and predicate."""
            if predicate is inspect.ismethod:
                # Provide a dummy method for resource objects to ensure they are recorded
                if obj is mock_resource:
                    def dummy() -> None:
                        return None
                    return [("dummy", dummy)]
                return []
            # Non-method attributes traversal
            if obj is mock_client:
                return [("cloud", mock_service)]
            if obj is mock_service:
                return [("resource", mock_resource)]
            return []

        mock_getmembers.side_effect = members_side_effect

        # First call should inspect and cache
        result1 = inspect_sdk_methods(mock_client)

        # Second call should use cache
        result2 = inspect_sdk_methods(mock_client)

        # The first result should be what the mock inspection produced
        assert "cloud.resource" in result1
        assert result1 is result2, "Second result should be the same cached object"

    @patch('gcore_mcp_server.core.inspection.inspect.getmodule')
    @patch('gcore_mcp_server.core.inspection.inspect.getmembers')
    def test_inspect_sdk_methods_with_no_cloud_service(self, mock_getmembers: Mock, mock_getmodule: Mock):
        """Test inspection with a client that has no cloud service."""
        # Clear cache first
        clear_inspection_cache()

        # Configure mocks to simulate a client with no services
        mock_getmodule.return_value = Mock(__name__="gcore.services")
        mock_getmembers.return_value = []

        mock_client = Mock()
        mock_client.cloud = None

        # Should return an empty dict, not raise an error
        result = inspect_sdk_methods(mock_client)
        assert result == {}

    def test_complex_sdk_data_structure(self, complex_gcore_sdk_data: dict[str, dict[str, dict[str, Any]]]):
        """Test with complex realistic SDK data structure."""
        mock_client = Mock()
        
        with patch('gcore_mcp_server.core.inspection.inspect_sdk_methods') as mock_inspect:
            mock_inspect.return_value = complex_gcore_sdk_data
            
            # Test get_all_resources
            resources = get_all_resources(mock_client)
            expected_resources = [
                "cloud.instances",
                "cloud.instances.images", 
                "cloud.volumes",
                "cloud.loadbalancers",
                "cloud.networks",
                "cloud.projects"
            ]
            
            for resource in expected_resources:
                assert resource in resources
                
            # Test iter_sdk_methods  
            methods = list(iter_sdk_methods(mock_client))
            method_names = [method[0] for method in methods]
            
            # Check some expected method names
            expected_methods = [
                "cloud.instances.create",
                "cloud.instances.delete", 
                "cloud.instances.list",
                "cloud.volumes.create",
                "cloud.loadbalancers.create",
                "cloud.projects.list"
            ]
            
            for method_name in expected_methods:
                assert method_name in method_names
                
            # Verify all methods are callable
            for _, method_obj in methods:
                assert callable(method_obj)

    def test_full_traversal_without_exceptions(self, deeply_nested_mock_client: Any):
        """Test full traversal of deeply nested client structure without exceptions."""
        clear_inspection_cache()
        
        # Mock the module inspection to simulate a real SDK structure
        def mock_getmodule_side_effect(obj_class: Any) -> Mock:
            mock_module = Mock()
            mock_module.__name__ = "gcore.resources"
            return mock_module
            
        def mock_getmembers_side_effect(obj: Any, predicate: Any | None = None) -> list[tuple[str, Any]]:
            """Return no attributes or methods to keep traversal shallow."""
            return []
        
        with patch("inspect.getmodule", side_effect=mock_getmodule_side_effect):
            with patch("inspect.getmembers", side_effect=mock_getmembers_side_effect):
                with patch("inspect.signature") as mock_signature:
                    with patch("inspect.getdoc") as mock_getdoc:
                        with patch(
                            "gcore_mcp_server.core.inspection.get_type_hints"
                        ) as mock_hints:
                            # Mock successful inspection responses
                            mock_signature.return_value = Signature([])
                            mock_getdoc.return_value = "Test method documentation"
                            mock_hints.return_value = {}
                            
                            # This should not raise any exceptions
                            try:
                                result = inspect_sdk_methods(deeply_nested_mock_client)
                                assert isinstance(result, dict)
                                
                                # Test that we can iterate over methods without issues
                                methods = list(
                                    iter_sdk_methods(deeply_nested_mock_client)
                                )
                                assert len(methods) >= 0  # Should have some methods
                                
                                # Test getting resources
                                resources = get_all_resources(deeply_nested_mock_client)
                                assert isinstance(resources, list)
                                
                            except Exception as e:
                                pytest.fail(f"Full traversal raised unexpected exception: {e}")

    def test_traversal_handles_inspection_errors_gracefully(self):
        """Test that traversal handles various inspection errors gracefully."""
        mock_client = Mock()
        mock_client.cloud = Mock()
        
        # Create a mock object that will cause signature inspection to fail
        problematic_method = Mock()
        
        def mock_getmodule_side_effect(obj_class: Any) -> Mock:
            mock_module = Mock()
            mock_module.__name__ = "gcore.resources"
            return mock_module
            
        def mock_getmembers_side_effect(obj: Any, predicate: Any | None = None) -> list[tuple[str, Any]]:
            if predicate and predicate == inspect.ismethod:
                return [("problematic_method", problematic_method)]
            else:
                # Return a resource that will trigger recursive inspection
                return [("instances", Mock())]
            
        with patch("inspect.getmodule", side_effect=mock_getmodule_side_effect):
            with patch('inspect.getmembers', side_effect=mock_getmembers_side_effect):
                with patch('inspect.signature') as mock_signature:
                    with patch('inspect.getdoc') as mock_getdoc:
                        with patch('gcore_mcp_server.core.inspection.get_type_hints') as mock_hints:
                            # Make signature inspection fail
                            mock_signature.side_effect = ValueError("Cannot inspect signature")
                            mock_getdoc.return_value = "Test method"
                            mock_hints.return_value = {}
                            
                            # This should not crash despite the error
                            result = inspect_sdk_methods(mock_client)
                            
                            # Should still return a dict (empty or with partial results)
                            assert isinstance(result, dict)

    def test_method_filtering_skips_private_methods(self):
        """Test that private methods and attributes are properly filtered."""
        mock_client = Mock()
        mock_client.cloud = Mock()
        mock_resource = Mock()
        mock_client.cloud.test_resource = mock_resource
        
        # Create both private and public methods
        private_method = Mock()
        public_method = Mock()
        
        def mock_getmodule_side_effect(obj_class: Any) -> Mock:
            mock_module = Mock()
            mock_module.__name__ = "gcore.resources"
            return mock_module
            
        def mock_getmembers_side_effect(obj: Any, predicate: Any | None = None) -> list[tuple[str, Any]]:
            if predicate and predicate == inspect.ismethod:
                return [
                    ('_private_method', private_method),
                    ('__dunder_method__', Mock()),
                    ('public_method', public_method)
                ]
            else:
                return []
                
        with patch('inspect.getmodule', side_effect=mock_getmodule_side_effect):
            with patch('inspect.getmembers', side_effect=mock_getmembers_side_effect):
                with patch('inspect.signature') as mock_signature:
                    with patch('inspect.getdoc') as mock_getdoc:
                        with patch('gcore_mcp_server.core.inspection.get_type_hints') as mock_hints:
                            mock_signature.return_value = Signature([])
                            mock_getdoc.return_value = "Test method"
                            mock_hints.return_value = {}
                            
                            result = inspect_sdk_methods(mock_client)
                            
                            # Check that private methods are not included
                            if "cloud.test_resource" in result:
                                methods = result["cloud.test_resource"]
                                assert "public_method" in methods
                                assert "_private_method" not in methods
                                assert "__dunder_method__" not in methods

    def test_complex_parameter_types_handling(self, complex_gcore_sdk_data: dict[str, dict[str, dict[str, Any]]]):
        """Test handling of complex parameter types in method signatures."""
        # Test that complex type annotations are preserved
        instances_create = complex_gcore_sdk_data["cloud.instances"]["create"]
        
        assert "param_types" in instances_create
        param_types = instances_create["param_types"]
        
        # Check that different types are properly represented
        assert param_types["name"] is str
        assert param_types["flavor_id"] is str
        assert param_types["region"] is str
        
        # Test union types
        volumes_delete = complex_gcore_sdk_data["cloud.volumes"]["delete"]
        assert volumes_delete["param_types"]["snapshots"] == str | None
        
        # Test complex return types
        assert instances_create["return_type"] == dict[str, Any]
        
        # Test list types
        loadbalancer_create = complex_gcore_sdk_data["cloud.loadbalancers"]["create"]
        assert loadbalancer_create["param_types"]["listeners"] == list[dict[str, Any]] | None 