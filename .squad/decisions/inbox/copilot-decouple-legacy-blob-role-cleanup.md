# Decouple legacy Blob role cleanup from azd deployment

The account-scoped legacy `Storage Blob Data Contributor` assignment is retired only by
the explicit `infra/scripts/retire_legacy_storage_blob_role.py` maintenance action after
deployment. It is no longer an `azure.yaml` postprovision hook.

The container-scoped assignment is the required private Blob route and is created by
Bicep. RBAC enumeration and deletion require separate operator permissions, so coupling
that cleanup to `azd up` made otherwise successful application deployments fail. The
maintenance script remains fail-closed: it deletes only one verified direct legacy
assignment after verifying exactly one direct container assignment.
