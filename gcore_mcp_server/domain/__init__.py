"""
Gcore SDK domain-specific logic and configurations.

This module contains all domain-specific knowledge about Gcore SDK,
including parameter handling, schema customizations, and naming conventions.
"""

from .gcore_domain import (
    GcoreDomainHandler,
    GcoreParameterType,
    get_gcore_domain_handler,
    GCORE_SPECIAL_PARAMETERS,
    MCP_PROJECT_REGION_INSTRUCTIONS,
    PROJECT_ID_TOOL_NOTE,
    REGION_ID_TOOL_NOTE,
    PROJECT_ID_REQUIRED_ERROR,
    REGION_ID_REQUIRED_ERROR,
    PROJECT_REGION_LOOKUP_TOOLS,
)

__all__ = [
    "GcoreDomainHandler",
    "GcoreParameterType",
    "get_gcore_domain_handler",
    "GCORE_SPECIAL_PARAMETERS",
    "MCP_PROJECT_REGION_INSTRUCTIONS",
    "PROJECT_ID_TOOL_NOTE",
    "REGION_ID_TOOL_NOTE",
    "PROJECT_ID_REQUIRED_ERROR",
    "REGION_ID_REQUIRED_ERROR",
    "PROJECT_REGION_LOOKUP_TOOLS",
]
