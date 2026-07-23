targetScope = 'resourceGroup'

param location string
param tags object
param environmentName string
param applicationIdentityClientId string
param applicationIdentityPrincipalId string
param applicationIdentityResourceId string
@secure()
param applicationInsightsConnectionString string
param applicationInsightsResourceId string
param logAnalyticsWorkspaceResourceId string
param openAiEndpoint string
param modelDeploymentName string
param workloadProfileType string
param workloadProfileMinimumCount int
param workloadProfileMaximumCount int
param containerCpu string
param containerMemory string
param monthlyBudgetAmount int
param budgetStartDate string
param alertContactEmails array
param enableApplicationSignalAlerts bool

var resourceToken = toLower(uniqueString(subscription().subscriptionId, resourceGroup().id, environmentName))
var containerAppName = 'ca-fantasy-cards-${environmentName}'
var containerAppsEnvironmentName = 'cae-fantasy-cards-${environmentName}'
var containerRegistryName = 'acrfantasycards${resourceToken}'
var storageAccountName = 'stfc${resourceToken}'
var blobContainerName = 'artifacts'
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var blobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var monitoringMetricsPublisherRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
	name: last(split(applicationInsightsResourceId, '/'))
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
	name: containerRegistryName
	location: location
	tags: tags
	sku: {
		name: 'Basic'
	}
	properties: {
		adminUserEnabled: false
		anonymousPullEnabled: false
		dataEndpointEnabled: false
		publicNetworkAccess: 'Enabled'
		policies: {
			azureADAuthenticationAsArmPolicy: {
				status: 'enabled'
			}
			quarantinePolicy: {
				status: 'disabled'
			}
			retentionPolicy: {
				days: 7
				status: 'disabled'
			}
			trustPolicy: {
				status: 'disabled'
				type: 'Notary'
			}
		}
	}
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2025-01-01' = {
	name: storageAccountName
	location: location
	tags: tags
	kind: 'StorageV2'
	sku: {
		name: 'Standard_LRS'
	}
	properties: {
		accessTier: 'Hot'
		allowBlobPublicAccess: false
		allowCrossTenantReplication: false
		allowSharedKeyAccess: false
		defaultToOAuthAuthentication: true
		dnsEndpointType: 'Standard'
		minimumTlsVersion: 'TLS1_2'
		publicNetworkAccess: 'Enabled'
		supportsHttpsTrafficOnly: true
	}
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
	parent: storageAccount
	name: 'default'
	properties: {
		containerDeleteRetentionPolicy: {
			days: 7
			enabled: true
		}
		deleteRetentionPolicy: {
			allowPermanentDelete: false
			days: 7
			enabled: true
		}
	}
}

resource artifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = {
	parent: blobService
	name: blobContainerName
	properties: {
		publicAccess: 'None'
	}
}

resource storageLifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2025-01-01' = {
	parent: storageAccount
	name: 'default'
	properties: {
		policy: {
			rules: [
				{
					name: 'delete-artifacts-after-30-days'
					type: 'Lifecycle'
					enabled: true
					definition: {
						actions: {
							baseBlob: {
								delete: {
									daysAfterCreationGreaterThan: 30
								}
							}
						}
						filters: {
							blobTypes: [
								'blockBlob'
							]
							prefixMatch: [
								'${blobContainerName}/'
							]
						}
					}
				}
			]
		}
	}
}

resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
	name: containerAppsEnvironmentName
	location: location
	tags: tags
	properties: {
		appLogsConfiguration: {
			destination: 'azure-monitor'
		}
		publicNetworkAccess: 'Enabled'
		workloadProfiles: [
			{
				name: 'dedicated'
				workloadProfileType: workloadProfileType
				minimumCount: workloadProfileMinimumCount
				maximumCount: workloadProfileMaximumCount
			}
		]
		zoneRedundant: false
	}
}

