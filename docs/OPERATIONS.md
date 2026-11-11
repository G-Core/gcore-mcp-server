# Operations

Every operation of the `gcore` Python SDK v0.63.0 that this server exposes:
823 in total. Each one is named by its SDK path, which is also what
`GCORE_TOOLS` and `GCORE_DENY_TOOLS` patterns match (see the README, "Writing
patterns").

The access class decides what needs approval and what read-only mode allows:
**read** (no side effects), **write** (creates or changes something) and
**destructive** (deletes, overwrites, interrupts or weakens something; needs
approval by default).

To check a pattern, run `gcore-mcp-server --list 'cloud.volumes.*'`.

This file is generated from the installed SDK; a test fails when it is out of
date. Regenerate it with `UPDATE_SNAPSHOTS=1 uv run pytest tests/test_catalog.py`.

## cdn (106)

| operation | access | summary |
|---|---|---|
| `cdn.aliases.create` | write | Create an alias: a hostname you own that is served with the settings of one of your CDN resources and with its own SSL certificate. |
| `cdn.aliases.create_multiple` | write | Create up to 1000 aliases for one CDN resource in a single request. |
| `cdn.aliases.delete` | destructive | Delete an alias. |
| `cdn.aliases.delete_multiple` | destructive | Delete up to 1000 aliases in a single request, selected either by ID or by hostname. |
| `cdn.aliases.get` | read | Get alias details |
| `cdn.aliases.get_certificate_status` | read | Get details about the latest Let's Encrypt certificate issuance attempt for an alias, including the CNAME records to create for domain validation and the state of each domain validation challenge. |
| `cdn.aliases.list` | read | Get information about aliases. |
| `cdn.aliases.retry_certificate` | write | Start a new Let's Encrypt certificate issuance attempt for an alias that has none running. |
| `cdn.aliases.update` | write | Change an alias. |
| `cdn.audit_logs.get` | read | Get information about CDN activity logs record. |
| `cdn.audit_logs.list` | read | Get information about all CDN activity logs records. |
| `cdn.cdn_resources.create` | write | Create CDN resource |
| `cdn.cdn_resources.delete` | destructive | Delete the CDN resource from the system permanently. |
| `cdn.cdn_resources.get` | read | Get CDN resource details |
| `cdn.cdn_resources.list` | read | Get information about all CDN resources in your account. |
| `cdn.cdn_resources.prefetch` | write | Pre-populate files to a CDN cache before users requests. |
| `cdn.cdn_resources.prevalidate_ssl_le_certificate` | read | Check whether a Let's Encrypt certificate can be issued for the CDN resource. |
| `cdn.cdn_resources.purge` | write | Delete cache from CDN servers. |
| `cdn.cdn_resources.replace` | destructive | Change CDN resource |
| `cdn.cdn_resources.rules.create` | write | Create rule |
| `cdn.cdn_resources.rules.delete` | destructive | Delete the rule from the system permanently. |
| `cdn.cdn_resources.rules.get` | read | Get rule details |
| `cdn.cdn_resources.rules.list` | read | Get rules list |
| `cdn.cdn_resources.rules.replace` | destructive | Change rule |
| `cdn.cdn_resources.rules.update` | write | Change rule |
| `cdn.cdn_resources.shield.get` | read | Get information about origin shielding. |
| `cdn.cdn_resources.shield.replace` | destructive | Change origin shielding settings or disabled origin shielding. |
| `cdn.cdn_resources.update` | write | Change CDN resource |
| `cdn.certificates.create` | write | Add an SSL certificate for content delivery over HTTPS protocol. |
| `cdn.certificates.delete` | destructive | Delete SSL certificate |
| `cdn.certificates.force_retry` | write | Force retry issuance of Let's Encrypt certificate if the previous attempt was failed. |
| `cdn.certificates.get` | read | Get SSL certificate details |
| `cdn.certificates.get_status` | read | Get details about the latest Let's Encrypt certificate issuing attempt for the CDN resource. |
| `cdn.certificates.get_usage` | read | Get list of CDN resources and aliases that are using this SSL certificate. |
| `cdn.certificates.list` | read | Get information about SSL certificates. |
| `cdn.certificates.renew` | write | Renew free Let's Encrypt certificate for the CDN resource. |
| `cdn.certificates.replace` | destructive | Change SSL certificate |
| `cdn.client_config.get` | read | Get information about CDN service. |
| `cdn.get_account_limits` | read | Get information about CDN service limits. |
| `cdn.get_account_overview` | read | Get information about CDN service. |
| `cdn.get_available_features` | read | Get information about available CDN features. |
| `cdn.ip_ranges.list` | read | Get all CDN networks that can be used to pull content from your origin. |
| `cdn.ips.list` | read | Get all IP addresses of CDN servers that can be used to pull content from your origin. |
| `cdn.list_alibaba_regions` | read | Get the list of Alibaba Cloud regions. |
| `cdn.list_aws_regions` | read | Get the list of Amazon AWS regions. |
| `cdn.list_purge_statuses` | read | Get purges history. |
| `cdn.logs.download` | read | Download CDN logs for up to 3 days starting today. |
| `cdn.logs.list` | read | Get CDN logs for up to 3 days starting today. |
| `cdn.logs_uploader.configs.create` | write | Create logs uploader config. |
| `cdn.logs_uploader.configs.delete` | destructive | Delete the logs uploader config from the system permanently. |
| `cdn.logs_uploader.configs.get` | read | Get information about logs uploader config. |
| `cdn.logs_uploader.configs.list` | read | Get list of logs uploader configs. |
| `cdn.logs_uploader.configs.replace` | destructive | Change logs uploader config. |
| `cdn.logs_uploader.configs.update` | write | Change logs uploader config partially. |
| `cdn.logs_uploader.configs.validate` | read | Validate logs uploader config. |
| `cdn.logs_uploader.policies.create` | write | Create logs uploader policy. |
| `cdn.logs_uploader.policies.delete` | destructive | Delete the logs uploader policy from the system permanently. |
| `cdn.logs_uploader.policies.get` | read | Get information about logs uploader policy. |
| `cdn.logs_uploader.policies.list` | read | Get list of logs uploader policies. |
| `cdn.logs_uploader.policies.list_fields` | read | Get list of available fields for logs uploader policy. |
| `cdn.logs_uploader.policies.list_fields_allowed_conversions` | read | Get the available fields for a logs uploader policy, each with the conversion types it permits in `field_conversions`. |
| `cdn.logs_uploader.policies.replace` | destructive | Change logs uploader policy. |
| `cdn.logs_uploader.policies.update` | write | Change logs uploader policy partially. |
| `cdn.logs_uploader.targets.create` | write | Create logs uploader target. |
| `cdn.logs_uploader.targets.delete` | destructive | Delete the logs uploader target from the system permanently. |
| `cdn.logs_uploader.targets.get` | read | Get information about logs uploader target. |
| `cdn.logs_uploader.targets.list` | read | Get list of logs uploader targets. |
| `cdn.logs_uploader.targets.replace` | destructive | Change logs uploader target. |
| `cdn.logs_uploader.targets.update` | write | Change logs uploader target partially. |
| `cdn.logs_uploader.targets.validate` | read | Validate logs uploader target. |
| `cdn.metrics.list` | read | Get CDN metrics |
| `cdn.network_capacity.list` | read | Get network capacity per country. |
| `cdn.origin_groups.create` | write | Create an origin group with one or more origin sources. |
| `cdn.origin_groups.delete` | destructive | Delete origin group |
| `cdn.origin_groups.get` | read | Get origin group details |
| `cdn.origin_groups.list` | read | Get all origin groups and related origin sources. |
| `cdn.origin_groups.replace` | destructive | Change origin group |
| `cdn.origin_groups.update` | write | Change origin group |
| `cdn.presets.applied.apply` | write | Apply the preset to an object (CDN resource or rule, according to the preset `object_type`). |
| `cdn.presets.applied.get` | read | Get a single object the preset is applied to. |
| `cdn.presets.applied.get_objects` | read | Get the list of objects the preset is currently applied to. |
| `cdn.presets.applied.get_resource_preset` | read | Get the preset applied to a CDN resource and the list of resource fields managed by the preset. |
| `cdn.presets.applied.get_rule_preset` | read | Get the preset applied to a rule and the list of rule fields managed by the preset. |
| `cdn.presets.applied.unapply` | destructive | Unapply the preset from the object. |
| `cdn.presets.get` | read | Get information about a preset. |
| `cdn.presets.list` | read | Get the list of presets available to your account. |
| `cdn.rule_templates.create` | write | Create rule template |
| `cdn.rule_templates.delete` | destructive | Delete rule template |
| `cdn.rule_templates.get` | read | Get rule template details |
| `cdn.rule_templates.list` | read | Get rule templates list |
| `cdn.rule_templates.replace` | destructive | Change rule template |
| `cdn.rule_templates.update` | write | Change rule template |
| `cdn.shielding_location.list` | read | Get information about all origin shielding locations available in the account. |
| `cdn.statistics.get_alias_usage_aggregated` | read | Get the number of aliases in use. |
| `cdn.statistics.get_logs_usage_aggregated` | read | Get the number of CDN resources that used Logs uploader. |
| `cdn.statistics.get_logs_usage_series` | read | Get Logs uploader usage statistics for up to 90 days starting today. |
| `cdn.statistics.get_resource_usage_aggregated` | read | Get aggregated CDN resources statistics. |
| `cdn.statistics.get_resource_usage_series` | read | Get CDN resources statistics for up to 365 days starting today. |
| `cdn.statistics.get_shield_usage_aggregated` | read | The number of CDN resources that use origin shielding. |
| `cdn.statistics.get_shield_usage_series` | read | Get origin shielding usage statistics for up to 365 days starting from today. |
| `cdn.trusted_ca_certificates.create` | write | Add a trusted CA certificate to verify an origin. |
| `cdn.trusted_ca_certificates.delete` | destructive | Delete trusted CA certificate |
| `cdn.trusted_ca_certificates.get` | read | Get trusted CA certificate details |
| `cdn.trusted_ca_certificates.list` | read | Get list of trusted CA certificates used to verify an origin. |
| `cdn.trusted_ca_certificates.replace` | destructive | Change trusted CA certificate |
| `cdn.update_account` | write | Change information about CDN service. |

## cloud (413)

| operation | access | summary |
|---|---|---|
| `cloud.audit_logs.list` | read | Retrieve user action log for one client or a set of projects |
| `cloud.baremetal.flavors.list` | read | List all available bare metal flavors in the specified project and region. |
| `cloud.baremetal.images.list` | read | Retrieve a list of available images for bare metal servers. |
| `cloud.baremetal.servers.action` | destructive | The action can be one of: start, stop, reboot or `reboot_hard`. |
| `cloud.baremetal.servers.create` | write | Create a new bare metal server with the specified configuration. |
| `cloud.baremetal.servers.create_and_poll` | write | Create a bare metal server and wait for it to be ready. Waits for the task to finish. |
| `cloud.baremetal.servers.delete` | destructive | Delete a bare metal server and it's associated resources |
| `cloud.baremetal.servers.get` | read | Retrieve detailed information about a specific baremetal instance. |
| `cloud.baremetal.servers.list` | read | List all bare metal servers in the specified project and region. |
| `cloud.baremetal.servers.rebuild` | destructive | Rebuild a bare metal server with a new image while preserving its configuration. |
| `cloud.baremetal.servers.rebuild_and_poll` | destructive | Rebuild a bare metal server and wait for it to be ready. Waits for the task to finish. |
| `cloud.baremetal.servers.update` | write | Rename bare metal server or update tags |
| `cloud.billing_reservations.list` | read | Get a list of billing reservations along with detailed information on resource configurations and associated pricing. |
| `cloud.cost_reports.get_aggregated_monthly` | read | Retrieve a detailed cost report totals for a specified month, which includes both commit and pay-as-you-go (overcommit) prices. |
| `cloud.cost_reports.get_breakdown` | read | Get daily costs for a given period, summed down to one dimension: region (default), project, resource type or flavor. |
| `cloud.cost_reports.get_detailed` | read | Get a detailed cost report for a given period and specific resources, sorted by cost by default. |
| `cloud.databases.postgres.clusters.create` | write | Create a new PostgreSQL cluster with the specified configuration. |
| `cloud.databases.postgres.clusters.delete` | destructive | Delete a PostgreSQL cluster and all its associated resources. |
| `cloud.databases.postgres.clusters.get` | read | Get detailed information about a specific PostgreSQL cluster. |
| `cloud.databases.postgres.clusters.list` | read | List all PostgreSQL clusters in the specified project and region. |
| `cloud.databases.postgres.clusters.update` | write | Update the configuration of an existing PostgreSQL cluster. |
| `cloud.databases.postgres.clusters.user_credentials.get` | read | Get the credentials for a specific user in a PostgreSQL cluster. |
| `cloud.databases.postgres.clusters.user_credentials.regenerate` | destructive | Generate new credentials for a specific user in a PostgreSQL cluster. |
| `cloud.databases.postgres.configurations.get` | read | Get all available PostgreSQL configurations for the specified region. |
| `cloud.databases.postgres.custom_configurations.validate` | read | Validate a custom PostgreSQL configuration file. |
| `cloud.file_shares.access_rules.create` | write | Create file share access rule |
| `cloud.file_shares.access_rules.delete` | destructive | Delete file share access rule |
| `cloud.file_shares.access_rules.list` | read | List file share access rules |
| `cloud.file_shares.create` | write | Create file share |
| `cloud.file_shares.create_and_poll` | write | Create file share and poll for the result. |
| `cloud.file_shares.delete` | destructive | Delete file share |
| `cloud.file_shares.delete_and_poll` | destructive | Delete file share and poll for the result. |
| `cloud.file_shares.get` | read | Get file share |
| `cloud.file_shares.list` | read | List file shares |
| `cloud.file_shares.resize` | destructive | Resize file share |
| `cloud.file_shares.resize_and_poll` | destructive | Resize file share and poll for the result. |
| `cloud.file_shares.update` | write | Rename file share, update tags or set share specific properties |
| `cloud.file_shares.update_and_poll` | write | Rename file share, update tags or set share specific properties. Waits for the task to finish. |
| `cloud.floating_ips.assign` | write | Assign floating IP to instance or loadbalancer. |
| `cloud.floating_ips.create` | write | Create floating IP |
| `cloud.floating_ips.create_and_poll` | write | Create floating IP and poll for the result. |
| `cloud.floating_ips.delete` | destructive | Delete floating IP |
| `cloud.floating_ips.delete_and_poll` | destructive | Delete floating IP and poll for the result. |
| `cloud.floating_ips.get` | read | Get floating IP |
| `cloud.floating_ips.list` | read | List floating IPs |
| `cloud.floating_ips.unassign` | destructive | **Deprecated**: Use `PATCH /v2/floatingips/{project_id}/{region_id}/{floating_ip_id}` instead. |
| `cloud.floating_ips.update` | destructive | This endpoint updates the association and tags of an existing Floating IP. |
| `cloud.floating_ips.update_and_poll` | destructive | Update floating IP and poll for the result. |
| `cloud.gpu_baremetal.clusters.action` | destructive | Immediately perform a specific action on all instances in baremetal GPU cluster. |
| `cloud.gpu_baremetal.clusters.action_and_poll` | destructive | Perform an action on a bare metal GPU cluster and poll for the result. |
| `cloud.gpu_baremetal.clusters.apply_settings` | destructive | Apply updated server settings to all servers in a bare metal GPU cluster. |
| `cloud.gpu_baremetal.clusters.apply_settings_and_poll` | destructive | Apply the cluster's server settings to all of its servers and poll for the result. |
| `cloud.gpu_baremetal.clusters.create` | write | Create a new bare metal GPU cluster with the specified configuration. |
| `cloud.gpu_baremetal.clusters.create_and_poll` | write | Create a bare metal GPU cluster and wait for it to be ready. Waits for the task to finish. |
| `cloud.gpu_baremetal.clusters.delete` | destructive | Delete a bare metal GPU cluster and all its associated resources. |
| `cloud.gpu_baremetal.clusters.delete_and_poll` | destructive | Delete a bare metal GPU cluster and poll for the result. |
| `cloud.gpu_baremetal.clusters.flavors.list` | read | List bare metal GPU flavors |
| `cloud.gpu_baremetal.clusters.get` | read | Get detailed information about a specific bare metal GPU cluster. |
| `cloud.gpu_baremetal.clusters.images.delete` | destructive | Delete bare metal GPU image |
| `cloud.gpu_baremetal.clusters.images.delete_and_poll` | destructive | Delete a bare metal GPU image and poll for the result. |
| `cloud.gpu_baremetal.clusters.images.get` | read | Get bare metal GPU image |
| `cloud.gpu_baremetal.clusters.images.list` | read | List bare metal GPU images |
| `cloud.gpu_baremetal.clusters.images.upload` | write | Upload new bare metal GPU image |
| `cloud.gpu_baremetal.clusters.images.upload_and_poll` | write | Upload a new bare metal GPU image and wait for the upload to complete. Waits for the task to finish. |
| `cloud.gpu_baremetal.clusters.interfaces.attach` | write | Attach interface to bare metal GPU cluster server. |
| `cloud.gpu_baremetal.clusters.interfaces.detach` | destructive | Detach interface from bare metal GPU cluster server. |
| `cloud.gpu_baremetal.clusters.interfaces.list` | read | Retrieve a list of network interfaces attached to the GPU cluster servers. |
| `cloud.gpu_baremetal.clusters.list` | read | List all bare metal GPU clusters in the specified project and region. |
| `cloud.gpu_baremetal.clusters.powercycle_all_servers` | destructive | Please use the `/v3/gpu/baremetal/{project_id}/{region_id}/clusters/{cluster_id}/action` instead. |
| `cloud.gpu_baremetal.clusters.reboot_all_servers` | destructive | Please use the `/v3/gpu/baremetal/{project_id}/{region_id}/clusters/{cluster_id}/action` instead. |
| `cloud.gpu_baremetal.clusters.rebuild` | destructive | Use `POST /v3/gpu/baremetal/{project_id}/{region_id}/clusters/{cluster_id}/apply_settings` instead. |
| `cloud.gpu_baremetal.clusters.rebuild_and_poll` | destructive | Rebuild a bare metal GPU cluster and poll for the result. |
| `cloud.gpu_baremetal.clusters.resize` | destructive | Change the number of nodes in a GPU cluster. |
| `cloud.gpu_baremetal.clusters.resize_and_poll` | destructive | Resize a bare metal GPU cluster and poll for the result. |
| `cloud.gpu_baremetal.clusters.servers.apply_settings` | destructive | Apply updated server settings to a specific server in a bare metal GPU cluster. |
| `cloud.gpu_baremetal.clusters.servers.apply_settings_and_poll` | destructive | Apply the cluster's server settings to a single server and poll for the result. |
| `cloud.gpu_baremetal.clusters.servers.delete` | destructive | Delete a specific node from a GPU cluster. |
| `cloud.gpu_baremetal.clusters.servers.delete_and_poll` | destructive | Delete a bare metal GPU server from cluster and poll for the result. |
| `cloud.gpu_baremetal.clusters.servers.get_console` | read | Get bare metal GPU cluster server console URL |
| `cloud.gpu_baremetal.clusters.servers.list` | read | List all servers in a bare metal GPU cluster. |
| `cloud.gpu_baremetal.clusters.servers.powercycle` | destructive | Stops and then starts the server, performing a hard reboot. |
| `cloud.gpu_baremetal.clusters.servers.reboot` | destructive | Reboot one bare metal GPU cluster server |
| `cloud.gpu_baremetal.clusters.servers.rebuild` | destructive | Rebuild a single server in a bare metal GPU cluster with a chosen image, user data, and SSH key. |
| `cloud.gpu_baremetal.clusters.servers.rebuild_and_poll` | destructive | Rebuild a bare metal GPU cluster server and poll for the result. |
| `cloud.gpu_baremetal.clusters.servers.replace` | destructive | Delete a server from the cluster and provision a new one in its place, maintaining the cluster size. |
| `cloud.gpu_baremetal.clusters.servers.replace_and_poll` | destructive | Replace a bare metal GPU cluster server and poll for the result. |
| `cloud.gpu_baremetal.clusters.update` | write | Update the name, tags, and/or server settings of an existing bare metal GPU cluster. |
| `cloud.gpu_baremetal.clusters.update_servers_settings` | write | Use `PATCH /v3/gpu/baremetal/{project_id}/{region_id}/clusters/{cluster_id}` instead, which now accepts `servers_settings` and `image_id` fields alongside `name` and `tags`. |
| `cloud.gpu_virtual.clusters.action` | destructive | Perform a specific action on a virtual GPU cluster. |
| `cloud.gpu_virtual.clusters.action_and_poll` | destructive | Perform an action on a virtual GPU cluster and poll for the result. |
| `cloud.gpu_virtual.clusters.create` | write | Create a new virtual GPU cluster with the specified configuration. |
| `cloud.gpu_virtual.clusters.create_and_poll` | write | Create a virtual GPU cluster and wait for it to be ready. Waits for the task to finish. |
| `cloud.gpu_virtual.clusters.delete` | destructive | Delete a virtual GPU cluster and all its associated resources. |
| `cloud.gpu_virtual.clusters.delete_and_poll` | destructive | Delete a virtual GPU cluster and poll for the result. |
| `cloud.gpu_virtual.clusters.flavors.list` | read | List virtual GPU flavors |
| `cloud.gpu_virtual.clusters.get` | read | Get detailed information about a specific virtual GPU cluster. |
| `cloud.gpu_virtual.clusters.images.delete` | destructive | Delete virtual GPU image |
| `cloud.gpu_virtual.clusters.images.delete_and_poll` | destructive | Delete a virtual GPU image and poll for the result. |
| `cloud.gpu_virtual.clusters.images.get` | read | Get virtual GPU image |
| `cloud.gpu_virtual.clusters.images.list` | read | List virtual GPU images |
| `cloud.gpu_virtual.clusters.images.upload` | write | Upload new virtual GPU image |
| `cloud.gpu_virtual.clusters.images.upload_and_poll` | write | Upload a new virtual GPU image and wait for the upload to complete. Waits for the task to finish. |
| `cloud.gpu_virtual.clusters.interfaces.list` | read | List all network interfaces for servers in a virtual GPU cluster. |
| `cloud.gpu_virtual.clusters.list` | read | List all virtual GPU clusters in the specified project and region. |
| `cloud.gpu_virtual.clusters.servers.delete` | destructive | Delete a server from a virtual GPU cluster and its associated resources. |
| `cloud.gpu_virtual.clusters.servers.delete_and_poll` | destructive | Delete a server from a virtual GPU cluster and poll for the result. |
| `cloud.gpu_virtual.clusters.servers.list` | read | List all servers in a virtual GPU cluster. |
| `cloud.gpu_virtual.clusters.update` | write | Update the name, tags, and/or server settings of an existing virtual GPU cluster. |
| `cloud.gpu_virtual.clusters.volumes.list` | read | List all volumes attached to servers in a virtual GPU cluster. |
| `cloud.inference.api_keys.create` | write | This endpoint creates a new API key for everywhere inference. |
| `cloud.inference.api_keys.delete` | destructive | This endpoint deletes a specific API key for everywhere inference. |
| `cloud.inference.api_keys.get` | read | This endpoint retrieves a specific API key for everywhere inference. |
| `cloud.inference.api_keys.list` | read | This endpoint retrieves a list of API keys for everywhere inference. |
| `cloud.inference.api_keys.update` | write | This endpoint updates a specific API key for everywhere inference. |
| `cloud.inference.applications.deployments.create` | write | Creates a new application deployment based on a selected catalog application. |
| `cloud.inference.applications.deployments.delete` | destructive | Deletes an existing application deployment along with all associated resources. |
| `cloud.inference.applications.deployments.get` | read | Retrieves detailed information about a specific application deployment. |
| `cloud.inference.applications.deployments.list` | read | Returns a list of your application deployments, including deployment names, associated catalog applications, regions, component configurations, and current status. |
| `cloud.inference.applications.deployments.update` | write | Updates an existing application deployment. |
| `cloud.inference.applications.templates.get` | read | Retrieves detailed information about a specific machine learning application template from the catalog. |
| `cloud.inference.applications.templates.list` | read | Returns a list of available machine learning application templates from the catalog. |
| `cloud.inference.deployments.create` | write | Create inference deployment |
| `cloud.inference.deployments.create_and_poll` | write | Create inference deployment. Waits for the task to finish. |
| `cloud.inference.deployments.delete` | destructive | Delete inference deployment |
| `cloud.inference.deployments.delete_and_poll` | destructive | Delete inference deployment and poll for the result. |
| `cloud.inference.deployments.get` | read | Get inference deployment |
| `cloud.inference.deployments.list` | read | List inference deployments |
| `cloud.inference.deployments.logs.list` | read | Get inference deployment logs |
| `cloud.inference.deployments.start` | write | This operation initializes an inference deployment after it was stopped, making it available to handle inference requests again. |
| `cloud.inference.deployments.stop` | destructive | This operation shuts down an inference deployment, making it unavailable for handling requests. |
| `cloud.inference.deployments.update` | write | Update inference deployment |
| `cloud.inference.deployments.update_and_poll` | write | Update inference deployment and poll for the result. |
| `cloud.inference.flavors.get` | read | Get inference flavor |
| `cloud.inference.flavors.list` | read | List inference flavors |
| `cloud.inference.get_capacity_by_region` | read | Get inference capacity by region |
| `cloud.inference.registry_credentials.create` | write | Create inference registry credential |
| `cloud.inference.registry_credentials.delete` | destructive | Delete inference registry credential |
| `cloud.inference.registry_credentials.get` | read | Get inference registry credential |
| `cloud.inference.registry_credentials.list` | read | List inference registry credentials |
| `cloud.inference.registry_credentials.replace` | destructive | Replace inference registry credential |
| `cloud.inference.secrets.create` | write | Create inference secret |
| `cloud.inference.secrets.delete` | destructive | Delete Inference Secret |
| `cloud.inference.secrets.delete_and_poll` | destructive | Delete an inference secret and poll until the API stops reporting it. |
| `cloud.inference.secrets.get` | read | Get inference secret |
| `cloud.inference.secrets.list` | read | List inference secrets |
| `cloud.inference.secrets.replace` | destructive | Replace inference secret |
| `cloud.instances.action` | destructive | The action can be one of: start, stop, reboot, `reboot_hard`, suspend or resume. |
| `cloud.instances.action_and_poll` | destructive | Perform the action on the instance and poll for the result. |
| `cloud.instances.add_to_placement_group` | write | Add an instance to a placement group. |
| `cloud.instances.add_to_placement_group_and_poll` | write | Put instance into the server group and poll for the result. |
| `cloud.instances.assign_security_group` | write | Assign the security group to the server. |
| `cloud.instances.create` | write | Create an instance with specified configuration. |
| `cloud.instances.create_and_poll` | write | Create one or many instances or basic VMs and poll for the result. |
| `cloud.instances.delete` | destructive | Delete instance |
| `cloud.instances.delete_and_poll` | destructive | Delete instance and poll for the result. |
| `cloud.instances.disable_port_security` | destructive | Deprecated. |
| `cloud.instances.enable_port_security` | write | Deprecated. |
| `cloud.instances.flavors.list` | read | Retrieve a list of available instance flavors in the project and region. |
| `cloud.instances.get` | read | Retrieve detailed information about a specific instance. |
| `cloud.instances.get_console` | read | Returns a URL to access the remote console for an instance. |
| `cloud.instances.images.create_from_volume` | write | Create a new image from a bootable volume. |
| `cloud.instances.images.create_from_volume_and_poll` | write | Create image from volume and poll for completion |
| `cloud.instances.images.delete` | destructive | Delete a specific image. |
| `cloud.instances.images.delete_and_poll` | destructive | Delete image and poll for the result. |
| `cloud.instances.images.get` | read | Retrieve detailed information about a specific image. |
| `cloud.instances.images.list` | read | Retrieve a list of available images in the project and region. |
| `cloud.instances.images.update` | write | Update image properties and tags. |
| `cloud.instances.images.upload` | write | Upload an image from a URL. |
| `cloud.instances.images.upload_and_poll` | write | Upload image and poll for completion |
| `cloud.instances.interfaces.attach` | write | Attach interface to instance |
| `cloud.instances.interfaces.attach_and_poll` | write | Attach interface to instance using external extend and poll for completion. |
| `cloud.instances.interfaces.detach` | destructive | Detach interface from instance |
| `cloud.instances.interfaces.detach_and_poll` | destructive | Detach interface from instance and poll for completion. |
| `cloud.instances.interfaces.list` | read | List all network interfaces attached to the specified instance. |
| `cloud.instances.list` | read | List all instances in the specified project and region. |
| `cloud.instances.metrics.list` | read | Get instance metrics, including cpu, memory, network and disk metrics |
| `cloud.instances.rebuild` | destructive | Rebuild instance with a new image while preserving its configuration. |
| `cloud.instances.rebuild_and_poll` | destructive | Rebuild the instance and poll for the result. |
| `cloud.instances.remove_from_placement_group` | destructive | Remove an instance from its current placement group. |
| `cloud.instances.remove_from_placement_group_and_poll` | destructive | Remove instance from the server group and poll for the result. |
| `cloud.instances.resize` | destructive | Change flavor of the instance. |
| `cloud.instances.resize_and_poll` | destructive | Change flavor of the instance and poll for the result. |
| `cloud.instances.unassign_security_group` | destructive | Un-assign the security group to the server. |
| `cloud.instances.update` | write | Rename instance or update tags |
| `cloud.ip_ranges.list` | read | Returns the complete list of IPv4 and IPv6 address ranges that Cloud uses for outbound (egress) traffic. |
| `cloud.k8s.clusters.create` | write | Create k8s cluster |
| `cloud.k8s.clusters.create_and_poll` | write | Create a k8s cluster and poll for the result. |
| `cloud.k8s.clusters.delete` | destructive | Delete k8s cluster |
| `cloud.k8s.clusters.delete_and_poll` | destructive | Delete a k8s cluster and poll for the result. |
| `cloud.k8s.clusters.get` | read | Get k8s cluster |
| `cloud.k8s.clusters.get_certificate` | read | Get k8s cluster CA certificate |
| `cloud.k8s.clusters.kubeconfig.get` | read | Get k8s cluster kubeconfig |
| `cloud.k8s.clusters.list` | read | List k8s clusters |
| `cloud.k8s.clusters.list_versions_for_upgrade` | read | List available k8s cluster versions for upgrade |
| `cloud.k8s.clusters.nodes.delete` | destructive | After deletion, the node will be automatically recreated to maintain the desired pool size. |
| `cloud.k8s.clusters.nodes.list` | read | List k8s cluster nodes |
| `cloud.k8s.clusters.pools.check_quota` | read | Calculate quota requirements for a new cluster pool before creation. |
| `cloud.k8s.clusters.pools.create` | write | Create k8s cluster pool |
| `cloud.k8s.clusters.pools.create_and_poll` | write | Create a k8s cluster pool and poll for the result. |
| `cloud.k8s.clusters.pools.delete` | destructive | Delete k8s cluster pool |
| `cloud.k8s.clusters.pools.delete_and_poll` | destructive | Delete a k8s cluster pool and poll for the result. |
| `cloud.k8s.clusters.pools.get` | read | Get k8s cluster pool |
| `cloud.k8s.clusters.pools.list` | read | List k8s cluster pools |
| `cloud.k8s.clusters.pools.nodes.delete` | destructive | After deletion, the node will be automatically recreated to maintain the desired pool size. |
| `cloud.k8s.clusters.pools.nodes.list` | read | List k8s cluster pool nodes |
| `cloud.k8s.clusters.pools.resize` | destructive | Resize k8s cluster pool |
| `cloud.k8s.clusters.pools.resize_and_poll` | destructive | Resize a k8s cluster pool and poll for the result. |
| `cloud.k8s.clusters.pools.update` | write | Update k8s cluster pool |
| `cloud.k8s.clusters.update` | write | Update k8s cluster |
| `cloud.k8s.clusters.update_and_poll` | write | Update a k8s cluster and poll for the result. |
| `cloud.k8s.clusters.upgrade` | destructive | Upgrade k8s cluster |
| `cloud.k8s.clusters.upgrade_and_poll` | destructive | Upgrade a k8s cluster and poll for the result. |
| `cloud.k8s.flavors.list` | read | Retrieve a list of flavors for k8s pool. |
| `cloud.k8s.list_versions` | read | List available k8s cluster versions for creation |
| `cloud.load_balancers.create` | write | Create load balancer |
| `cloud.load_balancers.create_and_poll` | write | Create load balancer. Waits for the task to finish. |
| `cloud.load_balancers.delete` | destructive | Delete load balancer |
| `cloud.load_balancers.delete_and_poll` | destructive | Delete load balancer and poll for the result. |
| `cloud.load_balancers.failover` | destructive | Failover load balancer |
| `cloud.load_balancers.failover_and_poll` | destructive | Failover load balancer and poll for the result. |
| `cloud.load_balancers.flavors.list` | read | Retrieve a list of load balancer flavors. |
| `cloud.load_balancers.get` | read | Get load balancer |
| `cloud.load_balancers.l7_policies.create` | write | Create load balancer L7 policy |
| `cloud.load_balancers.l7_policies.create_and_poll` | write | Create L7 policy and poll for completion. |
| `cloud.load_balancers.l7_policies.delete` | destructive | Delete load balancer L7 policy |
| `cloud.load_balancers.l7_policies.delete_and_poll` | destructive | Delete load balancer L7 policy. Waits for the task to finish. |
| `cloud.load_balancers.l7_policies.get` | read | Get load balancer L7 policy |
| `cloud.load_balancers.l7_policies.list` | read | List load balancer L7 policies |
| `cloud.load_balancers.l7_policies.rules.create` | write | Create load balancer L7 rule |
| `cloud.load_balancers.l7_policies.rules.create_and_poll` | write | Create load balancer L7 rule. Waits for the task to finish. |
| `cloud.load_balancers.l7_policies.rules.delete` | destructive | Delete load balancer L7 rule |
| `cloud.load_balancers.l7_policies.rules.delete_and_poll` | destructive | Delete L7 rule and poll for the result. |
| `cloud.load_balancers.l7_policies.rules.get` | read | Get load balancer L7 rule |
| `cloud.load_balancers.l7_policies.rules.list` | read | List load balancer L7 policy rules |
| `cloud.load_balancers.l7_policies.rules.replace` | destructive | Replace load balancer L7 rule properties |
| `cloud.load_balancers.l7_policies.rules.replace_and_poll` | destructive | Replace L7 rule and poll for the result. |
| `cloud.load_balancers.l7_policies.update` | write | Updates only provided fields; omitted ones stay unchanged. |
| `cloud.load_balancers.l7_policies.update_and_poll` | write | Update L7 policy and poll for completion. |
| `cloud.load_balancers.list` | read | List load balancers |
| `cloud.load_balancers.listeners.create` | write | Create load balancer listener |
| `cloud.load_balancers.listeners.create_and_poll` | write | Create load balancer listener. Waits for the task to finish. |
| `cloud.load_balancers.listeners.delete` | destructive | Delete load balancer listener |
| `cloud.load_balancers.listeners.delete_and_poll` | destructive | Delete listener and poll for the result. |
| `cloud.load_balancers.listeners.get` | read | Get load balancer listener |
| `cloud.load_balancers.listeners.list` | read | List load balancer listeners |
| `cloud.load_balancers.listeners.update` | write | Update load balancer listener |
| `cloud.load_balancers.listeners.update_and_poll` | write | Update listener and poll for the result. |
| `cloud.load_balancers.metrics.list` | read | Get load balancer metrics, including cpu, memory and network |
| `cloud.load_balancers.pools.create` | write | Create load balancer pool |
| `cloud.load_balancers.pools.create_and_poll` | write | Create load balancer pool. Waits for the task to finish. |
| `cloud.load_balancers.pools.delete` | destructive | Delete load balancer pool |
| `cloud.load_balancers.pools.delete_and_poll` | destructive | Delete pool and poll for the result. |
| `cloud.load_balancers.pools.get` | read | Get load balancer pool |
| `cloud.load_balancers.pools.health_monitors.create` | write | Creates a health monitor for a load balancer pool to automatically check the health status of pool members. |
| `cloud.load_balancers.pools.health_monitors.delete` | destructive | Removes the health monitor from a load balancer pool. |
| `cloud.load_balancers.pools.health_monitors.get` | read | Returns the health monitor configured for a load balancer pool, including its type, check intervals, timeouts, and the thresholds used to mark pool members as healthy or unhealthy. |
| `cloud.load_balancers.pools.health_monitors.update` | write | Updates the health monitor of a load balancer pool, such as its check intervals, timeouts, and the thresholds used to mark pool members as healthy or unhealthy. |
| `cloud.load_balancers.pools.list` | read | List load balancer pools |
| `cloud.load_balancers.pools.members.create` | write | Create load balancer pool member |
| `cloud.load_balancers.pools.members.create_and_poll` | write | Create pool member and poll for the result. |
| `cloud.load_balancers.pools.members.delete` | destructive | Delete load balancer pool member |
| `cloud.load_balancers.pools.members.delete_and_poll` | destructive | Delete pool member and poll for the result. |
| `cloud.load_balancers.pools.members.get` | read | Get load balancer pool member |
| `cloud.load_balancers.pools.members.list` | read | List load balancer pool members |
| `cloud.load_balancers.pools.members.replace` | destructive | Replaces the full set of pool members with the provided list (declarative, desired-state semantics): members present in the payload are created or updated, members currently on the pool but absent from the payload are deleted. |
| `cloud.load_balancers.pools.members.replace_and_poll` | destructive | Replace the pool's entire member list, poll for the result and return the resulting members. |
| `cloud.load_balancers.pools.members.update` | write | Updates the specified member's mutable settings. |
| `cloud.load_balancers.pools.members.update_and_poll` | write | Update pool member and poll for the result. |
| `cloud.load_balancers.pools.update` | write | Updates the specified load balancer pool with the provided changes. |
| `cloud.load_balancers.pools.update_and_poll` | write | Update pool and poll for the result. |
| `cloud.load_balancers.resize` | destructive | Resize load balancer |
| `cloud.load_balancers.resize_and_poll` | destructive | Resize load balancer and poll for the result. |
| `cloud.load_balancers.statuses.get` | read | Get load balancer status |
| `cloud.load_balancers.statuses.list` | read | List load balancers statuses |
| `cloud.load_balancers.update` | write | Rename load balancer, activate/deactivate logging, update preferred connectivity type and/or modify load balancer tags. |
| `cloud.networks.create` | write | Create network |
| `cloud.networks.create_and_poll` | write | Create network and poll for the result. |
| `cloud.networks.delete` | destructive | Delete network |
| `cloud.networks.delete_and_poll` | destructive | Delete network and poll for the result. |
| `cloud.networks.get` | read | Get network |
| `cloud.networks.list` | read | Returns a list of networks. |
| `cloud.networks.routers.attach_subnet` | write | Attach a subnet to an existing router. |
| `cloud.networks.routers.create` | write | Create a new router with the specified configuration. |
| `cloud.networks.routers.delete` | destructive | Delete a specific router and all its associated resources. |
| `cloud.networks.routers.detach_subnet` | destructive | Detach a subnet from an existing router. |
| `cloud.networks.routers.get` | read | Get detailed information about a specific router. |
| `cloud.networks.routers.list` | read | List all routers in the specified project and region. |
| `cloud.networks.routers.metrics.list` | read | Get the network traffic of each router interface, in bits and packets per second. |
| `cloud.networks.routers.update` | write | Update the configuration of an existing router. |
| `cloud.networks.routers.update_and_poll` | write | Update router and poll for the result. |
| `cloud.networks.subnets.create` | write | Create subnet |
| `cloud.networks.subnets.create_and_poll` | write | Create subnet and poll for the result. |
| `cloud.networks.subnets.delete` | destructive | Delete subnet |
| `cloud.networks.subnets.get` | read | Get subnet |
| `cloud.networks.subnets.list` | read | Returns a list of subnets. |
| `cloud.networks.subnets.update` | write | Update subnet |
| `cloud.networks.update` | write | Rename network and/or update network tags in a background task. |
| `cloud.networks.update_and_poll` | write | Update network and poll for the result. |
| `cloud.placement_groups.create` | write | Create an affinity or anti-affinity or soft-anti-affinity placement group |
| `cloud.placement_groups.delete` | destructive | Delete a placement group by its ID. |
| `cloud.placement_groups.get` | read | Retrieve a single placement group by its ID. |
| `cloud.placement_groups.list` | read | List all placement groups in the specified project and region. |
| `cloud.projects.create` | write | Create a new project for a client. |
| `cloud.projects.delete` | destructive | Delete a project and all its associated cloud resources across all regions. |
| `cloud.projects.get` | read | Retrieve detailed information about a specific project. |
| `cloud.projects.list` | read | Retrieve a list of projects for a client. |
| `cloud.projects.update` | write | This endpoint allows partial updates of a project (such as its name or description). |
| `cloud.quotas.get_all` | read | Get combined client quotas, including both regional and global quotas. |
| `cloud.quotas.get_by_region` | read | Get quotas for a specific region and client. |
| `cloud.quotas.get_global` | read | Get global quotas for a specific client. |
| `cloud.quotas.notification_threshold.delete` | destructive | Delete a client's quota notification threshold. |
| `cloud.quotas.notification_threshold.get` | read | Get a client's quota notification threshold. |
| `cloud.quotas.notification_threshold.update` | write | Update or create a client's quota notification threshold. |
| `cloud.quotas.requests.create` | write | Create a request to change current quotas. |
| `cloud.quotas.requests.delete` | destructive | Delete a specific quota limit request. |
| `cloud.quotas.requests.get` | read | Get detailed information about a specific quota limit request. |
| `cloud.quotas.requests.list` | read | Get a list of sent requests to change current quotas and their statuses. |
| `cloud.regions.get` | read | Get region |
| `cloud.regions.list` | read | List regions |
| `cloud.registries.artifacts.delete` | destructive | Delete a specific artifact from a repository. |
| `cloud.registries.artifacts.list` | read | List all artifacts in a specific repository. |
| `cloud.registries.create` | write | Create a new container registry with the specified configuration. |
| `cloud.registries.delete` | destructive | Delete a specific container registry and all its associated resources. |
| `cloud.registries.get` | read | Get detailed information about a specific container registry. |
| `cloud.registries.list` | read | List all container registries in the specified project and region. |
| `cloud.registries.repositories.delete` | destructive | Delete a specific repository from the container registry. |
| `cloud.registries.repositories.list` | read | List all repositories in the container registry. |
| `cloud.registries.resize` | destructive | Update the size of a container registry. |
| `cloud.registries.tags.delete` | destructive | Delete a specific tag from an artifact. |
| `cloud.registries.users.create` | write | Create a new user for accessing the container registry. |
| `cloud.registries.users.create_multiple` | write | Create multiple users for accessing the container registry in a single request. |
| `cloud.registries.users.delete` | destructive | Delete a specific user from the container registry. |
| `cloud.registries.users.list` | read | List all users with access to the container registry. |
| `cloud.registries.users.refresh_secret` | destructive | Generate a new secret for a specific registry user. |
| `cloud.registries.users.update` | write | Update the configuration of a specific registry user. |
| `cloud.reserved_fixed_ips.create` | write | Create a new reserved fixed IP with the specified configuration. |
| `cloud.reserved_fixed_ips.create_and_poll` | write | Create a new reserved fixed IP with the specified configuration and poll for the result. |
| `cloud.reserved_fixed_ips.delete` | destructive | Delete a specific reserved fixed IP and all its associated resources. |
| `cloud.reserved_fixed_ips.delete_and_poll` | destructive | Delete a specific reserved fixed IP and all its associated resources and poll for the result. |
| `cloud.reserved_fixed_ips.get` | read | Get detailed information about a specific reserved fixed IP. |
| `cloud.reserved_fixed_ips.list` | read | List all reserved fixed IPs in the specified project and region. |
| `cloud.reserved_fixed_ips.update` | destructive | Update the VIP status of a reserved fixed IP. |
| `cloud.reserved_fixed_ips.vip.candidate_ports.list` | read | List all instance ports that are available for connecting to a VIP. |
| `cloud.reserved_fixed_ips.vip.connected_ports.add` | write | Add instance ports to share a VIP. |
| `cloud.reserved_fixed_ips.vip.connected_ports.list` | read | List all instance ports that share a VIP. |
| `cloud.reserved_fixed_ips.vip.connected_ports.replace` | destructive | Replace the list of instance ports that share a VIP. |
| `cloud.reserved_fixed_ips.vip.toggle` | destructive | Update the VIP status of a reserved fixed IP. |
| `cloud.secrets.delete` | destructive | Delete secret |
| `cloud.secrets.get` | read | Get secret |
| `cloud.secrets.list` | read | List secrets |
| `cloud.secrets.upload_tls_certificate` | write | Create secret |
| `cloud.secrets.upload_tls_certificate_and_poll` | write | Create secret. Waits for the task to finish. |
| `cloud.security_groups.create` | write | Creates a new security group. |
| `cloud.security_groups.create_and_poll` | write | Create security group and poll for the result. |
| `cloud.security_groups.delete` | destructive | Delete a specific security group and all its associated rules. |
| `cloud.security_groups.get` | read | Get detailed information about a specific security group. |
| `cloud.security_groups.list` | read | List all security groups in the specified project and region. |
| `cloud.security_groups.revert_to_default` | destructive | Revert a security group to its previous state. |
| `cloud.security_groups.rules.create` | write | Add a new rule to an existing security group. |
| `cloud.security_groups.rules.create_and_poll` | write | Create a security group rule and poll for completion. |
| `cloud.security_groups.rules.delete` | destructive | Delete a specific rule from a security group. |
| `cloud.security_groups.rules.delete_and_poll` | destructive | Delete a security group rule and poll for completion. |
| `cloud.security_groups.rules.replace` | destructive | Update the configuration of an existing security group rule. |
| `cloud.security_groups.update` | write | Updates the specified security group with the provided changes. |
| `cloud.security_groups.update_and_poll` | write | Update security group and poll for the result. |
| `cloud.snapshot_schedules.add_schedules` | write | Add new schedules to an existing snapshot policy. |
| `cloud.snapshot_schedules.add_volumes` | write | Add volumes to an existing snapshot policy. |
| `cloud.snapshot_schedules.create` | write | Create a new snapshot policy with the specified configuration. |
| `cloud.snapshot_schedules.delete` | destructive | Delete a specific snapshot policy and all its associated schedules. |
| `cloud.snapshot_schedules.estimate_max_usage` | read | Calculate the maximum resource usage if all snapshots are created by the policy. |
| `cloud.snapshot_schedules.get` | read | Get detailed information about a specific snapshot policy. |
| `cloud.snapshot_schedules.list` | read | List all snapshot policies in the specified project and region. |
| `cloud.snapshot_schedules.remove_schedules` | destructive | Remove schedules from an existing snapshot policy. |
| `cloud.snapshot_schedules.remove_volumes` | destructive | Remove volumes from an existing snapshot policy. |
| `cloud.snapshot_schedules.update` | write | Update the configuration of an existing snapshot policy. |
| `cloud.ssh_keys.create` | write | To generate a key, omit the `public_key` parameter from the request body |
| `cloud.ssh_keys.delete` | destructive | Delete SSH key |
| `cloud.ssh_keys.get` | read | Get SSH key |
| `cloud.ssh_keys.list` | read | List SSH keys |
| `cloud.ssh_keys.update` | write | Share or unshare SSH key with users |
| `cloud.tasks.acknowledge_all` | write | Acknowledge all tasks |
| `cloud.tasks.acknowledge_one` | write | Acknowledge one task |
| `cloud.tasks.get` | read | Get task |
| `cloud.tasks.list` | read | List tasks |
| `cloud.tasks.poll` | read | Poll tasks. |
| `cloud.usage_reports.get` | read | Data from the past hour may not reflect the full set of statistics. |
| `cloud.users.role_assignments.create` | write | Assign a role to an existing user in the specified scope. |
| `cloud.users.role_assignments.delete` | destructive | Delete an existing role assignment. |
| `cloud.users.role_assignments.list` | read | List all role assignments in the specified scope. |
| `cloud.users.role_assignments.update` | write | Modify an existing role assignment for a user. |
| `cloud.volume_snapshots.create` | write | Create a new snapshot from a volume. |
| `cloud.volume_snapshots.create_and_poll` | write | Create a new snapshot from a volume and poll for the result. |
| `cloud.volume_snapshots.delete` | destructive | Delete a specific snapshot. |
| `cloud.volume_snapshots.delete_and_poll` | destructive | Delete a specific snapshot and poll for the result. |
| `cloud.volume_snapshots.get` | read | Get detailed information about a specific snapshot. |
| `cloud.volume_snapshots.list` | read | List all volume snapshots in the specified project and region. |
| `cloud.volume_snapshots.update` | write | Rename snapshot or update tags. |
| `cloud.volumes.attach_to_instance` | write | Attach the volume to instance. |
| `cloud.volumes.attach_to_instance_and_poll` | write | Attach the volume to instance and poll for the result. |
| `cloud.volumes.change_type` | write | Change the type of a volume. |
| `cloud.volumes.create` | write | Create a new volume in the project and region. |
| `cloud.volumes.create_and_poll` | write | Create a new volume in the project and region and poll for the result. |
| `cloud.volumes.delete` | destructive | Delete a volume and all its snapshots. |
| `cloud.volumes.delete_and_poll` | destructive | Delete a volume and all its snapshots and poll for the result. |
| `cloud.volumes.detach_from_instance` | destructive | Detach the volume from instance |
| `cloud.volumes.detach_from_instance_and_poll` | destructive | Detach the volume from instance and poll for the result. |
| `cloud.volumes.get` | read | Retrieve detailed information about a specific volume. |
| `cloud.volumes.list` | read | Retrieve a list of volumes in the project and region. |
| `cloud.volumes.resize` | destructive | Increase the size of a volume. |
| `cloud.volumes.resize_and_poll` | destructive | Increase the size of a volume and poll for the result. |
| `cloud.volumes.revert_to_last_snapshot` | destructive | Revert a volume to its last snapshot. |
| `cloud.volumes.types.list` | read | Returns the capabilities and the QoS profile of each volume type, sorted by name. |
| `cloud.volumes.update` | write | Rename a volume or update tags |

## dns (35)

| operation | access | summary |
|---|---|---|
| `dns.get_account_overview` | read | Get info about client |
| `dns.locations.list` | read | List of All locations continents/countries/regions. |
| `dns.locations.list_continents` | read | List of All locations continents. |
| `dns.locations.list_countries` | read | List of All locations countries. |
| `dns.locations.list_regions` | read | List of All locations regions. |
| `dns.lookup` | read | Get the dns records from a specific domain or ip. |
| `dns.metrics.list` | read | Example of success response: ``` HELP healthcheck_state The `healthcheck_state` metric reflects the state of a specific monitor after conducting a health check TYPE healthcheck_state gauge healthcheck_state{client_id="1",monitor_id="431",monitor_locations="us-east-1,us-west-1",monitor_name="test-monitor-1",monitor_type="http",rrset_name="rrset-name1",rrset_type="rrset-type1",zone_name="zone-name1"} 0 healthcheck_state{client_id="1",monitor_id="4871",monitor_locations="fr-1,fr-2",monitor_name="test-monitor-2",monitor_type="tcp",rrset_name="rrset-name2",rrset_type="rrset-type2",zone_name="zone-name2"} 1 healthcheck_state{client_id="2",monitor_id="7123",monitor_locations="ua-1,ua-2",monitor_name="test-monitor-3",monitor_type="icmp",rrset_name="rrset-name3",rrset_type="rrset-type3",zone_name="zone-name3"} 0 ``` |
| `dns.network_mappings.create` | write | Create new network mapping. |
| `dns.network_mappings.delete` | destructive | Delete network mapping. |
| `dns.network_mappings.get` | read | Particular network mapping item info Example of request: ``` curl --location --request GET 'https://api.gcore.com/dns/v2/network-mappings/123' \ --header 'Authorization: Bearer ...' ``` |
| `dns.network_mappings.get_by_name` | read | Get network mapping by name. |
| `dns.network_mappings.import_` | write | Import network mapping from YAML file. |
| `dns.network_mappings.list` | read | List of network mappings. |
| `dns.network_mappings.replace` | destructive | Update network mapping (Note: name of network mapping cannot be changed) Example of request: ``` curl --location --request PUT 'https://api.gcore.com/dns/v2/network-mappings/123' \ --header 'Authorization: Bearer ...' \ --header 'Content-Type: application/json' \ --data-raw '{ "name": "test-mapping", "mapping": [ { "tags": [ "tag1" ], "cidr4": [ "192.0.2.0/24" ] }, { "tags": [ "tag2", "tag3" ], "cidr4": [ "192.1.2.0/24" ], "cidr6": [ "aa:10::/64" ] } ] }' ``` |
| `dns.pickers.list` | read | Returns list of picker |
| `dns.pickers.presets.list` | read | Returns list of picker preset |
| `dns.zones.check_delegation_status` | read | Returns delegation status for specified domain name. |
| `dns.zones.create` | write | Add DNS zone. |
| `dns.zones.delete` | destructive | Delete DNS zone and its records and raws. |
| `dns.zones.disable` | destructive | Disable DNS zone. |
| `dns.zones.dnssec.get` | read | Get DNSSEC DS for a DNS zone. |
| `dns.zones.dnssec.update` | destructive | Enable or disable DNSSEC for a DNS zone. |
| `dns.zones.enable` | write | Enable DNS zone. |
| `dns.zones.export` | read | Export zone to bind9 format. |
| `dns.zones.get` | read | Zone info by zone name. |
| `dns.zones.get_statistics` | read | Statistics of DNS zone in common and by record types. |
| `dns.zones.import_` | write | Import zone in bind9 format. |
| `dns.zones.list` | read | Show created zones with pagination managed by limit and offset params. |
| `dns.zones.replace` | destructive | Update DNS zone and SOA record. |
| `dns.zones.rrsets.create` | write | Add the RRSet to the zone specified by zoneName, RRSets can be configured to be either dynamic or static. |
| `dns.zones.rrsets.delete` | destructive | Delete RRset. |
| `dns.zones.rrsets.get` | read | Particular RRset item info |
| `dns.zones.rrsets.get_failover_logs` | read | Get failover history for the RRset |
| `dns.zones.rrsets.list` | read | List of RRset. |
| `dns.zones.rrsets.replace` | destructive | Create/update RRset. |

## fastedge (30)

| operation | access | summary |
|---|---|---|
| `fastedge.apps.create` | write | Create a new edge application from a WebAssembly binary. |
| `fastedge.apps.delete` | destructive | Permanently delete an application and remove it from all edge networks. |
| `fastedge.apps.get` | read | Retrieve complete configuration and metadata for a specific application. |
| `fastedge.apps.list` | read | Retrieve a paginated list of applications owned by the authenticated client. |
| `fastedge.apps.logs.list` | read | List logs for the app |
| `fastedge.apps.replace` | destructive | Replace the complete configuration of an existing application. |
| `fastedge.apps.update` | write | Partially update an application's configuration. |
| `fastedge.binaries.create` | write | Upload a compiled WebAssembly binary to the edge platform. |
| `fastedge.binaries.delete` | destructive | Delete a WebAssembly binary from the platform. |
| `fastedge.binaries.get` | read | Retrieve complete information about a specific WebAssembly binary including metadata and compiled content. |
| `fastedge.binaries.list` | read | Retrieve all WebAssembly binaries owned by the authenticated client. |
| `fastedge.get_account_overview` | read | Retrieve the authenticated client's account status, resource quotas, and usage limits. |
| `fastedge.kv_stores.create` | write | Create a new key-value storage store for edge applications. |
| `fastedge.kv_stores.delete` | destructive | Permanently delete an edge storage store and all its data. |
| `fastedge.kv_stores.get` | read | Retrieve complete configuration and metadata for a specific edge storage store. |
| `fastedge.kv_stores.list` | read | Retrieve key-value storage stores available to the authenticated client. |
| `fastedge.kv_stores.replace` | destructive | Modify edge store configuration including name, description, and application associations. |
| `fastedge.secrets.create` | write | Create a new encrypted secret for use in edge applications. |
| `fastedge.secrets.delete` | destructive | Permanently delete a secret and all its slot values. |
| `fastedge.secrets.get` | read | Retrieve complete metadata for a specific secret including all time-based slots. |
| `fastedge.secrets.list` | read | Retrieve encrypted secrets available to the authenticated client. |
| `fastedge.secrets.replace` | destructive | Updates secret metadata and/or adds new time-based slots with encrypted values |
| `fastedge.secrets.update` | write | Partially updates secret metadata and/or modifies specific slots |
| `fastedge.statistics.get_call_series` | read | Retrieve aggregated call statistics for applications within a specified time period. |
| `fastedge.statistics.get_duration_series` | read | Retrieve execution time statistics showing how long applications took to process requests. |
| `fastedge.templates.create` | write | Create a new application template from an existing binary and configuration. |
| `fastedge.templates.delete` | destructive | Remove a template from the platform. |
| `fastedge.templates.get` | read | Retrieve complete configuration and metadata for a specific template. |
| `fastedge.templates.list` | read | Retrieve available application templates including system templates and user-created templates. |
| `fastedge.templates.replace` | destructive | Modify an existing template's configuration. |

## iam (11)

| operation | access | summary |
|---|---|---|
| `iam.api_tokens.create` | write | Create an API token in the current account. |
| `iam.api_tokens.delete` | destructive | Delete API token from current account. |
| `iam.api_tokens.get` | read | Get information about a specific API token. |
| `iam.api_tokens.list` | read | Get information about your permanent API tokens in the account. |
| `iam.get_account_overview` | read | Get information about your profile, users and other account details. |
| `iam.users.delete` | destructive | Revokes user's access to the specified account. |
| `iam.users.get` | read | Get a single user of the caller's own client. |
| `iam.users.get_me` | read | The authenticated user's own profile, including the clients they belong to. |
| `iam.users.invite` | write | Invite a user to the account. |
| `iam.users.list` | read | List the users of the caller's own client. |
| `iam.users.update` | write | This method updates user's details. |

## security (11)

| operation | access | summary |
|---|---|---|
| `security.bgp_announces.list` | read | List BGP announces with optional filtering by site, origin, announcement status, and client. |
| `security.bgp_announces.toggle` | destructive | Enable or disable BGP announces for a client. |
| `security.events.get` | read | Event Log Detail View |
| `security.events.list` | read | Event Logs Clients View |
| `security.profile_templates.list` | read | Get list of profile templates. |
| `security.profiles.create` | write | Create protection profile. |
| `security.profiles.delete` | destructive | Delete protection profile. |
| `security.profiles.get` | read | Get profile by id |
| `security.profiles.list` | read | Get list of protection profiles. |
| `security.profiles.recreate` | destructive | Recreate profile with another profile template (for other cases use detail API) |
| `security.profiles.replace` | destructive | Update profile. |

## storage (26)

| operation | access | summary |
|---|---|---|
| `storage.locations.list` | read | Returns storage locations where you can create new storages. |
| `storage.object_storages.access_keys.create` | write | Creates a new access key for an S3-compatible storage. |
| `storage.object_storages.access_keys.delete` | destructive | Deletes an access key from an S3-compatible storage. |
| `storage.object_storages.access_keys.get` | read | Returns details of a specific access key for an S3-compatible storage. |
| `storage.object_storages.access_keys.list` | read | Returns a list of access keys for an S3-compatible storage. |
| `storage.object_storages.buckets.create` | write | Creates a new bucket within an S3-compatible storage. |
| `storage.object_storages.buckets.delete` | destructive | Removes a bucket from an S3-compatible storage. |
| `storage.object_storages.buckets.get` | read | Returns bucket configuration including CORS, Lifecycle, and Policy settings in a consolidated response. |
| `storage.object_storages.buckets.list` | read | Returns a paginated list of buckets for an S3-compatible storage, including each bucket's CORS, Lifecycle, and Policy configuration. |
| `storage.object_storages.buckets.update` | write | Updates bucket CORS, Lifecycle, and/or Policy settings. |
| `storage.object_storages.create` | write | Creates a new S3-compatible storage instance in the specified location and returns the storage details including credentials. |
| `storage.object_storages.delete` | destructive | Deletes an S3-compatible storage instance. |
| `storage.object_storages.get` | read | Returns details of a specific S3-compatible storage instance. |
| `storage.object_storages.list` | read | Returns a paginated list of S3-compatible storage instances for the authenticated client. |
| `storage.object_storages.restore` | write | Restores a previously deleted S3-compatible storage instance if it was deleted within the last 2 weeks. |
| `storage.sftp_storages.create` | write | Creates a new SFTP storage instance in the specified location and returns the storage details including credentials. |
| `storage.sftp_storages.delete` | destructive | Deletes an SFTP storage instance. |
| `storage.sftp_storages.get` | read | Returns details of a specific SFTP storage instance (without credentials). |
| `storage.sftp_storages.list` | read | Returns a paginated list of SFTP storage instances for the authenticated client. |
| `storage.sftp_storages.update` | write | Updates SFTP storage configuration and/or credentials including password and SSH key management. |
| `storage.ssh_keys.create` | write | Creates an SSH public key for SFTP storage access. |
| `storage.ssh_keys.delete` | destructive | Removes an SSH public key. |
| `storage.ssh_keys.get` | read | Retrieves a single SSH key by ID. |
| `storage.ssh_keys.list` | read | Returns a paginated list of all SSH public keys for SFTP storage access. |
| `storage.statistics.get_usage_aggregated` | read | Consumption statistics is updated in near real-time as a standard practice. |
| `storage.statistics.get_usage_series` | read | Consumption statistics is updated in near real-time as a standard practice. |

## streaming (87)

| operation | access | summary |
|---|---|---|
| `streaming.ai_tasks.cancel` | destructive | Stopping a previously launched AI-task without waiting for it to be fully completed. |
| `streaming.ai_tasks.create` | write | Creating an AI task. |
| `streaming.ai_tasks.get` | read | This is the single method to check the execution status of an AI task, and obtain the result of any type of AI task. |
| `streaming.ai_tasks.get_ai_settings` | read | The method for revealing basic information and advanced underlying settings that are used when performing AI-tasks. |
| `streaming.ai_tasks.list` | read | Returns a list of previously created and processed AI tasks. |
| `streaming.broadcasts.create` | write | Broadcast entity is for setting up HTML video player, which serves to combine: - many live streams, - advertising, - and design in one config. |
| `streaming.broadcasts.delete` | destructive | Delete broadcast |
| `streaming.broadcasts.get` | read | Returns broadcast details |
| `streaming.broadcasts.get_spectators_count` | read | Returns number of simultaneous broadcast viewers at the current moment |
| `streaming.broadcasts.list` | read | Note: Feature "Broadcast" is outdated, soon it will be replaced by "Multicamera". |
| `streaming.broadcasts.update` | write | Updates broadcast settings |
| `streaming.directories.create` | write | Use this method to create a new directory entity. |
| `streaming.directories.delete` | destructive | Delete a directory **and all entities inside**. |
| `streaming.directories.get` | read | Complete directory structure with contents. |
| `streaming.directories.get_tree` | read | Tree structure of directories. |
| `streaming.directories.update` | write | Change a directory name or move to another "parent_id". |
| `streaming.players.create` | write | Create player |
| `streaming.players.delete` | destructive | Delete player |
| `streaming.players.get` | read | Returns player settings |
| `streaming.players.list` | read | Returns a list of created players |
| `streaming.players.preview` | read | Returns player configuration in HTML |
| `streaming.players.update` | write | Updates player settings |
| `streaming.playlists.create` | write | Playlist is a curated collection of video content organized in a sequential manner. |
| `streaming.playlists.delete` | destructive | Delete playlist |
| `streaming.playlists.get` | read | Returns a playlist details |
| `streaming.playlists.list` | read | Returns a list of created playlists |
| `streaming.playlists.update` | write | Change playlist |
| `streaming.playlists.videos.list` | read | Shows ordered array of playlist videos |
| `streaming.quality_sets.list` | read | Method returns a list of all custom quality sets. |
| `streaming.quality_sets.set_default` | write | Method to set default quality set for VOD and Live transcoding. |
| `streaming.restreams.create` | write | Creates a new restream for a specified live stream. |
| `streaming.restreams.delete` | destructive | Deletes a restream and stops the broadcast to the target destination |
| `streaming.restreams.get` | read | Returns configuration and status details for a specific restream |
| `streaming.restreams.list` | read | Returns a list of all restreams created in your account |
| `streaming.restreams.update` | write | Updates restream settings, such as the target URI or active status |
| `streaming.statistics.get_ffprobes` | read | Aggregates data for the specified video stream in the specified time interval. |
| `streaming.statistics.get_live_unique_viewers` | read | Calculates time series of unique viewers of Live streams via CDN. |
| `streaming.statistics.get_live_watch_time_cdn` | read | Calculates a time series of live streams watching duration in minutes. |
| `streaming.statistics.get_live_watch_time_total_cdn` | read | Calculates the total duration of live streams watching in minutes. |
| `streaming.statistics.get_max_streams_series` | read | Calculates time series of the amount of simultaneous streams. |
| `streaming.statistics.get_popular_videos` | read | Aggregates the number of views for all client videos, grouping them by id and sort from most popular to less in the built-in player. |
| `streaming.statistics.get_storage_series` | read | Calculates time series of the size of disk space in bytes for all processed and undeleted client videos. |
| `streaming.statistics.get_stream_series` | read | Calculates time series of the transcoding minutes of all streams. |
| `streaming.statistics.get_unique_viewers` | read | Get the number of unique viewers in the built-in player. |
| `streaming.statistics.get_unique_viewers_cdn` | read | Counts the number of unique viewers of a video entity over CDN. |
| `streaming.statistics.get_views` | read | Get the number of views in the built-in player. |
| `streaming.statistics.get_views_by_browsers` | read | Aggregates the number of views for all client videos, grouping them by browsers in the built-in player. |
| `streaming.statistics.get_views_by_country` | read | Aggregates the number of views grouping them by country in the built-in player. |
| `streaming.statistics.get_views_by_hostname` | read | Aggregates the number of views, grouping them by "host" domain name the built-in player was embedded to. |
| `streaming.statistics.get_views_by_operating_system` | read | Aggregates the number of views for all client videos, grouping them by device OSs in the built-in player. |
| `streaming.statistics.get_views_by_referer` | read | Aggregates the number of views, grouping them by "referrer" URL of pages the built-in player was embedded to. |
| `streaming.statistics.get_views_by_region` | read | Aggregates the number of views grouping them by regions of countries in the built-in player. |
| `streaming.statistics.get_views_heatmap` | read | Shows information about what part of the video your viewers watched in the built-in player. |
| `streaming.statistics.get_vod_storage_volume` | read | Calculates time series of the duration in minutes for all processed and undeleted client videos. |
| `streaming.statistics.get_vod_transcoding_duration` | read | Calculates time series of the transcoding time in minutes for all processed client videos. |
| `streaming.statistics.get_vod_unique_viewers_cdn` | read | Calculates time series of unique viewers of VOD via CDN. |
| `streaming.statistics.get_vod_watch_time_cdn` | read | Calculates a time series of video watching duration in minutes. |
| `streaming.statistics.get_vod_watch_time_total_cdn` | read | Calculates the total duration of video watching in minutes. |
| `streaming.streams.clear_dvr` | destructive | Clear live stream DVR |
| `streaming.streams.clips.create` | write | Create an instant clip from on-going live stream. |
| `streaming.streams.clips.list` | read | Get list of non expired instant clips for a stream. |
| `streaming.streams.create` | write | Use this method to create a new live stream entity for broadcasting. |
| `streaming.streams.delete` | destructive | Delete a live stream. |
| `streaming.streams.get` | read | Returns the complete details of a specific live stream, including its current state, configuration, and URLs for ingestion and playback. |
| `streaming.streams.list` | read | Returns a list of streams |
| `streaming.streams.overlays.create` | write | "Overlay" is a live HTML widget, which rendered and inserted over the live stream. |
| `streaming.streams.overlays.delete` | destructive | Delete an overlay |
| `streaming.streams.overlays.get` | read | Get overlay details |
| `streaming.streams.overlays.list` | read | Returns a list of HTML overlay widgets which are attached to a stream |
| `streaming.streams.overlays.update` | write | Updates overlay settings |
| `streaming.streams.overlays.update_multiple` | write | Updates settings for set of overlays |
| `streaming.streams.start_recording` | write | Start recording a stream. |
| `streaming.streams.stop_recording` | destructive | Stop recording a stream. |
| `streaming.streams.update` | write | Updates stream settings |
| `streaming.videos.create` | write | Use this method to create a new video entity. |
| `streaming.videos.create_multiple` | write | Mass upload of your videos. |
| `streaming.videos.delete` | destructive | Operation to delete video entity. |
| `streaming.videos.get` | read | Information about a video entity. |
| `streaming.videos.get_parameters_for_direct_upload` | read | Use this method to get TUS' session parameters: hostname of the server to upload, secure token. |
| `streaming.videos.list` | read | Returns a set of videos by the given criteria. |
| `streaming.videos.list_names` | read | Returns names for specified video IDs |
| `streaming.videos.subtitles.create` | write | Add new subtitle/captions to a video entity. |
| `streaming.videos.subtitles.delete` | destructive | Delete specified video subtitle |
| `streaming.videos.subtitles.get` | read | Returns information about a specific subtitle for a video. |
| `streaming.videos.subtitles.list` | read | Method returns a list of all subtitles that are already attached to a video. |
| `streaming.videos.subtitles.update` | write | Method to update subtitle of a video. |
| `streaming.videos.update` | write | Changes parameters of the video to new values. |

## waap (104)

| operation | access | summary |
|---|---|---|
| `waap.advanced_rules.list` | read | Retrieve an advanced rules descriptor |
| `waap.analytics.get_detailed_events` | read | Retrieves security events with the same filters, ordering and cursor pagination as [Get security events (V2)](#operation/`get_events_v2_analytics_events_get`). |
| `waap.analytics.get_event_statistics` | read | Retrieves event statistics per given dimension of a request characteristics. |
| `waap.analytics.get_events` | read | Retrieve security events over account's domains. |
| `waap.analytics.get_filters` | read | Retrieves autocomplete suggestions for specified filter parameter values observed within the current client account during the requested time range. |
| `waap.analytics.get_requests` | read | Retrieve request log data over account's domains. |
| `waap.analytics.get_traffic` | read | Retrieves a comprehensive report on traffic statistics for a set of domains. |
| `waap.analytics.get_traffic_filtered` | read | Retrieves a traffic time series data over a set of domains. |
| `waap.custom_page_sets.create` | write | Create a custom page set based on the provided data. |
| `waap.custom_page_sets.delete` | destructive | Delete a custom page set |
| `waap.custom_page_sets.get` | read | Retrieve a custom page set based on the provided ID |
| `waap.custom_page_sets.list` | read | Retrieve a list of custom page sets available for use |
| `waap.custom_page_sets.preview` | read | Allows to preview a custom page without creating it based on the provided type and data |
| `waap.custom_page_sets.update` | write | Fields with a value are updated, fields set to null are removed, and fields omitted are left unchanged (`name` cannot be removed). |
| `waap.domains.advanced_rules.create` | write | Create advanced rule |
| `waap.domains.advanced_rules.delete` | destructive | Delete advanced rule |
| `waap.domains.advanced_rules.get` | read | Retrieve a specific advanced rule assigned to a domain |
| `waap.domains.advanced_rules.list` | read | Retrieve a list of advanced rules assigned to a domain, offering filter, ordering, and pagination capabilities |
| `waap.domains.advanced_rules.toggle` | destructive | Toggle advanced rule |
| `waap.domains.advanced_rules.update` | write | Only properties present in the request will be updated |
| `waap.domains.api_discovery.openapi.scan` | write | Scan an API description file hosted online. |
| `waap.domains.api_discovery.openapi.upload` | write | An API description file must adhere to the OpenAPI specification and be written in YAML or JSON format. |
| `waap.domains.api_discovery.scan_results.get` | read | Get Scan Result |
| `waap.domains.api_discovery.scan_results.list` | read | Get Scan Results |
| `waap.domains.api_discovery.settings.get` | read | Retrieve the API discovery settings for a domain |
| `waap.domains.api_discovery.settings.update` | write | Update the API discovery settings for a domain |
| `waap.domains.api_path_groups.list` | read | Retrieve a list of API path groups for a specific domain |
| `waap.domains.api_paths.create` | write | Create an API path for a domain |
| `waap.domains.api_paths.delete` | destructive | Delete a specific API path for a domain |
| `waap.domains.api_paths.get` | read | Retrieve a specific API path for a domain |
| `waap.domains.api_paths.list` | read | Retrieve a list of API paths for a specific domain |
| `waap.domains.api_paths.update` | write | Update a specific API path for a domain |
| `waap.domains.custom_rules.create` | write | Create custom rule |
| `waap.domains.custom_rules.delete` | destructive | Delete custom rule |
| `waap.domains.custom_rules.delete_multiple` | destructive | Delete multiple custom WAAP rules |
| `waap.domains.custom_rules.get` | read | Extracts a specific custom rule assigned to a domain |
| `waap.domains.custom_rules.list` | read | Extracts a list of custom rules assigned to a domain, offering filter, ordering, and pagination capabilities |
| `waap.domains.custom_rules.toggle` | destructive | Toggle custom rule |
| `waap.domains.custom_rules.update` | write | Only properties present in the request will be updated |
| `waap.domains.delete` | destructive | Delete an inactive domain by ID. |
| `waap.domains.firewall_rules.create` | write | Create firewall rule |
| `waap.domains.firewall_rules.delete` | destructive | Delete firewall rule |
| `waap.domains.firewall_rules.delete_multiple` | destructive | Delete multiple WAAP firewall rules |
| `waap.domains.firewall_rules.get` | read | Extracts a specific firewall rule assigned to a domain |
| `waap.domains.firewall_rules.list` | read | Extracts a list of firewall rules assigned to a domain, offering filter, ordering, and pagination capabilities |
| `waap.domains.firewall_rules.toggle` | destructive | Toggle firewall rule |
| `waap.domains.firewall_rules.update` | write | Only properties present in the request will be updated |
| `waap.domains.get` | read | Retrieve detailed information about a specific domain |
| `waap.domains.insight_silences.create` | write | Create a new insight silence for a specified domain. |
| `waap.domains.insight_silences.delete` | destructive | Delete an insight silence for a specific domain. |
| `waap.domains.insight_silences.get` | read | Retrieve a specific insight silence for a specific domain |
| `waap.domains.insight_silences.list` | read | Retrieve a list of insight silences for a specific domain |
| `waap.domains.insight_silences.update` | write | Update an insight silence for a specific domain. |
| `waap.domains.insights.get` | read | Retrieve a specific insight for a specific domain. |
| `waap.domains.insights.list` | read | Retrieve a list of insights for a specific domain. |
| `waap.domains.insights.replace` | destructive | Update the status of an insight for a specific domain. |
| `waap.domains.list` | read | Retrieve a list of domains associated with the client, including traffic statistics |
| `waap.domains.list_rule_sets` | read | Retrieve a paginated list of policy rule sets available for a particular domain. |
| `waap.domains.policies.get` | read | Retrieve the configuration of a security policy on a domain. |
| `waap.domains.policies.list` | read | Retrieve a paginated list of policies linked to a particular domain, optionally filtered by rule set |
| `waap.domains.policies.update` | write | Configure a security policy on a domain. |
| `waap.domains.policy_overrides.create` | write | Create a policy override |
| `waap.domains.policy_overrides.delete` | destructive | Delete a policy override |
| `waap.domains.policy_overrides.get` | read | Retrieve a policy override |
| `waap.domains.policy_overrides.list` | read | Retrieve policy overrides |
| `waap.domains.policy_overrides.list_owasp_top_threats_targets` | read | List OWASP Top Threats targets selectable as a policy override target |
| `waap.domains.policy_overrides.update` | write | Update a policy override |
| `waap.domains.settings.get` | read | Retrieve settings for a specific domain |
| `waap.domains.settings.update` | write | Set various settings for a specific domain. |
| `waap.domains.statistics.get_ddos_attacks` | read | Retrieve a domain's DDoS attacks |
| `waap.domains.statistics.get_ddos_info` | read | Returns the top DDoS counts grouped by URL, User-Agent, IP, COUNTRY or JA4. |
| `waap.domains.statistics.get_events_aggregated` | read | Retrieve an domain's event statistics |
| `waap.domains.statistics.get_request_details` | read | Retrieves all the available information for a request that matches a given request id |
| `waap.domains.update` | write | Update domain |
| `waap.filter_templates.create` | write | Create a filter template for the authenticated user. |
| `waap.filter_templates.delete` | destructive | Delete a filter template owned by the authenticated user. |
| `waap.filter_templates.get` | read | Retrieve a single filter template, scoped to the authenticated user. |
| `waap.filter_templates.list` | read | List filter templates owned by the authenticated user. |
| `waap.filter_templates.update` | write | Update or rename a filter template owned by the authenticated user. |
| `waap.firewall_rules.list` | read | Returns all firewall rules across all domains belonging to the authenticated account. |
| `waap.get_account_overview` | read | Get information about WAAP service for the client |
| `waap.insights.list_types` | read | Insight types are generalized categories that encompass various specific occurrences of the same kind. |
| `waap.ip_info.get_account_attack_time_series` | read | Retrieve a time-series of attacks originating from a specified IP address, scoped to the authenticated account's domains |
| `waap.ip_info.get_account_counts` | read | Retrieve comprehensive metrics for an IP address including distinct counts of attack types, domains, paths, and user agents across all account domains |
| `waap.ip_info.get_account_top_user_agents` | read | Retrieve up to 10 top user agents associated with an IP across all account domains. |
| `waap.ip_info.get_attack_time_series` | read | Retrieve a time-series of attacks originating from a specified IP address. |
| `waap.ip_info.get_blocked_requests` | read | Retrieve metrics, which enumerate blocked requests originating from a specific IP to a domain, grouped by rule name and taken action. |
| `waap.ip_info.get_ddos_attack_series` | read | Fetch and analyze DDoS (Distributed Denial of Service) attack metrics for a specified IP address. |
| `waap.ip_info.get_ip_info` | read | Fetch details about a particular IP address, including WHOIS data, risk score, and additional tags. |
| `waap.ip_info.get_top_attacks` | read | Returns top attack types with associated domains, paths, and counts across all account domains |
| `waap.ip_info.get_top_domains` | read | Retrieve top attacked domains for an IP address, scoped to the authenticated account's domains |
| `waap.ip_info.get_top_paths` | read | Retrieve top attacked paths for an IP address, scoped to the authenticated account's domains |
| `waap.ip_info.get_top_urls` | read | Returns a list of the top 10 URLs accessed by a specified IP address within a specific domain. |
| `waap.ip_info.get_top_user_agents` | read | Retrieve the top 10 user agents interacting with a specified domain, filtered by IP. |
| `waap.ip_info.get_top_user_sessions` | read | Obtain the top 10 user sessions interfacing with a particular domain, identified by IP. |
| `waap.ip_info.list_attacked_countries` | read | Retrieve a list of countries attacked by the specified IP address |
| `waap.ip_info.metrics.list` | read | Retrieve metrics encompassing the counts of total requests, blocked requests and unique sessions associated with a specified IP address. |
| `waap.ip_reputation.clear_local_tags` | destructive | Clear all tags associated between the provided IP addresses and domains. |
| `waap.ip_reputation.list` | read | Retrieve a list of tags associated with the IP address grouped by domains. |
| `waap.organizations.list` | read | This endpoint retrieves a list of network organizations that own IP ranges as identified by the Whois service.It supports pagination, filtering based on various parameters, and ordering of results. |
| `waap.prebilling.get_breakdown` | read | Retrieve a report on the calling client's own billable consumption by given metric with per-account breakdown. |
| `waap.prebilling.get_total` | read | Retrieve an aggregated report on the calling client's own billable consumption by given metric |
| `waap.statistics.get_usage_series` | read | Retrieve statistics data as a time series. |
| `waap.tags.list` | read | Tags are shortcuts for the rules used in WAAP policies for the creation of more complex WAAP rules |
