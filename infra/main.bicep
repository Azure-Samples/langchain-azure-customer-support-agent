targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (used to generate resource names)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the principal (user) for local development RBAC. Set automatically by `azd`.')
param principalId string = ''

@description('Main support driver model deployment name.')
param mainDeploymentName string = 'gpt-5.4-mini'

@description('Main support driver model name.')
param mainModelName string = 'gpt-5.4-mini'

@description('Main support driver model version.')
param mainModelVersion string = '2026-03-17'

@description('Cheap utility model deployment name (refine, validate, summarise).')
param nanoDeploymentName string = 'gpt-5-nano'

@description('Cheap utility model name.')
param nanoModelName string = 'gpt-5-nano'

@description('Cheap utility model version.')
param nanoModelVersion string = '2025-08-07'

@description('Embedding model deployment name (used at author time only — kb_embeddings.npy is committed).')
param embeddingDeploymentName string = 'text-embedding-3-small'

@description('Whether the chat container app already exists (set by azd).')
param chatExists bool = false

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = { 'azd-env-name': environmentName }

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'resources'
  scope: rg
  params: {
    location: location
    tags: tags
    resourceToken: resourceToken
    abbrs: abbrs
    principalId: principalId
    mainDeploymentName: mainDeploymentName
    mainModelName: mainModelName
    mainModelVersion: mainModelVersion
    nanoDeploymentName: nanoDeploymentName
    nanoModelName: nanoModelName
    nanoModelVersion: nanoModelVersion
    embeddingDeploymentName: embeddingDeploymentName
    chatExists: chatExists
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = rg.name
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = resources.outputs.containerRegistryLoginServer

output AZURE_OPENAI_ENDPOINT string = resources.outputs.openAiEndpoint
output AZURE_OPENAI_MAIN_DEPLOYMENT string = mainDeploymentName
output AZURE_OPENAI_NANO_DEPLOYMENT string = nanoDeploymentName
output AZURE_OPENAI_EMBEDDING_DEPLOYMENT string = embeddingDeploymentName

output CHAT_URL string = resources.outputs.chatUri
output APPLICATIONINSIGHTS_CONNECTION_STRING string = resources.outputs.applicationInsightsConnectionString
