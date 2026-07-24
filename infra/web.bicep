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
var monitoringMetricsPublisherRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var blobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var privateContainerAppName = 'ca-fc-${resourceToken}-pvt'
var privateContainerAppsEnvironmentName = '${containerAppsEnvironmentName}-private'
var privateVirtualNetworkName = 'vnet-fantasy-cards-${environmentName}-private'
var privateInfrastructureSubnetName = 'snet-container-apps-infrastructure'
var privateEndpointSubnetName = 'snet-private-endpoints'
var privateEndpointName = 'pe-${storageAccountName}-blob'
var privateDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
	name: last(split(applicationInsightsResourceId, '/'))
}

module containerRegistry 'br/public:avm/res/container-registry/registry:0.9.3' = {
	name: 'container-registry-${resourceToken}'
	params: {
		name: containerRegistryName
		location: location
		tags: tags
		acrSku: 'Basic'
		acrAdminUserEnabled: false
		anonymousPullEnabled: false
		dataEndpointEnabled: false
		publicNetworkAccess: 'Enabled'
		azureADAuthenticationAsArmPolicyStatus: 'enabled'
		quarantinePolicyStatus: 'disabled'
		retentionPolicyStatus: 'disabled'
		retentionPolicyDays: 7
		trustPolicyStatus: 'disabled'
		enableTelemetry: false
	}
}

module storageAccount 'br/public:avm/res/storage/storage-account:0.9.1' = {
	name: 'storage-account-${resourceToken}'
	params: {
		name: storageAccountName
		location: location
		tags: tags
		skuName: 'Standard_LRS'
		accessTier: 'Hot'
		allowBlobPublicAccess: false
		allowCrossTenantReplication: false
		allowSharedKeyAccess: false
		defaultToOAuthAuthentication: true
		dnsEndpointType: 'Standard'
		minimumTlsVersion: 'TLS1_2'
		publicNetworkAccess: 'Disabled'
		supportsHttpsTrafficOnly: true
		managementPolicyRules: [
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
		blobServices: {
			containerDeleteRetentionPolicyEnabled: true
			containerDeleteRetentionPolicyDays: 7
			deleteRetentionPolicyEnabled: true
			deleteRetentionPolicyDays: 7
			deleteRetentionPolicyAllowPermanentDelete: false
			containers: [
				{
					name: blobContainerName
					publicAccess: 'None'
				}
			]
			diagnosticSettings: [
				{
					name: 'send-to-log-analytics'
					workspaceResourceId: logAnalyticsWorkspaceResourceId
					logAnalyticsDestinationType: 'Dedicated'
					logCategoriesAndGroups: [
						{
							categoryGroup: 'allLogs'
						}
					]
					metricCategories: [
						{
							category: 'Transaction'
						}
					]
				}
			]
		}
		enableTelemetry: false
	}
}

resource containerRegistryResource 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
	name: containerRegistryName
}

resource storageAccountResource 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
	name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' existing = {
	parent: storageAccountResource
	name: 'default'
}

resource artifactContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' existing = {
	parent: blobService
	name: blobContainerName
}

module privateVirtualNetwork 'br/public:avm/res/network/virtual-network:0.9.0' = {
	name: 'private-virtual-network-${resourceToken}'
	params: {
		name: privateVirtualNetworkName
		location: location
		tags: tags
		addressPrefixes: [
			'10.30.0.0/26'
		]
		subnets: [
			{
				name: privateInfrastructureSubnetName
				addressPrefix: '10.30.0.0/27'
				delegation: 'Microsoft.App/environments'
			}
			{
				name: privateEndpointSubnetName
				addressPrefix: '10.30.0.32/28'
				privateEndpointNetworkPolicies: 'Disabled'
			}
		]
		enableTelemetry: false
	}
}

module privateDnsZone 'br/public:avm/res/network/private-dns-zone:0.8.1' = {
	name: 'private-dns-zone-${resourceToken}'
	params: {
		name: privateDnsZoneName
		location: 'global'
		tags: tags
		virtualNetworkLinks: [
			{
				name: '${privateVirtualNetworkName}-link'
				virtualNetworkResourceId: privateVirtualNetwork.outputs.resourceId
				registrationEnabled: false
			}
		]
		enableTelemetry: false
	}
}

module blobPrivateEndpoint 'br/public:avm/res/network/private-endpoint:0.9.1' = {
	name: 'blob-private-endpoint-${resourceToken}'
	params: {
		name: privateEndpointName
		location: location
		tags: tags
		subnetResourceId: privateVirtualNetwork.outputs.subnetResourceIds[1]
		privateLinkServiceConnections: [
			{
				name: 'blob'
				properties: {
					privateLinkServiceId: storageAccountResource.id
					groupIds: [
						'blob'
					]
				}
			}
		]
		privateDnsZoneGroup: {
			name: 'blob'
			privateDnsZoneGroupConfigs: [
				{
					name: 'privatelink-blob-core-windows-net'
					privateDnsZoneResourceId: privateDnsZone.outputs.resourceId
				}
			]
		}
		enableTelemetry: false
	}
	dependsOn: [
		storageAccount
	]
}

