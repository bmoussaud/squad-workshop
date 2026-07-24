targetScope = 'resourceGroup'

@description('Azure region for the Foundry development resources.')
param location string = 'swedencentral'

@description('Azure region for application hosting resources.')
param applicationLocation string = 'francecentral'

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

@description('Azure Container Apps dedicated workload profile type validated for the target region and subscription.')
param workloadProfileType string

@minValue(1)
@description('Minimum dedicated workload profile instance count validated against availability and cost.')
param workloadProfileMinimumCount int

@minValue(1)
@description('Maximum dedicated workload profile instance count validated against availability and cost.')
param workloadProfileMaximumCount int

@description('Container App CPU allocation, validated for the selected workload profile.')
param containerCpu string

@description('Container App memory allocation, validated for the selected workload profile, such as 2Gi.')
param containerMemory string

@minValue(1)
@description('Approved monthly resource-group budget amount in the billing currency.')
param monthlyBudgetAmount int

@description('Deterministic budget period start date in ISO 8601 format, aligned to the first day of a month.')
param budgetStartDate string

@minLength(1)
@description('Email recipients for budget and operational alerts.')
param alertContactEmails array

@description('Enable application-signal log alerts only after Azure Validate confirms telemetry tables and queries.')
param enableApplicationSignalAlerts bool = false

var tags = {
  environment: environmentName
  workload: 'fantasy-cards'
  managedBy: 'azd-bicep'
}

module foundry 'foundry.bicep' = {
  name: 'foundry-${environmentName}'
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

module web 'web.bicep' = {
  name: 'web-${environmentName}'
  params: {
    location: applicationLocation
    tags: tags
    environmentName: environmentName
    applicationIdentityClientId: foundry.outputs.applicationIdentityClientId
    applicationIdentityPrincipalId: foundry.outputs.applicationIdentityPrincipalId
    applicationIdentityResourceId: foundry.outputs.applicationIdentityResourceId
    applicationInsightsConnectionString: foundry.outputs.applicationInsightsConnectionString
    applicationInsightsResourceId: foundry.outputs.applicationInsightsResourceId
    logAnalyticsWorkspaceResourceId: foundry.outputs.logAnalyticsWorkspaceResourceId
    openAiEndpoint: foundry.outputs.openAiEndpoint
    modelDeploymentName: modelDeploymentName
    workloadProfileType: workloadProfileType
    workloadProfileMinimumCount: workloadProfileMinimumCount
    workloadProfileMaximumCount: workloadProfileMaximumCount
    containerCpu: containerCpu
    containerMemory: containerMemory
    monthlyBudgetAmount: monthlyBudgetAmount
    budgetStartDate: budgetStartDate
    alertContactEmails: alertContactEmails
    enableApplicationSignalAlerts: enableApplicationSignalAlerts
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
output SERVICE_WEB_URI string = web.outputs.serviceUri
output AZURE_CONTAINER_APP_NAME string = web.outputs.containerAppName
output AZURE_CONTAINER_APPS_ENVIRONMENT_NAME string = web.outputs.containerAppsEnvironmentName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = web.outputs.containerRegistryEndpoint
output AZURE_STORAGE_ACCOUNT_URL string = web.outputs.storageAccountUrl
output FANTASY_CARD_BLOB_CONTAINER string = web.outputs.blobContainerName
output APPLICATION_IDENTITY_PRINCIPAL_ID string = foundry.outputs.applicationIdentityPrincipalId
