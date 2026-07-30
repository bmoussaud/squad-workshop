targetScope = 'resourceGroup'

param location string
param tags object
@description('Create a new Microsoft Foundry account/project/model deployment. Defaults to false; callers that provision Foundry must set this explicitly.')
param deployFoundry bool = false
param foundryAccountName string
param foundryProjectName string
@description('Existing shared Microsoft Foundry account name. Required when deployFoundry is false.')
param sharedFoundryAccountName string = ''
@description('Existing shared Microsoft Foundry project name. Required when deployFoundry is false.')
param sharedFoundryProjectName string = ''
@description('Resource group containing the shared Microsoft Foundry account when deployFoundry is false. Defaults to this deployment resource group.')
param sharedFoundryResourceGroupName string = ''
param platformIdentityName string
param applicationIdentityName string
param logAnalyticsWorkspaceName string
param applicationInsightsName string
param modelDeploymentName string
param modelName string
param modelVersion string
param modelSkuName string
param modelCapacity int
@description('Versioned custom RAI policy required for the production image deployment.')
param raiPolicyName string = 'fantasy-cards-content-policy-v1'
@description('Repository-managed version for the custom RAI policy configuration.')
param raiPolicyVersion string = '1'

var resolvedSharedFoundryResourceGroupName = empty(sharedFoundryResourceGroupName) ? resourceGroup().name : sharedFoundryResourceGroupName
// Built-in role definition ID for "Cognitive Services OpenAI User" (subscriptionResourceId is stable across regions/tenants).
var openAiUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')

module platformIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'platform-identity-${platformIdentityName}'
  params: {
    name: platformIdentityName
    location: location
    tags: tags
  }
}

module applicationIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'application-identity-${applicationIdentityName}'
  params: {
    name: applicationIdentityName
    location: location
    tags: tags
  }
}

module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.16.0' = {
  name: 'log-analytics-${logAnalyticsWorkspaceName}'
  params: {
    name: logAnalyticsWorkspaceName
    location: location
    tags: tags
    dataRetention: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    forceCmkForQuery: false
    skuName: 'PerGB2018'
  }
}

module applicationInsights 'br/public:avm/res/insights/component:0.8.0' = {
  name: 'application-insights-${applicationInsightsName}'
  params: {
    name: applicationInsightsName
    workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
    location: location
    tags: tags
    applicationType: 'web'
    disableIpMasking: false
    disableLocalAuth: true
    ingestionMode: 'LogAnalytics'
    kind: 'web'
    retentionInDays: 30
  }
}

module foundryAccount 'br/public:avm/res/cognitive-services/account:0.15.1' = if (deployFoundry) {
  name: 'foundry-account-${foundryAccountName}'
  params: {
    name: foundryAccountName
    kind: 'AIServices'
    location: location
    tags: tags
    allowProjectManagement: true
    customSubDomainName: foundryAccountName
    disableLocalAuth: true
    managedIdentities: {
      userAssignedResourceIds: [
        platformIdentity.outputs.resourceId
      ]
    }
    publicNetworkAccess: 'Enabled'
    restrictOutboundNetworkAccess: false
    sku: 'S0'
    diagnosticSettings: [
      {
        name: 'send-to-${logAnalyticsWorkspaceName}'
        workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
        logCategoriesAndGroups: [
          {
            categoryGroup: 'allLogs'
          }
        ]
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
      }
    ]
    roleAssignments: [
      {
        principalId: applicationIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
      }
    ]
  }
}

resource foundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = if (deployFoundry) {
  name: foundryAccountName
}

// native-bicep-fallback: The selected Cognitive Services account AVM does not expose custom RAI policy creation or deployment policy binding.
resource contentPolicy 'Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01-preview' = if (deployFoundry) {
  parent: foundryAccountResource
  name: raiPolicyName
  properties: {
    basePolicyName: 'Microsoft.DefaultV2'
    mode: 'Default'
    contentFilters: [
      {
        name: 'Hate'
        source: 'Prompt'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'Sexual'
        source: 'Prompt'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'Violence'
        source: 'Prompt'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'SelfHarm'
        source: 'Prompt'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'Hate'
        source: 'Completion'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'Sexual'
        source: 'Completion'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'Violence'
        source: 'Completion'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
      {
        name: 'SelfHarm'
        source: 'Completion'
        enabled: true
        blocking: true
        severityThreshold: 'Medium'
      }
    ]
  }
  dependsOn: [
    foundryAccount
  ]
}

// native-bicep-fallback: The selected Cognitive Services account AVM does not expose custom RAI policy creation or deployment policy binding.
resource foundryModelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01-preview' = if (deployFoundry) {
  parent: foundryAccountResource
  name: modelDeploymentName
  sku: {
    name: modelSkuName
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    raiPolicyName: raiPolicyName
    versionUpgradeOption: 'NoAutoUpgrade'
  }
  dependsOn: [
    contentPolicy
  ]
}

// native-bicep-fallback: The Cognitive Services account AVM does not create Foundry project child resources; the available Foundry pattern module replaces the approved user-assigned identity design with system-assigned identities.
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = if (deployFoundry) {
  parent: foundryAccountResource
  name: foundryProjectName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', platformIdentityName)}': {}
    }
  }
  properties: {
    description: 'Development project for fantasy card generation.'
    displayName: 'Fantasy Cards Development'
  }
  dependsOn: [
    foundryAccount
    platformIdentity
  ]
}

// Shared Foundry reference path (deployFoundry = false, e.g. PR environments). No new Foundry account/project is
// created; the PR application identity is granted "Cognitive Services OpenAI User" on the existing shared account.
// A nested module is required because the shared account may live in a different resource group than this
// deployment's target scope, and a resource's `scope` must match its own file's target scope.
module sharedFoundryRbac 'modules/shared-foundry-rbac.bicep' = if (!deployFoundry) {
  name: 'shared-foundry-rbac-${applicationIdentityName}'
  scope: resourceGroup(resolvedSharedFoundryResourceGroupName)
  params: {
    foundryAccountName: sharedFoundryAccountName
    principalId: applicationIdentity.outputs.principalId
    roleDefinitionId: openAiUserRoleDefinitionId
    roleDescription: 'Allow this PR application identity to invoke the shared Microsoft Foundry OpenAI deployment.'
  }
}

output accountName string = deployFoundry ? foundryAccount.outputs.name : sharedFoundryAccountName
output projectName string = deployFoundry ? foundryProject.name : sharedFoundryProjectName
output projectEndpoint string = 'https://${deployFoundry ? foundryAccount.outputs.name : sharedFoundryAccountName}.services.ai.azure.com/api/projects/${deployFoundry ? foundryProject.name : sharedFoundryProjectName}'
output openAiEndpoint string = 'https://${deployFoundry ? foundryAccount.outputs.name : sharedFoundryAccountName}.services.ai.azure.com/openai/v1'
output applicationIdentityClientId string = applicationIdentity.outputs.clientId
output applicationIdentityPrincipalId string = applicationIdentity.outputs.principalId
output applicationIdentityResourceId string = applicationIdentity.outputs.resourceId
output raiPolicyName string = raiPolicyName
output raiPolicyVersion string = raiPolicyVersion
@secure()
output applicationInsightsConnectionString string = applicationInsights.outputs.connectionString
output applicationInsightsResourceId string = applicationInsights.outputs.resourceId
output logAnalyticsWorkspaceResourceId string = logAnalyticsWorkspace.outputs.resourceId
