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

var resolvedSharedFoundryResourceGroupName = empty(sharedFoundryResourceGroupName) ? resourceGroup().name : sharedFoundryResourceGroupName
// Built-in role definition ID for "Cognitive Services OpenAI User" (subscriptionResourceId is stable across regions/tenants).
var openAiUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var moduleDeploymentNameToken = toLower(uniqueString(resourceGroup().id, applicationIdentityName, logAnalyticsWorkspaceName))

module platformIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'platform-identity-${moduleDeploymentNameToken}'
  params: {
    name: platformIdentityName
    location: location
    tags: tags
  }
}

module applicationIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.6.0' = {
  name: 'application-identity-${moduleDeploymentNameToken}'
  params: {
    name: applicationIdentityName
    location: location
    tags: tags
  }
}

module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.16.0' = {
  name: 'log-analytics-${moduleDeploymentNameToken}'
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
  name: 'application-insights-${moduleDeploymentNameToken}'
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
  name: 'foundry-account-${moduleDeploymentNameToken}'
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
    deployments: [
      {
        name: modelDeploymentName
        model: {
          format: 'OpenAI'
          name: modelName
          version: modelVersion
        }
        sku: {
          name: modelSkuName
          capacity: modelCapacity
        }
        versionUpgradeOption: 'NoAutoUpgrade'
      }
    ]
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
  name: 'shared-foundry-rbac-${moduleDeploymentNameToken}'
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
output applicationInsightsConnectionString string = applicationInsights.outputs.connectionString
output applicationInsightsResourceId string = applicationInsights.outputs.resourceId
output logAnalyticsWorkspaceResourceId string = logAnalyticsWorkspace.outputs.resourceId
