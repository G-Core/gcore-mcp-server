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
)

__all__ = [
    "GcoreDomainHandler",
    "GcoreParameterType",
    "get_gcore_domain_handler",
    "GCORE_SPECIAL_PARAMETERS",
] 