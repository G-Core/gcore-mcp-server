"""Toolset definitions and management functionality."""

import os
import logging
from typing import Final

from .settings import (
    generate_short_tool_name,
    get_unified_tool_config,
    UNIFIED_TOOLS_ENV_VAR,
)
from ..domain import get_gcore_domain_handler

logger = logging.getLogger(__name__)


def get_raw_toolsets() -> dict[str, list[str]]:
    """Get raw (unshortened) toolset definitions from domain handler."""
    domain_handler = get_gcore_domain_handler()
    base_toolsets = domain_handler.get_toolset_definitions()

    # Add additional custom toolsets not in base domain
    additional_toolsets = {
        "baremetal": [
            # Baremetal Servers
            "cloud.baremetal.images.list",
            "cloud.baremetal.flavors.list",
            "cloud.baremetal.flavors.list_suitable",
            "cloud.baremetal.servers.create",
            "cloud.baremetal.servers.list",
            "cloud.baremetal.servers.rebuild",
        ],
        "gpu_baremetal": [
            # GPU Baremetal Clusters
            "cloud.gpu_baremetal_clusters.create",
            "cloud.gpu_baremetal_clusters.get",
            "cloud.gpu_baremetal_clusters.delete",
            "cloud.gpu_baremetal_clusters.list",
            "cloud.gpu_baremetal_clusters.rebuild",
            "cloud.gpu_baremetal_clusters.resize",
            "cloud.gpu_baremetal_clusters.powercycle_all_servers",
            "cloud.gpu_baremetal_clusters.reboot_all_servers",
            "cloud.gpu_baremetal_clusters.interfaces.list",
            "cloud.gpu_baremetal_clusters.servers.delete",
            "cloud.gpu_baremetal_clusters.servers.attach_interface",
            "cloud.gpu_baremetal_clusters.servers.detach_interface",
            "cloud.gpu_baremetal_clusters.servers.get_console",
            "cloud.gpu_baremetal_clusters.servers.powercycle",
            "cloud.gpu_baremetal_clusters.servers.reboot",
            "cloud.gpu_baremetal_clusters.flavors.list",
            "cloud.gpu_baremetal_clusters.images.upload",
            "cloud.gpu_baremetal_clusters.images.list",
            "cloud.gpu_baremetal_clusters.images.get",
            "cloud.gpu_baremetal_clusters.images.delete",
        ],
        "ai_ml": [
            # Inference
            "cloud.inference.get_capacity_by_region",
            "cloud.inference.flavors.list",
            "cloud.inference.flavors.get",
            "cloud.inference.models.list",
            "cloud.inference.models.get",
            "cloud.inference.deployments.create",
            "cloud.inference.deployments.list",
            "cloud.inference.deployments.get",
            "cloud.inference.deployments.update",
            "cloud.inference.deployments.delete",
            "cloud.inference.deployments.get_api_key",
            "cloud.inference.deployments.start",
            "cloud.inference.deployments.stop",
            "cloud.inference.deployments.logs.list",
            "cloud.inference.registry_credentials.create",
            "cloud.inference.registry_credentials.list",
            "cloud.inference.registry_credentials.get",
            "cloud.inference.registry_credentials.replace",
            "cloud.inference.registry_credentials.delete",
            "cloud.inference.secrets.create",
            "cloud.inference.secrets.list",
            "cloud.inference.secrets.get",
            "cloud.inference.secrets.replace",
            "cloud.inference.secrets.delete",
        ],
        "cleanup": [
            # Contains all delete methods
            "cloud.secrets.delete",
            "cloud.ssh_keys.delete",
            "cloud.load_balancers.delete",
            "cloud.load_balancers.l7policies.delete",
            "cloud.load_balancers.listeners.delete",
            "cloud.load_balancers.pools.delete",
            "cloud.reserved_fixed_ips.delete",
            "cloud.networks.delete",
            "cloud.networks.subnets.delete",
            "cloud.networks.routers.delete",
            "cloud.volumes.delete",
            "cloud.floating_ips.delete",
            "cloud.security_groups.delete",
            "cloud.inference.deployments.delete",
            "cloud.placement_groups.delete",
            "cloud.registries.delete",
            "cloud.file_shares.delete",
            "cloud.gpu_baremetal_clusters.delete",
            "cloud.gpu_baremetal_clusters.servers.delete",
            "cloud.gpu_baremetal_clusters.images.delete",
            "cloud.instances.delete",
            "cloud.instances.images.delete",
        ],
        "list": [
            "cloud.instances.list",
            "cloud.instances.flavors.list",
            "cloud.instances.images.list",
            "cloud.baremetal.images.list",
            "cloud.baremetal.flavors.list",
            "cloud.baremetal.servers.list",
            "cloud.gpu_baremetal_clusters.list",
            "cloud.gpu_baremetal_clusters.flavors.list",
            "cloud.gpu_baremetal_clusters.images.list",
            "cloud.networks.list",
            "cloud.networks.subnets.list",
            "cloud.networks.routers.list",
        ],
    }

    # Merge with base toolsets
    result = base_toolsets.copy()
    result.update(additional_toolsets)
    return result


