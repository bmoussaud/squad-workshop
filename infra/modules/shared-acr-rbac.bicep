targetScope = 'resourceGroup'

@description('Existing shared Azure Container Registry name. The registry lives in the resource group targeted by the parent module scope call.')
param containerRegistryName string

@description('Principal ID of the PR application managed identity that needs to pull images from the shared registry.')
param principalId string

@description('Role definition resource ID to assign (AcrPull).')
param roleDefinitionId string

@description('Human-readable description recorded on the role assignment.')
param roleDescription string

// native-bicep-fallback: A role assignment scoped to a resource in a different resource group than the calling
// Bicep file's target scope must be deployed through a module whose own `scope` targets that resource group;
// no maintained AVM module exposes this specific cross-resource-group RBAC-only contract.
resource sharedContainerRegistryResource 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: containerRegistryName
}

resource sharedAcrRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sharedContainerRegistryResource
  name: guid(sharedContainerRegistryResource.id, principalId, roleDefinitionId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionId
    description: roleDescription
  }
}

output loginServer string = sharedContainerRegistryResource.properties.loginServer
