"""SDK method inspection functionality."""

import inspect
from typing import Any, Generator, Callable, get_type_hints

from gcore import Gcore

# Type alias for the structure holding inspected resource methods
ResourceMethodsDict = dict[str, dict[str, dict[str, Any]]]

# Cache for inspected SDK methods
_resource_methods_cache: ResourceMethodsDict | None = None


def _inspect_recursive(
    obj: Any, 
    current_path_parts: list[str], 
    methods_dict: ResourceMethodsDict,
    base_module_name: str
) -> None:
    """
    Recursively inspects an object to find methods and nested resources.
    """
    # Attributes/methods to skip at any level
    skip_names = [
        '_client', '_version', '_qs', '_session', '_options', '_params', 
        '_response_timeout', 'api_key', 'project_id', 'region_id', 
        'with_raw_response', 'with_streaming_response', 'copy', 'model_copy'
    ]

    current_path = ".".join(current_path_parts)
    if not current_path_parts: # Should not happen if initial call is correct
        current_path = obj.__class__.__name__.lower() # Fallback for the root object if path is empty

    resource_entry: dict[str, dict[str, Any]] = methods_dict.get(current_path, {})

    # Inspect methods of the current object
    for method_name, method_obj in inspect.getmembers(obj, inspect.ismethod):
        if method_name.startswith('_') or method_name in skip_names:
            continue
        
        try:
            sig = inspect.signature(method_obj)
            docstring = inspect.getdoc(method_obj) or ""
            param_types = get_type_hints(method_obj)
            
            resource_entry[method_name] = {
                'signature': sig,
                'docstring': docstring,
                'param_types': param_types,
                'return_type': param_types.get('return'),
                'method_obj': method_obj, # Store the actual method object
            }
        except (ValueError, TypeError) as e: # Handle cases where signature or hints can't be retrieved
            print(f"Error inspecting method {current_path}.{method_name}: {str(e)}")

    if resource_entry:
        methods_dict[current_path] = resource_entry

    # Inspect attributes for nested resources
    for attr_name, attr_value in inspect.getmembers(obj, lambda x: not inspect.isroutine(x)):
        if attr_name.startswith('_') or attr_name in skip_names:
            continue

        # Heuristic: recurse if the attribute's type is defined within the SDK's base module
        # or if it's a common pattern for resource grouping (like 'instances' having 'images')
        # This helps avoid recursing into standard library types or unrelated complex objects.
        try:
            attr_module = inspect.getmodule(attr_value.__class__)
            if attr_module and attr_module.__name__.startswith(base_module_name):
                 _inspect_recursive(attr_value, current_path_parts + [attr_name], methods_dict, base_module_name)
        except Exception:
            # print(f"Error determining module for {current_path}.{attr_name}: {str(e)}")
            pass # Some objects might not have a clear module or __class__


def iter_sdk_methods(client: Any) -> Generator[tuple[str, Callable[..., Any]], None, None]:
    """Yield **public** leaf callables from the SDK as (full_name, fn)."""
    resource_methods_data = inspect_sdk_methods(client)
    for resource_path, methods in resource_methods_data.items():
        for method_name, method_info in methods.items():
            full_name = f"{resource_path}.{method_name}"
            method_obj = method_info.get('method_obj')
            if callable(method_obj):
                yield full_name, method_obj


def inspect_sdk_methods(client: Gcore) -> ResourceMethodsDict:
    """
    Inspect the SDK to discover all available resource methods, including nested ones.
    Uses a cache to avoid re-inspecting on subsequent calls.
    """
    global _resource_methods_cache
    if _resource_methods_cache is not None:
        return _resource_methods_cache

    inspected_methods: ResourceMethodsDict = {}
    
    client_module = inspect.getmodule(client.__class__)
    base_module_name = client_module.__name__.split('.')[0] if client_module else "gcore"
    
    # Top-level attributes on the client to skip
    skip_top_level = [
        'api_key', 'project_id', 'region_id', 'with_raw_response', 
        'with_streaming_response', 'copy', 'model_copy', 'from_env'
    ]

    # Inspect all top-level service attributes of the client (e.g., cloud, waap, dns)
    for service_name, service_obj in inspect.getmembers(client):
        if service_name.startswith('_') or service_name in skip_top_level:
            continue
        
        # Heuristic: if it's an object from the same base SDK module, treat it as a service
        service_module = inspect.getmodule(service_obj.__class__)
        if not service_module or not service_module.__name__.startswith(base_module_name):
            continue

        # Found a service object (like client.cloud, client.waap).
        # Now, start the recursive inspection on its attributes.
        for attr_name, attr_value in inspect.getmembers(service_obj, lambda x: not inspect.isroutine(x)):
            if attr_name.startswith('_'):
                continue
            
            attr_module = inspect.getmodule(attr_value.__class__)
            if attr_module and attr_module.__name__.startswith(base_module_name):
                 _inspect_recursive(attr_value, [service_name, attr_name], inspected_methods, base_module_name)

        # Also handle methods directly on the service object itself (e.g., client.dns.list_zones())
        for method_name, method_obj in inspect.getmembers(service_obj, inspect.ismethod):
            if method_name.startswith('_'):
                continue

            resource_path = service_name
            if resource_path not in inspected_methods:
                inspected_methods[resource_path] = {}
            try:
                sig = inspect.signature(method_obj)
                docstring = inspect.getdoc(method_obj) or ""
                param_types = get_type_hints(method_obj)
                inspected_methods[resource_path][method_name] = {
                    'signature': sig,
                    'docstring': docstring,
                    'param_types': param_types,
                    'return_type': param_types.get('return'),
                    'method_obj': method_obj,
                }
            except (ValueError, TypeError) as e:
                print(f"Error inspecting method {resource_path}.{method_name}: {str(e)}")

    _resource_methods_cache = inspected_methods
    return inspected_methods


def get_all_resources(client: Gcore) -> list[str]:
    """Get a list of all available hierarchical resource paths from the CloudAPI."""
    resource_methods_data = inspect_sdk_methods(client)
    return list(resource_methods_data.keys())


def clear_inspection_cache() -> None:
    """Clear the inspection cache. Useful for testing."""
    global _resource_methods_cache
    _resource_methods_cache = None 