resource containerApp 'Microsoft.App/containerApps@2024-10-02-preview' = {
	name: containerAppName
	location: location
	tags: union(tags, {
		'azd-service-name': 'web'
	})
	identity: {
		type: 'UserAssigned'
		userAssignedIdentities: {
			'${applicationIdentityResourceId}': {}
		}
	}
	properties: {
		environmentId: containerAppsEnvironment.id
		workloadProfileName: 'dedicated'
		configuration: {
			activeRevisionsMode: 'Single'
			ingress: {
				allowInsecure: false
				external: true
				targetPort: 8000
				transport: 'auto'
			}
			registries: [
				{
					identity: applicationIdentityResourceId
					server: containerRegistry.properties.loginServer
				}
			]
		}
		template: {
			containers: [
				{
					name: 'web'
					image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
					env: [
						{
							name: 'FANTASY_CARD_IMAGE_GENERATOR'
							value: 'foundry'
						}
						{
							name: 'AZURE_OPENAI_ENDPOINT'
							value: openAiEndpoint
						}
						{
							name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
							value: modelDeploymentName
						}
						{
							name: 'AZURE_CLIENT_ID'
							value: applicationIdentityClientId
						}
						{
							name: 'FANTASY_CARD_IMAGE_TIMEOUT_SECONDS'
							value: '120'
						}
						{
							name: 'FANTASY_CARD_ARTIFACT_STORE'
							value: 'blob'
						}
						{
							name: 'AZURE_STORAGE_ACCOUNT_URL'
							value: storageAccount.properties.primaryEndpoints.blob
						}
						{
							name: 'FANTASY_CARD_BLOB_CONTAINER'
							value: blobContainerName
						}
						{
							name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
							value: applicationInsightsConnectionString
						}
						{
							name: 'PORT'
							value: '8000'
						}
						{
							name: 'FANTASY_CARD_MAX_GENERATION_CONCURRENCY'
							value: '1'
						}
						{
							name: 'FANTASY_CARD_RATE_LIMIT_ATTEMPTS'
							value: '10'
						}
						{
							name: 'FANTASY_CARD_RATE_LIMIT_WINDOW_SECONDS'
							value: '600'
						}
					]
					resources: {
						cpu: json(containerCpu)
						memory: containerMemory
					}
					probes: [
						{
							type: 'Liveness'
							httpGet: {
								path: '/health/live'
								port: 8000
								scheme: 'HTTP'
							}
							initialDelaySeconds: 10
							periodSeconds: 30
							timeoutSeconds: 5
							failureThreshold: 3
						}
						{
							type: 'Readiness'
							httpGet: {
								path: '/health/ready'
								port: 8000
								scheme: 'HTTP'
							}
							initialDelaySeconds: 5
							periodSeconds: 10
							timeoutSeconds: 5
							failureThreshold: 3
						}
					]
				}
			]
			scale: {
				minReplicas: 1
				maxReplicas: 2
				rules: [
					{
						name: 'http-concurrency'
						http: {
							metadata: {
								concurrentRequests: '1'
							}
						}
					}
				]
			}
		}
	}
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
	scope: containerRegistry
	name: guid(containerRegistry.id, applicationIdentityPrincipalId, acrPullRoleDefinitionId)
	properties: {
		principalId: applicationIdentityPrincipalId
		principalType: 'ServicePrincipal'
		roleDefinitionId: acrPullRoleDefinitionId
		description: 'Allow the fantasy cards application identity to pull runtime images.'
	}
}

resource blobDataAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
	scope: artifactContainer
	name: guid(artifactContainer.id, applicationIdentityPrincipalId, blobDataContributorRoleDefinitionId)
	properties: {
		principalId: applicationIdentityPrincipalId
		principalType: 'ServicePrincipal'
		roleDefinitionId: blobDataContributorRoleDefinitionId
		description: 'Allow the fantasy cards application identity to read and write generated artifacts.'
	}
}

resource monitoringMetricsPublisherAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
	scope: applicationInsights
	name: guid(applicationInsights.id, applicationIdentityPrincipalId, monitoringMetricsPublisherRoleDefinitionId)
	properties: {
		principalId: applicationIdentityPrincipalId
		principalType: 'ServicePrincipal'
		roleDefinitionId: monitoringMetricsPublisherRoleDefinitionId
		description: 'Allow the fantasy cards application identity to publish authenticated telemetry.'
	}
}

resource environmentDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: containerAppsEnvironment
	name: 'send-to-log-analytics'
	properties: {
		workspaceId: logAnalyticsWorkspaceResourceId
		logAnalyticsDestinationType: 'Dedicated'
		logs: [
			{
				categoryGroup: 'allLogs'
				enabled: true
			}
		]
		metrics: [
			{
				category: 'AllMetrics'
				enabled: true
			}
		]
	}
}

