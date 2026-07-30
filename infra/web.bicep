targetScope = 'resourceGroup'

param location string
param tags object
param environmentName string
@description('Create a new Azure Container Registry in this resource group. Defaults to true; PR environments should set this to false and pull from the shared ACR instead.')
param deployAcr bool = true
@description('Existing shared Azure Container Registry name. Required when deployAcr is false.')
param sharedContainerRegistryName string = ''
@description('Resource group containing the shared Azure Container Registry when deployAcr is false. Defaults to this deployment resource group.')
param sharedContainerRegistryResourceGroupName string = ''
param applicationIdentityClientId string
param applicationIdentityPrincipalId string
param applicationIdentityResourceId string
@secure()
param applicationInsightsConnectionString string
param applicationInsightsResourceId string
param logAnalyticsWorkspaceResourceId string
param openAiEndpoint string
param modelDeploymentName string
param raiPolicyName string
param raiPolicyVersion string
param workloadProfileType string
param workloadProfileMinimumCount int
param workloadProfileMaximumCount int
param containerCpu string
param containerMemory string
param monthlyBudgetAmount int
param budgetStartDate string
param alertContactEmails array
param enableApplicationSignalAlerts bool
param enableContainerAppsAuth bool = false
param entraAuthClientId string = ''
param entraAuthTenantId string = ''
param oidcTenantId string
param oidcClientId string
@secure()
param oidcClientSecret string
@secure()
param sessionSecretCurrent string
@secure()
param sessionSecretPrevious string
param applicationExternalIngress bool

@description('Precomputed Container App resource name from the Phase 1 naming module (CONTAINER_APP_NAME). Empty falls back to the dev-derived ca-fantasy-cards-<environmentName>, which overflows the 32-char Container App limit for long PR environment names; PR environments MUST supply this.')
param containerAppName string = ''

@description('Precomputed Container Apps managed environment name from the Phase 1 naming module (CONTAINER_APPS_ENVIRONMENT_NAME). Empty falls back to the dev-derived cae-fantasy-cards-<environmentName>; PR environments MUST supply this.')
param containerAppsEnvironmentName string = ''

@description('Precomputed Storage account name from the Phase 1 naming module (STORAGE_ACCOUNT_NAME). Empty falls back to the dev-derived stfc<resourceToken>. PR environments SHOULD supply this so the name is stable and hash-anchored rather than uniqueString-derived.')
param storageAccountName string = ''

@description('Precomputed private app-tier VNet name (VIRTUAL_NETWORK_NAME). Empty falls back to the dev-derived vnet-fantasy-cards-<environmentName>-private, which overflows the 64-char VNet limit for long PR environment names; PR environments MUST supply this.')
param virtualNetworkName string = ''

var resourceToken = toLower(uniqueString(subscription().subscriptionId, resourceGroup().id, environmentName))
var containerAppNameEffective = empty(containerAppName) ? 'ca-fantasy-cards-${environmentName}' : containerAppName
var containerAppsEnvironmentNameEffective = empty(containerAppsEnvironmentName) ? 'cae-fantasy-cards-${environmentName}' : containerAppsEnvironmentName
var containerRegistryName = 'acrfantasycards${resourceToken}'
var storageAccountNameEffective = empty(storageAccountName) ? 'stfc${resourceToken}' : storageAccountName
var blobContainerName = 'artifacts'
var monitoringMetricsPublisherRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '3913510d-42f4-4e42-8a64-420c390055eb')
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var blobDataContributorRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var privateContainerAppName = 'ca-fc-${resourceToken}-pvt'
var privateContainerAppsEnvironmentName = '${containerAppsEnvironmentNameEffective}-private'
var privateVirtualNetworkName = empty(virtualNetworkName) ? 'vnet-fantasy-cards-${environmentName}-private' : virtualNetworkName
var privateInfrastructureSubnetName = 'snet-container-apps-infrastructure'
var privateEndpointSubnetName = 'snet-private-endpoints'
var privateEndpointName = 'pe-${storageAccountNameEffective}-blob'
var privateDnsZoneName = 'privatelink.blob.${environment().suffixes.storage}'
var resolvedSharedContainerRegistryResourceGroupName = empty(sharedContainerRegistryResourceGroupName) ? resourceGroup().name : sharedContainerRegistryResourceGroupName
var containerAppsWorkloadProfileName = workloadProfileType == 'Consumption' ? 'Consumption' : 'dedicated'
var aadAuthSentinelClientId = '00000000-0000-4000-8000-000000000000'
var hasValidEntraAuthClientId = !empty(entraAuthClientId) && toLower(entraAuthClientId) != aadAuthSentinelClientId
var hasValidEntraAuthTenantId = !empty(entraAuthTenantId)
var enableAcaAuthConfig = enableContainerAppsAuth && hasValidEntraAuthClientId && hasValidEntraAuthTenantId
var entraOpenIdIssuer = '${environment().authentication.loginEndpoint}${entraAuthTenantId}/v2.0'
var containerAppsWorkloadProfile = workloadProfileType == 'Consumption' ? {
	name: containerAppsWorkloadProfileName
	workloadProfileType: workloadProfileType
} : {
	name: containerAppsWorkloadProfileName
	workloadProfileType: workloadProfileType
	minimumCount: workloadProfileMinimumCount
	maximumCount: workloadProfileMaximumCount
}
var publicApplicationBaseUrl = 'https://${containerAppNameEffective}.${containerAppsEnvironment.properties.defaultDomain}'
var privateApplicationBaseUrl = 'https://${privateContainerAppName}.${privateContainerAppsEnvironment.properties.defaultDomain}'
var applicationSecrets = {
	secureList: [
		{
			name: 'oidc-client-secret'
			value: oidcClientSecret
		}
		{
			name: 'session-secret-current'
			value: sessionSecretCurrent
		}
		{
			name: 'session-secret-previous'
			value: sessionSecretPrevious
		}
	]
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
	name: last(split(applicationInsightsResourceId, '/'))
}

