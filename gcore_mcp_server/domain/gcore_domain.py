"""
Gcore SDK domain-specific handlers and configurations.

This module extracts all Gcore SDK specific logic from the core modules,
making the core functionality more universal and domain-agnostic.
"""

from typing import Any, Dict, List, Set
from enum import Enum


class GcoreParameterType(Enum):
    """Types of special Gcore parameters that need custom handling."""
    VOLUMES = "volumes"
    INTERFACES = "interfaces" 
    SECURITY_GROUPS = "security_groups"
    FLAVORS = "flavors"
    NETWORKS = "networks"
    INSTANCES = "instances"
    PROJECTS = "projects"
    REGIONS = "regions"


# Domain-specific parameter names that require special handling
GCORE_SPECIAL_PARAMETERS: Set[str] = {
    "volumes",
    "interfaces", 
    "security_groups",
    "flavors",
    "networks",
    "instances", 
    "projects",
    "regions",
}


class GcoreDomainHandler:
    """Handler for Gcore SDK domain-specific logic."""
    
    @staticmethod
    def get_parameter_description(param_name: str, base_description: str = "") -> str:
        """Get domain-specific parameter descriptions."""
        descriptions = {
            "volumes": (
                "List of volume configurations. Each item can define a volume from an image, "
                "snapshot, or refer to an existing volume. "
                'Example for a boot volume from image: `[{"source": "image", "image_id": "...", '
                '"boot_index": 0, "size": 50}]`. '
                'Example for an existing volume: `[{"id": "..."}]`.'
            ),
            "interfaces": (
                "List of network interface configurations. "
                'Example: `[{"type": "external", "network_id": "..."}]`'
            ),
            "security_groups": (
                "List of security group UUIDs. "
                'Example: `["<sg_uuid1>", "<sg_uuid2>"]`'
            ),
        }
        
        if param_name in descriptions:
            return descriptions[param_name]
        
        return base_description
    
    @staticmethod
    def get_parameter_examples(param_name: str) -> List[Any]:
        """Get domain-specific parameter examples."""
        examples = {
            "volumes": [
                [{"source": "image", "image_id": "<image_uuid>", "boot_index": 0, "size": 50}],
                [{"id": "<existing_volume_uuid>"}]
            ],
            "interfaces": [
                [{"type": "external", "network_id": "<network_uuid>"}],
                [{"type": "internal", "subnet_id": "<subnet_uuid>", "security_groups": ["<sg_uuid>"]}]
            ],
            "security_groups": [
                ["<sg_uuid1>", "<sg_uuid2>"]
            ],
        }
        
        return examples.get(param_name, [])
    
    @staticmethod
    def get_union_type_description_enhancement(param_name: str, base_description: str) -> str:
        """Enhance union type descriptions with domain-specific examples."""
        if param_name == "volumes":
            return (
                base_description + 
                '. Example for a boot volume: `{"source": "image", "image_id": "...", '
                '"boot_index": 0, "size": 50}`'
            )
        return base_description
    
    @staticmethod
    def get_json_conversion_parameters() -> Set[str]:
        """Get parameters that need automatic JSON string conversion."""
        return {"volumes", "interfaces", "security_groups"}
    
    @staticmethod
    def is_special_parameter(param_name: str) -> bool:
        """Check if a parameter requires special domain handling."""
        return param_name in GCORE_SPECIAL_PARAMETERS
    
    @staticmethod
    def get_resource_shortening_rules() -> Dict[str, str]:
        """Get resource name shortening rules for tool names."""
        return {
            # Core resources
            "instances": "insts",
            "flavors": "flavs",
            "images": "imgs",
            "snapshots": "snaps",
            "volumes": "vols",
            "networks": "nets",
            "subnets": "subs",
            "routers": "rtrs",
            "ports": "ports",
            "floating_ips": "fips",
            "reserved_fixed_ips": "rfips",
            "load_balancers": "lb",
            "listeners": "lnrs",
            "pools": "pools",
            "members": "mbrs",
            "health_monitors": "hms",
            "l7policies": "l7pols",
            "l7rules": "l7rules",
            "security_groups": "secgrps",
            "security_group_rules": "secgrp_rules",
            "placement_groups": "placegrps",
            "ssh_keys": "sshkeys",
            "keypairs": "keypairs",
            "quotas": "quotas",
            "projects": "projs",
            "regions": "rgns",
            "secrets": "secr",
            "clusters": "clstrs",
            "nodes": "nodes",
            "registries": "regs",
            "file_shares": "fshares",
            "ai_clusters": "ai_clstrs",
            "inference": "infer",
            "deployments": "deploys",
        }
    
    @staticmethod
    def get_method_shortening_rules() -> Dict[str, str]:
        """Get method name shortening rules for tool names."""
        return {
            # CRUD operations
            "create": "new",
            "delete": "del",
            "list": "ls",
            "update": "upd",
            "replace": "repl",
            
            # Instance operations
            "assign_security_group": "assign_secgrp",
            "unassign_security_group": "unassign_secgrp",
            "add_to_placement_group": "add_placegrp",
            "remove_from_placement_group": "rm_placegrp",
            "disable_port_security": "dis_portsec",
            "enable_port_security": "en_portsec",
            "get_console": "console",
            "resize": "resize",
            "action": "action",
            "create_from_volume": "new_vol",
            "upload": "upload",
            "download": "download",
            
            # Volume operations
            "change_type": "chg_type",
            "revert_to_last_snapshot": "revert_snap",
            "attach_to_instance": "att_inst",
            "detach_from_instance": "det_inst",
            "extend": "extend",
            "create_snapshot": "snap",
            "revert": "revert",
            "get_capacity_by_region": "get_cap_region",
            
            # Network operations
            "attach_subnet": "att_sub",
            "detach_subnet": "det_sub",
            "attach_router": "att_rtr",
            "detach_router": "det_rtr",
            
            # Load balancer operations
            "add_member": "add_mbr",
            "remove_member": "rm_mbr",
            "failover": "failover",
            
            # Security operations
            "copy": "copy",
            "revert_to_default": "revert_def",
            
            # GPU operations
            "hard_reboot": "hard_reboot",
            "soft_reboot": "soft_reboot",
            "start": "start",
            "stop": "stop",
            "suspend": "suspend",
            "resume": "resume",
            "rebuild": "rebuild",
        }
    
    @staticmethod
    def get_toolset_definitions() -> Dict[str, List[str]]:
        """Get Gcore-specific toolset definitions."""
        return {
            "instances": [
                # Instances
                "cloud.instances.create", "cloud.instances.list", "cloud.instances.get", 
                "cloud.instances.update", "cloud.instances.delete",
                "cloud.instances.assign_security_group", "cloud.instances.unassign_security_group", 
                "cloud.instances.resize", "cloud.instances.get_console",
                "cloud.instances.add_to_placement_group", "cloud.instances.remove_from_placement_group", 
                "cloud.instances.disable_port_security", "cloud.instances.enable_port_security", 
                "cloud.instances.action",
                "cloud.instances.flavors.list", "cloud.instances.flavors.list_suitable", 
                "cloud.instances.flavors.list_for_resize",
                "cloud.instances.interfaces.list", "cloud.instances.interfaces.attach", 
                "cloud.instances.interfaces.detach",
                "cloud.instances.images.create_from_volume", "cloud.instances.images.list", 
                "cloud.instances.images.get", "cloud.instances.images.update",
                "cloud.instances.images.delete", "cloud.instances.images.upload",
                "cloud.instances.metrics.list",
            ],
            "baremetal": [
                # Bare Metal
                "cloud.baremetal.create", "cloud.baremetal.list", "cloud.baremetal.get", 
                "cloud.baremetal.update", "cloud.baremetal.delete",
                "cloud.baremetal.action", "cloud.baremetal.resize", "cloud.baremetal.get_console",
                "cloud.baremetal.assign_security_group", "cloud.baremetal.unassign_security_group",
                "cloud.baremetal.add_to_placement_group", "cloud.baremetal.remove_from_placement_group",
                "cloud.baremetal.disable_port_security", "cloud.baremetal.enable_port_security",
                "cloud.baremetal.flavors.list", "cloud.baremetal.flavors.list_suitable",
                "cloud.baremetal.interfaces.list", "cloud.baremetal.interfaces.attach", 
                "cloud.baremetal.interfaces.detach",
                "cloud.baremetal.metrics.list",
            ],
            "gpu": [
                # GPU Clusters
                "cloud.gpu_baremetal_clusters.create", "cloud.gpu_baremetal_clusters.list", 
                "cloud.gpu_baremetal_clusters.get", "cloud.gpu_baremetal_clusters.update", 
                "cloud.gpu_baremetal_clusters.delete",
                "cloud.gpu_baremetal_clusters.flavors.list",
                "cloud.gpu_baremetal_clusters.servers.create", "cloud.gpu_baremetal_clusters.servers.list", 
                "cloud.gpu_baremetal_clusters.servers.get", "cloud.gpu_baremetal_clusters.servers.delete",
                "cloud.gpu_baremetal_clusters.images.list", "cloud.gpu_baremetal_clusters.images.get", 
                "cloud.gpu_baremetal_clusters.images.update", "cloud.gpu_baremetal_clusters.images.delete",
            ],
            "networking": [
                # Networks
                "cloud.networks.create", "cloud.networks.list", "cloud.networks.get", 
                "cloud.networks.update", "cloud.networks.delete",
                "cloud.networks.subnets.create", "cloud.networks.subnets.list", 
                "cloud.networks.subnets.get", "cloud.networks.subnets.update", 
                "cloud.networks.subnets.delete",
                "cloud.networks.routers.create", "cloud.networks.routers.list", 
                "cloud.networks.routers.get", "cloud.networks.routers.update", 
                "cloud.networks.routers.delete",
                "cloud.networks.routers.attach_subnet", "cloud.networks.routers.detach_subnet",
                # Floating IPs
                "cloud.floating_ips.create", "cloud.floating_ips.list", "cloud.floating_ips.get", 
                "cloud.floating_ips.update", "cloud.floating_ips.delete",
                # Reserved Fixed IPs
                "cloud.reserved_fixed_ips.create", "cloud.reserved_fixed_ips.list", 
                "cloud.reserved_fixed_ips.get", "cloud.reserved_fixed_ips.update", 
                "cloud.reserved_fixed_ips.delete",
                # Load Balancers
                "cloud.load_balancers.create", "cloud.load_balancers.list", "cloud.load_balancers.get", 
                "cloud.load_balancers.update", "cloud.load_balancers.delete",
                "cloud.load_balancers.flavors.list",
                # Listeners
                "cloud.load_balancers.listeners.create", "cloud.load_balancers.listeners.list", 
                "cloud.load_balancers.listeners.get", "cloud.load_balancers.listeners.update", 
                "cloud.load_balancers.listeners.delete",
                # Pools
                "cloud.load_balancers.pools.create", "cloud.load_balancers.pools.list", 
                "cloud.load_balancers.pools.get", "cloud.load_balancers.pools.update", 
                "cloud.load_balancers.pools.delete",
                # L7 Policies
                "cloud.load_balancers.l7policies.create", "cloud.load_balancers.l7policies.list", 
                "cloud.load_balancers.l7policies.get", "cloud.load_balancers.l7policies.update", 
                "cloud.load_balancers.l7policies.delete",
            ],
            "security": [
                # Security Groups
                "cloud.security_groups.create", "cloud.security_groups.list", 
                "cloud.security_groups.get", "cloud.security_groups.update", 
                "cloud.security_groups.delete",
                "cloud.security_groups.copy", "cloud.security_groups.revert_to_default",
                "cloud.security_groups.rules.create", "cloud.security_groups.rules.replace", 
                "cloud.security_groups.rules.delete",
                # SSH Keys
                "cloud.ssh_keys.create", "cloud.ssh_keys.list", "cloud.ssh_keys.get", 
                "cloud.ssh_keys.update", "cloud.ssh_keys.delete",
                # Secrets
                "cloud.secrets.create", "cloud.secrets.list", "cloud.secrets.get", 
                "cloud.secrets.update", "cloud.secrets.delete",
            ],
            "storage": [
                # Volumes
                "cloud.volumes.create", "cloud.volumes.list", "cloud.volumes.get", 
                "cloud.volumes.update", "cloud.volumes.delete",
                "cloud.volumes.resize", "cloud.volumes.change_type", 
                "cloud.volumes.revert_to_last_snapshot",
                "cloud.volumes.attach_to_instance", "cloud.volumes.detach_from_instance",
                "cloud.volumes.snapshots.create", "cloud.volumes.snapshots.list", 
                "cloud.volumes.snapshots.get", "cloud.volumes.snapshots.update", 
                "cloud.volumes.snapshots.delete",
                # File Shares
                "cloud.file_shares.create", "cloud.file_shares.list", "cloud.file_shares.get", 
                "cloud.file_shares.update", "cloud.file_shares.delete",
                "cloud.file_shares.extend", "cloud.file_shares.get_capacity_by_region",
            ],
            "management": [
                # Projects
                "cloud.projects.create", "cloud.projects.list", "cloud.projects.get", 
                "cloud.projects.update", "cloud.projects.delete",
                # Regions
                "cloud.regions.list", "cloud.regions.get",
                # Placement Groups
                "cloud.placement_groups.create", "cloud.placement_groups.list", 
                "cloud.placement_groups.get", "cloud.placement_groups.update", 
                "cloud.placement_groups.delete",
                # Tasks
                "cloud.tasks.list", "cloud.tasks.get", "cloud.tasks.acknowledge_all", 
                "cloud.tasks.acknowledge_one",
                # Quotas
                "cloud.quotas.list", "cloud.quotas.get",
            ],
            "ai": [
                # AI Clusters
                "cloud.ai_clusters.create", "cloud.ai_clusters.list", "cloud.ai_clusters.get", 
                "cloud.ai_clusters.update", "cloud.ai_clusters.delete",
                # Inference
                "cloud.inference.deployments.create", "cloud.inference.deployments.list", 
                "cloud.inference.deployments.get", "cloud.inference.deployments.update", 
                "cloud.inference.deployments.delete",
            ],
            "containers": [
                # Registries
                "cloud.registries.create", "cloud.registries.list", "cloud.registries.get", 
                "cloud.registries.update", "cloud.registries.delete",
            ],
        }


# Global instance for easy access
_gcore_domain_handler = GcoreDomainHandler()


def get_gcore_domain_handler() -> GcoreDomainHandler:
    """Get the global Gcore domain handler instance."""
    return _gcore_domain_handler 