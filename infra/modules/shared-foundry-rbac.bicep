targetScope = 'resourceGroup'

@description('Existing shared Microsoft Foundry account name. The account lives in the resource group targeted by the parent module scope call.')
param foundryAccountName string

@description('Principal ID of the PR application managed identity that needs access to the shared Foundry account.')
param principalId string

@description('Role definition resource ID to assign (e.g. Cognitive Services OpenAI User).')
param roleDefinitionId string

@description('Human-readable description recorded on the role assignment.')
param roleDescription string

// native-bicep-fallback: A role assignment scoped to a resource in a different resource group than the calling
// Bicep file's target scope must be deployed through a module whose own `scope` targets that resource group;
// no maintained AVM module exposes this specific cross-resource-group RBAC-only contract.
resource sharedFoundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource sharedFoundryRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: sharedFoundryAccountResource
  name: guid(sharedFoundryAccountResource.id, principalId, roleDefinitionId)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionId
    description: roleDescription
  }
}