module containerRegistry 'br/public:avm/res/container-registry/registry:0.9.3' = if (deployAcr) {
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
		name: storageAccountNameEffective
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

resource containerRegistryResource 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = if (deployAcr) {
	name: containerRegistryName
}

// Shared ACR reference path (deployAcr = false, e.g. PR environments). No new registry is created; the PR
// application identity is granted AcrPull on the existing shared registry via a nested module because a
// resource's `scope` must match its own file's target scope, and the shared registry may live in another
// resource group than this deployment.
module sharedAcrRbac 'modules/shared-acr-rbac.bicep' = if (!deployAcr) {
	name: 'shared-acr-rbac-${resourceToken}'
	scope: resourceGroup(resolvedSharedContainerRegistryResourceGroupName)
	params: {
		containerRegistryName: sharedContainerRegistryName
		principalId: applicationIdentityPrincipalId
		roleDefinitionId: acrPullRoleDefinitionId
		roleDescription: 'Allow the fantasy cards application identity to pull container images from the shared registry.'
	}
}

var containerRegistryLoginServer = deployAcr ? containerRegistry.outputs.loginServer : sharedAcrRbac.outputs.loginServer

resource storageAccountResource 'Microsoft.Storage/storageAccounts@2025-01-01' existing = {
	name: storageAccountNameEffective
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
			containerAppsWorkloadProfile
		]
		zoneRedundant: false
	}
}

// native-bicep-fallback: The maintained managed-environment AVM requires a Log Analytics shared key for app logs, which violates the approved secretless telemetry contract.
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2024-10-02-preview' = {
	name: containerAppsEnvironmentNameEffective
	location: location
	tags: tags
	properties: {
		appLogsConfiguration: {
			destination: 'azure-monitor'
		}
		publicNetworkAccess: 'Enabled'
		workloadProfiles: [
			containerAppsWorkloadProfile
		]
		zoneRedundant: false
	}
}

