targetScope = 'resourceGroup'

@description('Azure region for the Foundry development resources.')
param location string = 'swedencentral'

@description('Short environment identifier applied to resource tags.')
param environmentName string

@description('Globally unique Microsoft Foundry account name.')
param foundryAccountName string

@description('Microsoft Foundry project name.')
param foundryProjectName string

@description('User-assigned identity attached to the Foundry account.')
param platformIdentityName string

@description('User-assigned identity used by the application to invoke the model.')
param applicationIdentityName string

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string

@description('Application Insights component name.')
param applicationInsightsName string

@description('Model deployment name used by application configuration.')
param modelDeploymentName string

@description('Exact model name confirmed in the target region catalog.')
param modelName string

@description('Exact model version confirmed in the target region catalog.')
param modelVersion string

@description('Deployment SKU confirmed for the selected model version.')
param modelSkuName string

@minValue(1)
@description('Deployment capacity. Revalidate quota and live capacity immediately before provisioning.')
param modelCapacity int = 1

var tags = {
  environment: environmentName
  workload: 'fantasy-cards'
  managedBy: 'azd-bicep'
}

module foundry 'foundry.bicep' = {
  params: {
    location: location
    tags: tags
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    platformIdentityName: platformIdentityName
    applicationIdentityName: applicationIdentityName
    logAnalyticsWorkspaceName: logAnalyticsWorkspaceName
    applicationInsightsName: applicationInsightsName
    modelDeploymentName: modelDeploymentName
    modelName: modelName
    modelVersion: modelVersion
    modelSkuName: modelSkuName
    modelCapacity: modelCapacity
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = resourceGroup().name
output AZURE_AI_ACCOUNT_NAME string = foundry.outputs.accountName
output AZURE_AI_PROJECT_NAME string = foundry.outputs.projectName
output AZURE_AI_PROJECT_ENDPOINT string = foundry.outputs.projectEndpoint
output AZURE_OPENAI_ENDPOINT string = foundry.outputs.openAiEndpoint
output AZURE_OPENAI_DEPLOYMENT_NAME string = modelDeploymentName
output AZURE_CLIENT_ID string = foundry.outputs.applicationIdentityClientId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = foundry.outputs.applicationInsightsConnectionString
