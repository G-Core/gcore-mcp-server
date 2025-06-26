"""Tests for unified tool configuration functionality."""

import os
from unittest.mock import patch

from gcore_mcp_server.config.settings import (
    get_unified_tool_config,
    parse_unified_tool_config,
    UNIFIED_TOOLS_ENV_VAR,
    convert_pattern_to_regex,
)
from gcore_mcp_server.config.toolsets import (
    get_allowed_tools_list,
)


class TestUnifiedConfiguration:
    """Test suite for unified tool configuration functionality."""

    def test_get_unified_tool_config_with_config(self):
        """Test that GCORE_TOOLS variable is parsed correctly."""
        env_vars = {
            UNIFIED_TOOLS_ENV_VAR: "instances,cloud.volumes.*",
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            toolsets, patterns = get_unified_tool_config()
            # Should use unified config
            assert "instances" in toolsets
            assert "cloud.volumes.*" in patterns

    def test_get_unified_tool_config_empty(self):
        """Test fallback when unified variable not set."""
        with patch.dict(os.environ, {}, clear=True):
            toolsets, patterns = get_unified_tool_config()
            assert toolsets == []
            assert patterns == []

    def test_parse_unified_tool_config_mixed_entries(self):
        """Test parsing mixed toolsets and patterns."""
        config_str = "instances,management,cloud.volumes.*,dns.records.create"
        
        with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {"instances": [], "management": []}):
            toolsets, patterns = parse_unified_tool_config(config_str)
            assert toolsets == ["instances", "management"]
            assert patterns == ["cloud.volumes.*", "dns.records.create"]

    def test_parse_unified_tool_config_only_toolsets(self):
        """Test parsing config with only toolsets."""
        config_str = "instances,management,ai_ml"
        
        with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {"instances": [], "management": [], "ai_ml": []}):
            toolsets, patterns = parse_unified_tool_config(config_str)
            assert toolsets == ["instances", "management", "ai_ml"]
            assert patterns == []

    def test_parse_unified_tool_config_only_patterns(self):
        """Test parsing config with only patterns."""
        config_str = "cloud.volumes.*,dns.records.create,cloud.instances.create"
        
        with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {}):
            toolsets, patterns = parse_unified_tool_config(config_str)
            assert toolsets == []
            assert patterns == ["cloud.volumes.*", "dns.records.create", "cloud.instances.create"]

    def test_parse_unified_tool_config_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        config_str = " instances , cloud.volumes.* , management , dns.* "
        
        with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {"instances": [], "management": []}):
            toolsets, patterns = parse_unified_tool_config(config_str)
            assert toolsets == ["instances", "management"]
            assert patterns == ["cloud.volumes.*", "dns.*"]

    def test_get_allowed_tools_list_unified_new_config(self):
        """Test unified tool list generation with GCORE_TOOLS variable."""
        available_tools = [
            "cloud.instances.create",
            "cloud.instances.delete",
            "cloud.volumes.create",
            "cloud.volumes.delete",
        ]
        
        env_vars = {
            UNIFIED_TOOLS_ENV_VAR: "instances,cloud.volumes.*"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {"instances": ["cloud.insts.new"]}):
                result = get_allowed_tools_list(available_tools)
                
                # Should contain both toolset tools and pattern-matched tools
                assert "cloud.insts.new" in result  # From toolset
                assert "cloud.vols.new" in result   # From pattern
                assert "cloud.vols.del" in result   # From pattern

    def test_get_allowed_tools_list_empty_config_uses_defaults(self):
        """Test that empty config falls back to defaults."""
        available_tools = ["cloud.instances.create"]
        
        with patch.dict(os.environ, {}, clear=True):
            with patch("gcore_mcp_server.config.toolsets.DEFAULT_TOOLSETS", ["instances"]):
                with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {"instances": ["cloud.insts.new"]}):
                    result = get_allowed_tools_list(available_tools)
                    assert "cloud.insts.new" in result

    def test_get_allowed_tools_list_toolsets_only(self):
        """Test tool list generation with only toolsets (no patterns)."""
        env_vars = {
            UNIFIED_TOOLS_ENV_VAR: "instances"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {"instances": ["cloud.insts.new", "cloud.insts.del"]}):
                result = get_allowed_tools_list()  # No available tools provided
                assert result == ["cloud.insts.new", "cloud.insts.del"]

    def test_get_allowed_tools_list_patterns_only(self):
        """Test tool list generation with only patterns (no toolsets)."""
        available_tools = [
            "cloud.instances.create",
            "cloud.instances.delete",
        ]
        
        env_vars = {
            UNIFIED_TOOLS_ENV_VAR: "cloud.instances.*"
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("gcore_mcp_server.config.toolsets.TOOLSETS", {}):
                result = get_allowed_tools_list(available_tools)
                
                # Should contain pattern-matched tools only
                assert "cloud.insts.new" in result
                assert "cloud.insts.del" in result

    def test_convert_pattern_to_regex(self):
        """Test pattern to regex conversion."""
        # Exact pattern
        assert convert_pattern_to_regex("cloud.instances.create") == "^cloud\\.instances\\.create$"
        
        # Wildcard pattern
        assert convert_pattern_to_regex("cloud.*") == "^cloud\\..*$"
        
        # Complex pattern
        assert convert_pattern_to_regex("cloud.*.create") == "^cloud\\..*\\.create$"