module containerApp 'br/public:avm/res/app/container-app:0.9.0' = {
	name: 'container-app-${resourceToken}'
	params: {
		name: containerAppNameEffective
		location: location
		tags: tags
		managedIdentities: {
			userAssignedResourceIds: [
				applicationIdentityResourceId
			]
		}
		environmentResourceId: containerAppsEnvironment.id
		workloadProfileName: containerAppsWorkloadProfileName
		activeRevisionsMode: 'Single'
		ingressAllowInsecure: false
		ingressExternal: false
		ingressTargetPort: 8000
		ingressTransport: 'auto'
		registries: [
				{
					identity: applicationIdentityResourceId
					server: containerRegistryLoginServer
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
							name: 'FANTASY_CARD_RAI_POLICY_NAME'
							value: raiPolicyName
						}
						{
							name: 'FANTASY_CARD_RAI_POLICY_VERSION'
							value: raiPolicyVersion
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
						{
							name: 'AZURE_TENANT_ID'
							value: oidcTenantId
						}
						{
							name: 'FANTASY_CARD_OIDC_CLIENT_ID'
							value: oidcClientId
						}
						{
							name: 'FANTASY_CARD_OIDC_CLIENT_SECRET'
							secretRef: 'oidc-client-secret'
						}
						{
							name: 'FANTASY_CARD_APPLICATION_BASE_URL'
							value: publicApplicationBaseUrl
						}
						{
							name: 'FANTASY_CARD_SESSION_SECRET_CURRENT'
							secretRef: 'session-secret-current'
						}
						{
							name: 'FANTASY_CARD_SESSION_SECRET_PREVIOUS'
							secretRef: 'session-secret-previous'
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
		secrets: applicationSecrets
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
		workloadProfileName: containerAppsWorkloadProfileName
		activeRevisionsMode: 'Single'
		ingressAllowInsecure: false
		ingressExternal: applicationExternalIngress
		ingressTargetPort: 8000
		ingressTransport: 'auto'
		registries: [
			{
				identity: applicationIdentityResourceId
				server: containerRegistryLoginServer
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
						name: 'FANTASY_CARD_RAI_POLICY_NAME'
						value: raiPolicyName
					}
					{
						name: 'FANTASY_CARD_RAI_POLICY_VERSION'
						value: raiPolicyVersion
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
					{
						name: 'AZURE_TENANT_ID'
						value: oidcTenantId
					}
					{
						name: 'FANTASY_CARD_OIDC_CLIENT_ID'
						value: oidcClientId
					}
					{
						name: 'FANTASY_CARD_OIDC_CLIENT_SECRET'
						secretRef: 'oidc-client-secret'
					}
					{
						name: 'FANTASY_CARD_APPLICATION_BASE_URL'
						value: privateApplicationBaseUrl
					}
					{
						name: 'FANTASY_CARD_SESSION_SECRET_CURRENT'
						secretRef: 'session-secret-current'
					}
					{
						name: 'FANTASY_CARD_SESSION_SECRET_PREVIOUS'
						secretRef: 'session-secret-previous'
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
		secrets: applicationSecrets
	}
}

resource containerAppResource 'Microsoft.App/containerApps@2024-10-02-preview' existing = {
	name: containerAppNameEffective
}

resource privateContainerAppResource 'Microsoft.App/containerApps@2024-10-02-preview' existing = {
	name: privateContainerAppName
}

// native-bicep-fallback: The selected Container App AVM module does not expose authConfig identity-provider wiring, so auth is configured explicitly on the deployed app.
resource containerAppAuthConfig 'Microsoft.App/containerApps/authConfigs@2024-10-02-preview' = if (enableAcaAuthConfig) {
	name: 'current'
	parent: containerAppResource
	properties: {
		platform: {
			enabled: true
		}
		globalValidation: {
			unauthenticatedClientAction: 'RedirectToLoginPage'
		}
		identityProviders: {
			azureActiveDirectory: {
				enabled: true
				registration: {
					clientId: entraAuthClientId
					openIdIssuer: entraOpenIdIssuer
				}
			}
		}
	}
	dependsOn: [
		containerApp
	]
}

// native-bicep-fallback: The selected Container App AVM module does not expose authConfig identity-provider wiring, so auth is configured explicitly on the deployed app.
resource privateContainerAppAuthConfig 'Microsoft.App/containerApps/authConfigs@2024-10-02-preview' = if (enableAcaAuthConfig) {
	name: 'current'
	parent: privateContainerAppResource
	properties: {
		platform: {
			enabled: true
		}
		globalValidation: {
			unauthenticatedClientAction: 'RedirectToLoginPage'
		}
		identityProviders: {
			azureActiveDirectory: {
				enabled: true
				registration: {
					clientId: entraAuthClientId
					openIdIssuer: entraOpenIdIssuer
				}
			}
		}
	}
	dependsOn: [
		privateContainerApp
	]
}

// native-bicep-fallback: The registry AVM supports registry-scoped assignments, but this explicit assignment preserves the existing deterministic name and role-definition-ID contract.
resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployAcr) {
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

// Shared ACR reference path (deployAcr = false, e.g. PR environments): AcrPull on the existing shared registry is
// granted by the `sharedAcrRbac` module above instead of creating a per-PR registry.

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
	dependsOn: [
		containerApp
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
// Only applies to a registry created in this deployment; a shared/external registry's diagnostics remain owned by its own environment.
resource registryDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (deployAcr) {
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
	dependsOn: [
		containerApp
	]
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
output containerRegistryEndpoint string = containerRegistryLoginServer
output storageAccountUrl string = storageAccount.outputs.primaryBlobEndpoint
output blobContainerName string = artifactContainer.name
