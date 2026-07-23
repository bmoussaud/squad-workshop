using './main.bicep'

param location = 'swedencentral'
param applicationLocation = 'francecentral'
param environmentName = 'dev-8f327f8c'
param foundryAccountName = 'fnd-fantasy-cards-dev-8f327f8c'
param foundryProjectName = 'prj-fantasy-cards-dev-8f327f8c'
param platformIdentityName = 'id-fantasy-cards-platform-dev-8f327f8c'
param applicationIdentityName = 'id-fantasy-cards-app-dev-8f327f8c'
param logAnalyticsWorkspaceName = 'log-fantasy-cards-dev-8f327f8c'
param applicationInsightsName = 'appi-fantasy-cards-dev-8f327f8c'
param modelDeploymentName = 'gpt-image-2-dev'
param modelName = 'gpt-image-2'
param modelVersion = '2026-04-21'
param modelSkuName = 'GlobalStandard'
param modelCapacity = 1
param workloadProfileType = readEnvironmentVariable('AZURE_CONTAINER_APPS_WORKLOAD_PROFILE_TYPE')
param workloadProfileMinimumCount = int(readEnvironmentVariable('AZURE_CONTAINER_APPS_WORKLOAD_PROFILE_MIN_COUNT'))
param workloadProfileMaximumCount = int(readEnvironmentVariable('AZURE_CONTAINER_APPS_WORKLOAD_PROFILE_MAX_COUNT'))
param containerCpu = readEnvironmentVariable('AZURE_CONTAINER_APP_CPU')
param containerMemory = readEnvironmentVariable('AZURE_CONTAINER_APP_MEMORY')
param monthlyBudgetAmount = int(readEnvironmentVariable('AZURE_MONTHLY_BUDGET_AMOUNT'))
param budgetStartDate = readEnvironmentVariable('AZURE_BUDGET_START_DATE')
param alertContactEmails = split(readEnvironmentVariable('AZURE_ALERT_CONTACT_EMAILS'), ';')
param enableApplicationSignalAlerts = bool(readEnvironmentVariable('AZURE_ENABLE_APPLICATION_SIGNAL_ALERTS'))