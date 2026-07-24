targetScope = 'resourceGroup'

param location string
param tags object
param foundryAccountName string
param foundryProjectName string
param platformIdentityName string
param applicationIdentityName string
param logAnalyticsWorkspaceName string
param applicationInsightsName string
param modelDeploymentName string
param modelName string
param modelVersion string
param modelSkuName string
param modelCapacity int

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

module foundryAccount 'br/public:avm/res/cognitive-services/account:0.15.1' = {
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

resource foundryAccountResource 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

// native-bicep-fallback: The Cognitive Services account AVM does not create Foundry project child resources; the available Foundry pattern module replaces the approved user-assigned identity design with system-assigned identities.
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
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

output accountName string = foundryAccount.outputs.name
output projectName string = foundryProject.name
output projectEndpoint string = 'https://${foundryAccount.outputs.name}.services.ai.azure.com/api/projects/${foundryProject.name}'
output openAiEndpoint string = 'https://${foundryAccount.outputs.name}.services.ai.azure.com/openai/v1'
output applicationIdentityClientId string = applicationIdentity.outputs.clientId
output applicationIdentityPrincipalId string = applicationIdentity.outputs.principalId
output applicationIdentityResourceId string = applicationIdentity.outputs.resourceId
output applicationInsightsConnectionString string = applicationInsights.outputs.connectionString
output applicationInsightsResourceId string = applicationInsights.outputs.resourceId
output logAnalyticsWorkspaceResourceId string = logAnalyticsWorkspace.outputs.resourceId