// native-bicep-fallback: The maintained managed-environment AVM requires a Log Analytics shared key for app logs, which violates the approved secretless telemetry contract.
resource privateContainerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
	name: privateContainerAppsEnvironmentName
	location: location
	tags: tags
	properties: {
		appLogsConfiguration: {
			destination: 'azure-monitor'
		}
		publicNetworkAccess: 'Enabled'
		vnetConfiguration: {
			infrastructureSubnetId: privateVirtualNetwork.outputs.subnetResourceIds[0]
			internal: false
		}
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

// native-bicep-fallback: The maintained managed-environment AVM requires a Log Analytics shared key for app logs, which violates the approved secretless telemetry contract.
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

module containerApp 'br/public:avm/res/app/container-app:0.9.0' = {
	name: 'container-app-${resourceToken}'
	params: {
		name: containerAppName
		location: location
		tags: tags
		managedIdentities: {
			userAssignedResourceIds: [
				applicationIdentityResourceId
			]
		}
		environmentResourceId: containerAppsEnvironment.id
		workloadProfileName: 'dedicated'
		activeRevisionsMode: 'Single'
		ingressAllowInsecure: false
		ingressExternal: true
		ingressTargetPort: 8000
		ingressTransport: 'auto'
		registries: [
				{
					identity: applicationIdentityResourceId
					server: containerRegistry.outputs.loginServer
				}
			]
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
							value: storageAccount.outputs.primaryBlobEndpoint
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
		scaleMinReplicas: 1
		scaleMaxReplicas: 2
		scaleRules: [
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

module privateContainerApp 'br/public:avm/res/app/container-app:0.9.0' = {
	name: 'private-container-app-${resourceToken}'
	params: {
		name: privateContainerAppName
		location: location
		tags: union(tags, {
			'azd-service-name': 'web'
		})
		managedIdentities: {
			userAssignedResourceIds: [
				applicationIdentityResourceId
			]
		}
		environmentResourceId: privateContainerAppsEnvironment.id
		workloadProfileName: 'dedicated'
		activeRevisionsMode: 'Single'
		ingressAllowInsecure: false
		ingressExternal: true
		ingressTargetPort: 8000
		ingressTransport: 'auto'
		registries: [
			{
				identity: applicationIdentityResourceId
				server: containerRegistry.outputs.loginServer
			}
		]
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
						value: storageAccount.outputs.primaryBlobEndpoint
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
		scaleMinReplicas: 1
		scaleMaxReplicas: 2
		scaleRules: [
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

resource containerAppResource 'Microsoft.App/containerApps@2024-10-02-preview' existing = {
	name: containerAppName
}

resource privateContainerAppResource 'Microsoft.App/containerApps@2024-10-02-preview' existing = {
	name: privateContainerAppName
}

// native-bicep-fallback: The registry AVM supports registry-scoped assignments, but this explicit assignment preserves the existing deterministic name and role-definition-ID contract.
resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
	scope: containerRegistryResource
	name: guid(containerRegistryResource.id, applicationIdentityPrincipalId, acrPullRoleDefinitionId)
	dependsOn: [
		containerRegistry
	]
	properties: {
		principalId: applicationIdentityPrincipalId
		principalType: 'ServicePrincipal'
		roleDefinitionId: acrPullRoleDefinitionId
		description: 'Allow the fantasy cards application identity to pull container images from the registry.'
	}
}

// native-bicep-fallback: The Storage AVM does not expose the required artifact-container scope for this least-privilege assignment.
resource blobDataAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
	scope: artifactContainer
	name: guid(artifactContainer.id, applicationIdentityPrincipalId, blobDataContributorRoleDefinitionId)
	dependsOn: [
		storageAccount
	]
	properties: {
		principalId: applicationIdentityPrincipalId
		principalType: 'ServicePrincipal'
		roleDefinitionId: blobDataContributorRoleDefinitionId
		description: 'Allow the fantasy cards application identity to read and write private artifacts.'
	}
}



// native-bicep-fallback: No selected AVM exposes the required Application Insights component scope.
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

// native-bicep-fallback: The selected managed-environment AVM is unsuitable because it requires a shared key; this diagnostic setting remains tied to the native environment fallback.
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

// native-bicep-fallback: The selected managed-environment AVM is unsuitable because it requires a shared key; this diagnostic setting remains tied to the native private-environment fallback.
resource privateEnvironmentDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: privateContainerAppsEnvironment
	name: 'send-to-log-analytics'
	dependsOn: [
		privateContainerApp
	]
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

// native-bicep-fallback: The Container App AVM does not expose the required app diagnostic-setting configuration.
resource appDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: containerAppResource
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

// native-bicep-fallback: The Container App AVM does not expose the required app diagnostic-setting configuration.
resource privateAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: privateContainerAppResource
	name: 'send-to-log-analytics'
	dependsOn: [
		privateContainerApp
	]
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

// native-bicep-fallback: The registry diagnostic setting preserves the current dedicated Log Analytics destination and category selection.
resource registryDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
	scope: containerRegistryResource
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

// native-bicep-fallback: No suitable selected AVM preserves the approved email-receiver and alert-action contract.
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

// native-bicep-fallback: No maintained AVM resource module supports the required resource-group budget notification contract.
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

// native-bicep-fallback: No suitable AVM preserves this application-specific KQL alert query.
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

// native-bicep-fallback: No suitable AVM preserves this application-specific KQL alert query.
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

// native-bicep-fallback: No suitable AVM preserves this application-specific KQL alert query.
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

// native-bicep-fallback: No suitable AVM preserves this application-specific KQL alert query.
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

// native-bicep-fallback: No suitable AVM preserves the Container Apps replica metric and approved threshold contract.
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
			containerAppResource.id
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

output serviceUri string = 'https://${privateContainerApp.outputs.fqdn}'
output containerAppName string = privateContainerApp.outputs.name
output containerAppsEnvironmentName string = privateContainerAppsEnvironment.name
output containerRegistryEndpoint string = containerRegistry.outputs.loginServer
output storageAccountUrl string = storageAccount.outputs.primaryBlobEndpoint
output blobContainerName string = artifactContainer.name