resource appDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: containerApp
	name: 'send-to-log-analytics'
	properties: {
		workspaceId: logAnalyticsWorkspaceResourceId
		logAnalyticsDestinationType: 'Dedicated'
		metrics: [
			{
				category: 'AllMetrics'
				enabled: true
			}
		]
	}
}

resource registryDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: containerRegistry
	name: 'send-to-log-analytics'
	properties: {
		workspaceId: logAnalyticsWorkspaceResourceId
		logAnalyticsDestinationType: 'Dedicated'
		logs: [
			{
				categoryGroup: 'allLogs'
				enabled: true
			}
		]
		metrics: [
			{
				category: 'AllMetrics'
				enabled: true
			}
		]
	}
}

resource storageDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: blobService
	name: 'send-to-log-analytics'
	properties: {
		workspaceId: logAnalyticsWorkspaceResourceId
		logAnalyticsDestinationType: 'Dedicated'
		logs: [
			{
				categoryGroup: 'allLogs'
				enabled: true
			}
		]
		metrics: [
			{
				category: 'Transaction'
				enabled: true
			}
		]
	}
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
	name: 'ag-fantasy-cards-${environmentName}'
	location: 'global'
	tags: tags
	properties: {
		enabled: true
		groupShortName: 'fantasycard'
		emailReceivers: [for (email, index) in alertContactEmails: {
			name: 'email-${index + 1}'
			emailAddress: email
			useCommonAlertSchema: true
		}]
	}
}

resource resourceGroupBudget 'Microsoft.Consumption/budgets@2024-08-01' = {
	name: 'budget-fantasy-cards-${environmentName}'
	properties: {
		amount: monthlyBudgetAmount
		category: 'Cost'
		timeGrain: 'Monthly'
		timePeriod: {
			startDate: budgetStartDate
		}
		filter: {
			dimensions: {
				name: 'ResourceGroupName'
				operator: 'In'
				values: [
					resourceGroup().name
				]
			}
		}
		notifications: {
			Actual50: {
				enabled: true
				operator: 'GreaterThanOrEqualTo'
				threshold: 50
				thresholdType: 'Actual'
				contactEmails: alertContactEmails
				contactGroups: [
					actionGroup.id
				]
			}
			Actual80: {
				enabled: true
				operator: 'GreaterThanOrEqualTo'
				threshold: 80
				thresholdType: 'Actual'
				contactEmails: alertContactEmails
				contactGroups: [
					actionGroup.id
				]
			}
			Actual100: {
				enabled: true
				operator: 'GreaterThanOrEqualTo'
				threshold: 100
				thresholdType: 'Actual'
				contactEmails: alertContactEmails
				contactGroups: [
					actionGroup.id
				]
			}
		}
	}
}

resource http5xxAlert 'Microsoft.Insights/scheduledQueryRules@2025-01-01-preview' = if (enableApplicationSignalAlerts) {
	name: 'alert-fantasy-cards-http-5xx-${environmentName}'
	location: location
	tags: tags
	kind: 'LogAlert'
	properties: {
		displayName: 'Fantasy Cards HTTP 5xx responses'
		description: 'At least five server responses were recorded in five minutes.'
		enabled: enableApplicationSignalAlerts
		evaluationFrequency: 'PT5M'
		windowSize: 'PT5M'
		severity: 2
		scopes: [
			applicationInsightsResourceId
		]
		skipQueryValidation: true
		autoMitigate: true
		criteria: {
			allOf: [
				{
					query: 'AppRequests | where ResultCode startswith "5"'
					timeAggregation: 'Count'
					operator: 'GreaterThanOrEqual'
					threshold: 5
					failingPeriods: {
						minFailingPeriodsToAlert: 1
						numberOfEvaluationPeriods: 1
					}
				}
			]
		}
		actions: {
			actionGroups: [
				actionGroup.id
			]
		}
	}
}