# Dynamically generate shortened toolsets from domain handler
def _generate_toolsets() -> dict[str, list[str]]:
    """Generate TOOLSETS with shortened names."""
    raw_toolsets = get_raw_toolsets()
    shortened_toolsets: dict[str, list[str]] = {}

    for toolset_key, tool_list in raw_toolsets.items():
        shortened_toolsets[toolset_key] = [
            generate_short_tool_name(tool_name) for tool_name in tool_list
        ]

    return shortened_toolsets


# Legacy support - dynamically generated toolsets
TOOLSETS: Final[dict[str, list[str]]] = _generate_toolsets()

# Default toolsets if GCORE_TOOLS is not set or empty
DEFAULT_TOOLSETS: Final[list[str]] = ["management", "instances"]


def get_active_toolset_names() -> list[str]:
    """
    Retrieves the list of active toolset names from the unified configuration.
    If no configuration is set, returns default toolset names.
    """
    # Get unified configuration
    toolset_names, _ = get_unified_tool_config()
    if toolset_names or os.getenv(UNIFIED_TOOLS_ENV_VAR) is not None:
        return toolset_names
    
    # Fall back to defaults if no config
    return DEFAULT_TOOLSETS


def get_allowed_tools_list(all_available_tools: list[str] | None = None) -> list[str]:
    """
    Constructs a flat list of all tools using unified configuration.
    Automatically detects toolsets vs patterns and combines them with toolset priority.
    
    Args:
        all_available_tools: List of all available tool names from SDK (full names, not shortened).
                           If None, only toolset-based tools are returned.
        
    Returns:
        List of tool names (shortened) allowed by the current configuration.
    """
    # Get unified configuration
    toolset_names, pattern_filters = get_unified_tool_config()
    
    # If no unified config, fall back to defaults
    if not toolset_names and not pattern_filters and os.getenv(UNIFIED_TOOLS_ENV_VAR) is None:
        toolset_names = DEFAULT_TOOLSETS
    
    # Get tools from toolsets
    toolset_tools: list[str] = []
    for toolset_name in toolset_names:
        if toolset_name in TOOLSETS:
            toolset_tools.extend(TOOLSETS[toolset_name])
        else:
            logger.warning("Unknown toolset '%s', skipping", toolset_name)
    
    # Remove duplicates from toolset tools while preserving order
    toolset_tools = list(dict.fromkeys(toolset_tools))
    
    # Get tools from patterns if any patterns exist and we have available tools
    pattern_matched_tools: list[str] = []
    if pattern_filters and all_available_tools:
        # Use the pattern matching logic
        for tool_name in all_available_tools:
            for pattern in pattern_filters:
                if pattern == tool_name or (
                    "*" in pattern 
                    and __import__("re").match(
                        __import__("re").escape(pattern).replace(r"\*", r".*"), 
                        tool_name
                    )
                ):
                    pattern_matched_tools.append(tool_name)
                    break
        
        # Convert to shortened names
        pattern_matched_tools = [
            generate_short_tool_name(tool_name) for tool_name in pattern_matched_tools
        ]
    
    # Combine with toolset tools having priority
    combined_dict: dict[str, None] = dict.fromkeys(
        toolset_tools + pattern_matched_tools
    )
    combined_tools = list(combined_dict.keys())
    
    logger.info(
        "Unified tool selection: %d from toolsets, %d from patterns, %d total unique",
        len(toolset_tools),
        len(pattern_matched_tools),
        len(combined_tools),
    )
    
    return combined_tools


def derive_allowed_resources(tool_list: list[str]) -> list[str]:
    """
    Derives a list of allowed resource types from tool names.

    For example, from ['cloud.insts.new', 'cloud.vols.ls'],
    this would return ['insts', 'vols'].

    Args:
        tool_list: List of tool names in shortened format.

    Returns:
        List of unique resource names derived from the tool names.
    """
    resources: set[str] = set()
    for tool in tool_list:
        parts = tool.split(".")
        if len(parts) >= 2:
            # Extract the resource part (second component in cloud.resource.method)
            resource = parts[1]
            resources.add(resource)
    return sorted(list(resources))



