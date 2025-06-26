"""Configuration settings and shortening rules."""

import os
import re
import logging
from typing import Final
from ..domain import get_gcore_domain_handler

logger = logging.getLogger(__name__)

UNIFIED_TOOLS_ENV_VAR: Final[str] = "GCORE_TOOLS"
MAX_TOOL_NAME_LEN: Final[int] = 60

def get_shortening_rules() -> dict[str, str]:
    """Get combined shortening rules from domain handler."""
    domain_handler = get_gcore_domain_handler()
    rules: dict[str, str] = {}
    rules.update(domain_handler.get_resource_shortening_rules())
    rules.update(domain_handler.get_method_shortening_rules())

    # Additional rules not in domain handler (legacy/specific)
    additional_rules = {
        "interfaces": "ifaces",
        "metrics": "metr",
        "baremetal": "bm",
        "gpu_baremetal_clusters": "gpu_bm_clusters",
        "l7_policies": "l7pols",
        "health_monitors": "health_mon",
        "members": "membs",
        "statuses": "stats",
        "ip_ranges": "iprngs",
        "rules": "rls",
        "access_rules": "accessrls",
        "repositories": "repos",
        "artifacts": "arts",
        "users": "usrs",
        "tasks": "tsks",
        "quotas": "qotas",
        "requests": "reqs",
        "role_assignments": "roleasgns",
        "billing_reservations": "billresrvs",
        "models": "mdls",
        "logs": "logs",
        "registry_credentials": "regcreds",
        # Method parts / verbs
        "resize": "resz",
        "get_console": "get_con",
        "action": "act",
        "list_suitable": "ls_suit",
        "list_for_resize": "ls_resz",
        "attach": "att",
        "detach": "det",
        "upload": "upl",
        "list": "ls",
        "get": "get",
        "powercycle_all_servers": "pwrall_srvs",
        "reboot_all_servers": "rebootall_srvs",
        "servers": "srvs",
        "powercycle": "pwrcycle",
        "failover": "failovr",
        "remove": "rm",
        "list_candidate_ports": "ls_cand_ports",
        "list_connected_ports": "ls_conn_ports",
        "replace_connected_ports": "repl_conn_ports",
        "update_connected_ports": "upd_conn_ports",
        "copy": "cp",
        "change_type": "chng_type",
        "create_multiple": "new_multi",
        "refresh_secret": "refresh_secr",
        "acknowledge_all": "ack_all",
        "acknowledge_one": "ack_one",
        "upload_tls_certificate": "upl_tls_cert",
        "get_api_key": "get_apikey",
    }

    rules.update(additional_rules)
    return rules


def generate_short_tool_name(
    original_dot_name: str, max_len: int = MAX_TOOL_NAME_LEN
) -> str:
    """
    Generates a shortened tool name by applying segment-wise shortenings
    and then truncating to a maximum length. Retains dot-separated format.
    """
    shortening_rules = get_shortening_rules()
    parts = original_dot_name.split(".")
    shortened_parts = [shortening_rules.get(part, part) for part in parts]
    short_name_untruncated = ".".join(shortened_parts)

    if len(short_name_untruncated) <= max_len:
        return short_name_untruncated

    # Truncate to max_len if necessary
    return short_name_untruncated[:max_len]


def convert_pattern_to_regex(pattern: str) -> str:
    """Convert a wildcard pattern to a regex pattern."""
    # Escape all regex special characters
    escaped = re.escape(pattern)
    # Replace escaped asterisks with regex wildcard that matches everything including dots
    regex_pattern = escaped.replace(r"\*", r".*")
    # Ensure full match from start to end
    regex_pattern = f"^{regex_pattern}$"
    return regex_pattern


def get_unified_tool_config() -> tuple[list[str], list[str]]:
    """Get unified tool configuration from environment variable.
    
    Returns:
        Tuple of (toolset_names, pattern_filters)
    """
    unified_config = os.getenv(UNIFIED_TOOLS_ENV_VAR)
    if unified_config:
        return parse_unified_tool_config(unified_config)
    
    # Return empty lists if no config
    return [], []


def parse_unified_tool_config(config_str: str) -> tuple[list[str], list[str]]:
    """Parse unified tool configuration string into toolsets and patterns.
    
    Args:
        config_str: Comma-separated list of toolset names and/or patterns
        
    Returns:
        Tuple of (toolset_names, pattern_filters)
    """
    from .toolsets import TOOLSETS  # Import here to avoid circular imports
    
    entries = [entry.strip() for entry in config_str.split(",") if entry.strip()]
    toolset_names: list[str] = []
    pattern_filters: list[str] = []
    
    for entry in entries:
        if entry in TOOLSETS:
            # Known toolset name
            toolset_names.append(entry)
            logger.debug("Recognized '%s' as toolset", entry)
        else:
            # Treat as pattern
            pattern_filters.append(entry)
            logger.debug("Treating '%s' as pattern", entry)
    
    return toolset_names, pattern_filters