resource readinessAlert 'Microsoft.Insights/scheduledQueryRules@2025-01-01-preview' = if (enableApplicationSignalAlerts) {
	name: 'alert-fantasy-cards-readiness-${environmentName}'
	location: location
	tags: tags
	kind: 'LogAlert'
	properties: {
		displayName: 'Fantasy Cards readiness failures'
		description: 'At least three readiness requests failed in five minutes.'
		enabled: enableApplicationSignalAlerts
		evaluationFrequency: 'PT5M'
		windowSize: 'PT5M'
		severity: 1
		scopes: [
			applicationInsightsResourceId
		]
		skipQueryValidation: true
		autoMitigate: true
		criteria: {
			allOf: [
				{
					query: 'AppRequests | where Url endswith "/health/ready" and Success == false'
					timeAggregation: 'Count'
					operator: 'GreaterThanOrEqual'
					threshold: 3
					failingPeriods: {
						minFailingPeriodsToAlert: 1
						numberOfEvaluationPeriods: 1
					}
				}
			]
		}
		actions: {
			actionGroups: [
				actionGroup.id
			]
		}
	}
}

resource providerAlert 'Microsoft.Insights/scheduledQueryRules@2025-01-01-preview' = if (enableApplicationSignalAlerts) {
	name: 'alert-fantasy-cards-provider-${environmentName}'
	location: location
	tags: tags
	kind: 'LogAlert'
	properties: {
		displayName: 'Fantasy Cards provider failures'
		description: 'At least three provider throttles or timeouts occurred in fifteen minutes.'
		enabled: enableApplicationSignalAlerts
		evaluationFrequency: 'PT5M'
		windowSize: 'PT15M'
		severity: 1
		scopes: [
			applicationInsightsResourceId
		]
		skipQueryValidation: true
		autoMitigate: true
		criteria: {
			allOf: [
				{
					query: 'AppTraces | where (Properties["dependency"] == "provider" and Properties["error_code"] in ("authentication_failed", "provider_timeout", "provider_unavailable", "throttled")) or Properties["error_code"] == "rate_limited"'
					timeAggregation: 'Count'
					operator: 'GreaterThanOrEqual'
					threshold: 3
					failingPeriods: {
						minFailingPeriodsToAlert: 1
						numberOfEvaluationPeriods: 1
					}
				}
			]
		}
		actions: {
			actionGroups: [
				actionGroup.id
			]
		}
	}
}

resource blobFailureAlert 'Microsoft.Insights/scheduledQueryRules@2025-01-01-preview' = if (enableApplicationSignalAlerts) {
	name: 'alert-fantasy-cards-blob-${environmentName}'
	location: location
	tags: tags
	kind: 'LogAlert'
	properties: {
		displayName: 'Fantasy Cards Blob failures'
		description: 'At least three Blob read or write failures occurred in fifteen minutes.'
		enabled: enableApplicationSignalAlerts
		evaluationFrequency: 'PT5M'
		windowSize: 'PT15M'
		severity: 1
		scopes: [
			applicationInsightsResourceId
		]
		skipQueryValidation: true
		autoMitigate: true
		criteria: {
			allOf: [
				{
					query: 'AppTraces | where Properties["dependency"] == "blob" and Properties["success"] == "false"'
					timeAggregation: 'Count'
					operator: 'GreaterThanOrEqual'
					threshold: 3
					failingPeriods: {
						minFailingPeriodsToAlert: 1
						numberOfEvaluationPeriods: 1
					}
				}
			]
		}
		actions: {
			actionGroups: [
				actionGroup.id
			]
		}
	}
}

resource replicaCeilingAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
	name: 'alert-fantasy-cards-replicas-${environmentName}'
	location: 'global'
	tags: tags
	properties: {
		description: 'Container App replica count exceeded the approved ceiling of two.'
		enabled: true
		severity: 1
		evaluationFrequency: 'PT1M'
		windowSize: 'PT5M'
		scopes: [
			containerApp.id
		]
		autoMitigate: true
		criteria: {
			'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
			allOf: [
				{
					name: 'ReplicaCountAboveTwo'
					criterionType: 'StaticThresholdCriterion'
					metricName: 'Replicas'
					metricNamespace: 'Microsoft.App/containerApps'
					operator: 'GreaterThan'
					threshold: 2
					timeAggregation: 'Maximum'
					skipMetricValidation: true
				}
			]
		}
		actions: [
			{
				actionGroupId: actionGroup.id
			}
		]
	}
}

output serviceUri string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output containerAppName string = containerApp.name
output containerAppsEnvironmentName string = containerAppsEnvironment.name
output containerRegistryEndpoint string = containerRegistry.properties.loginServer
output storageAccountUrl string = storageAccount.properties.primaryEndpoints.blob
output blobContainerName string = artifactContainer.name