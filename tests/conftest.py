"""Pytest fixtures for MCP Gcore tests."""

from typing import Any, TypedDict, Optional, Union, Literal

# Required and NotRequired live in typing (Python ≥3.11). For Python 3.10 fallback to typing_extensions.
try:
    from typing import Required, NotRequired  # type: ignore
except ImportError:  # Python < 3.11
    from typing_extensions import Required, NotRequired  # type: ignore

from unittest.mock import Mock
from inspect import Parameter, Signature
from gcore import Gcore

import pytest


class MockVolumeSpec(TypedDict, total=False):
    """Mock volume specification for testing."""
    source: Required[Literal["image", "snapshot", "volume"]]
    image_id: NotRequired[str]
    snapshot_id: NotRequired[str] 
    volume_id: NotRequired[str]
    size: NotRequired[int]
    boot_index: NotRequired[int]


class MockNetworkInterface(TypedDict):
    """Mock network interface configuration."""
    type: Literal["external", "internal"]
    network_id: Optional[str]
    subnet_id: Optional[str]
    security_groups: Optional[list[str]]


@pytest.fixture
def mock_gcore_client():
    """Create a mock Gcore client for testing."""
    client = Mock(spec=Gcore)
    
    # Mock cloud service
    cloud = Mock()
    client.cloud = cloud
    
    # Mock instances resource
    instances = Mock()
    cloud.instances = instances
    
    # Mock methods with proper signatures
    def create_instance(
        name: str,
        flavor_id: str,
        volumes: list[MockVolumeSpec],
        interfaces: list[MockNetworkInterface],
        keypair_name: Optional[str] = None
    ) -> dict[str, Any]:
        return {"id": "test-instance-id", "name": name}
    
    def list_instances(limit: Optional[int] = None) -> list[dict[str, Any]]:
        return [{"id": "instance-1", "name": "test-instance"}]
    
    def get_instance(instance_id: str) -> dict[str, Any]:
        return {"id": instance_id, "name": "test-instance"}
    
    # Set up method objects with proper docstrings
    instances.create = Mock(side_effect=create_instance)
    instances.create.__doc__ = "Create a new instance"
    instances.list = Mock(side_effect=list_instances) 
    instances.list.__doc__ = "List instances"
    instances.get = Mock(side_effect=get_instance)
    instances.get.__doc__ = "Get instance details"
    
    # Mock flavors sub-resource
    flavors = Mock()
    instances.flavors = flavors
    
    def list_flavors() -> list[dict[str, Any]]:
        return [{"id": "flavor-1", "name": "small"}]
    
    flavors.list = Mock(side_effect=list_flavors)
    flavors.list.__doc__ = "List available flavors"
    
    # Mock projects resource  
    projects = Mock()
    cloud.projects = projects
    
    def list_projects(client_id: Optional[str] = None) -> list[dict[str, Any]]:
        return [{"id": "project-1", "name": "test-project"}]
    
    projects.list = Mock(side_effect=list_projects)
    projects.list.__doc__ = "List projects"
    
    return client


@pytest.fixture
def mock_method_info():
    """Create mock method info for testing."""
    params = [
        Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
        Parameter("flavor_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
        Parameter("volumes", Parameter.POSITIONAL_OR_KEYWORD, annotation=list[MockVolumeSpec]),
        Parameter("interfaces", Parameter.POSITIONAL_OR_KEYWORD, annotation=list[MockNetworkInterface]),
        Parameter("keypair_name", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=Optional[str])
    ]
    
    signature = Signature(parameters=params)
    
    return {
        'signature': signature,
        'docstring': 'Create a new instance with specified configuration',
        'param_types': {
            'name': str,
            'flavor_id': str, 
            'volumes': list[MockVolumeSpec],
            'interfaces': list[MockNetworkInterface],
            'keypair_name': Optional[str]
        },
        'return_type': dict[str, Any],
        'method_obj': Mock()
    }


@pytest.fixture
def sample_resource_methods():
    """Sample resource methods data for testing."""
    return {
        "cloud.instances": {
            "create": {
                'signature': Signature([
                    Parameter("name", Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
                    Parameter("flavor_id", Parameter.POSITIONAL_OR_KEYWORD, annotation=str)
                ]),
                'docstring': 'Create instance',
                'param_types': {'name': str, 'flavor_id': str},
                'method_obj': Mock()
            },
            "list": {
                'signature': Signature([
                    Parameter("limit", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=Optional[int])
                ]),
                'docstring': 'List instances',
                'param_types': {'limit': Optional[int]},
                'method_obj': Mock()
            }
        },
        "cloud.projects": {
            "list": {
                'signature': Signature([
                    Parameter("client_id", Parameter.POSITIONAL_OR_KEYWORD, default=None, annotation=Optional[str])
                ]),
                'docstring': 'List projects',
                'param_types': {'client_id': Optional[str]},
                'method_obj': Mock()
            }
        }
    }


@pytest.fixture
def sample_type_annotations():
    """Sample type annotations for schema conversion testing."""
    return {
        'string_type': str,
        'integer_type': int,
        'boolean_type': bool,
        'optional_string': Optional[str],
        'union_type': Union[str, int],
        'literal_type': Literal["small", "medium", "large"],
        'list_type': list[str],
        'dict_type': dict[str, Any],
        'typeddict_type': MockVolumeSpec,
        'complex_list': list[MockVolumeSpec]
    } 