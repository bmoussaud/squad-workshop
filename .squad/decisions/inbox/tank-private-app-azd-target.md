# Private app azd deployment target

- **Decision:** Tag only `ca-fc-${resourceToken}-pvt` with `azd-service-name: web`; leave the original Container App fully provisioned without that tag as the manual rollback target.
- **Reason:** `azd` discovers Container Apps by the service tag. Two tagged apps make publish-web ambiguous, while the VNet-integrated private app is the one with private Blob reachability.
- **Traffic:** The private environment is external and its app has external ingress. This change moves only the `azd` image-deployment target; it creates no Front Door, custom-domain, or DNS cutover. Product Owner approval is required for any external traffic/domain change.
