# variables - these need to be updated
$tenantID = '<>'
$SubscriptionID = '<>'
$suffix = '<>'
$location = '<>'
$expertupn = '<>'
$stewardupn = '<>'

#### no need to change anything below this line ####
$suffix = $suffix.ToLower()
$resourceGroupName = $suffix + 'PurviewPoC'
$dataEstateResourceGroupName = $suffix + 'dataestate'
$purviewAccountName =  $suffix + 'purviewpoc'
$appInsightsName = $suffix + 'azurefunctionsappinsight'
$logAnalyticsWorkspaceName = $suffix + 'loganalyticsworkspace'
$keyVaultName = $suffix + 'purviewpockeyvault'
$functionAppName = $suffix + 'azurefunctionapp'
$storageaccountname = $suffix + 'purviewpocsa'
$appServicePlanName = $suffix + 'appserviceplan'
$serviceprincipalname = $suffix + 'purviewpocsp'

#Check 7-Zip ios installed
$7zipPath = "$env:ProgramFiles\7-Zip\7z.exe"
if(test-path $7zipPath){Set-Alias 7z $7zipPath}
else{
  write-output "please ensure 7Zip is installed from: https://www.7-zip.org/"
}
#install Azure cli
## Check AZ is installed
try {
    az --version
    az upgrade --all --yes
  }
  catch {
    #Invoke-WebRequest -Uri https://aka.ms/installazurecliwindows -OutFile .\AzureCLI.msi; Start-Process msiexec.exe -Wait -ArgumentList '/I AzureCLI.msi'
    choco uninstall azure-cli
    choco install azure-cli --version 2.15.1
    az version
  }

#allow AZ CLI extesnions to be installed
az config set extension.use_dynamic_install=yes_without_prompt

#login to azure
az login 
az account set --subscription $subscriptionID 

# Register providers
az provider register --namespace Microsoft.Purview
az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.EventHub
az provider register --namespace Microsoft.DataFactory

# Create Resource Group
az group create --location $location --name $resourceGroupName


# Deploy Purview Account 
push-location
set-location .\infra
az deployment group create --resource-group $resourceGroupName --template-file .\purview.json --parameters "name=$purviewAccountName"  "location=$location"
Pop-Location


# Get Starter Kit Dir 

Invoke-WebRequest -Uri https://github.com/Azure/Purview-Samples/raw/master/PurviewStarterKitV4.zip -OutFile .\PurviewStarterKitV4.zip
Expand-Archive -Path '.\PurviewStarterKitV4.zip' -DestinationPath '.\PurviewStarterKitV4' -force

# unblock files downloaded from the internet
Get-ChildItem -Recurse | Unblock-File

push-location
set-location '.\PurviewStarterKitV4\PurviewStarterKitV4'

# fix the location in the script
((Get-Content -path .\DemoScript.ps1 -Raw) -replace 'East US', $location) | Set-Content -Path .\DemoScript.ps1

# Run starter kit
.\RunStarterKit.ps1 -ConnectToAzure -TenantId $tenantID -SubscriptionId $SubscriptionID

.\RunStarterKit.ps1 -CatalogName $purviewAccountName -TenantId $tenantID `
-ResourceGroup $dataEstateResourceGroupName `
-SubscriptionId $SubscriptionID `
-CatalogResourceGroup $resourceGroupName 

Pop-Location

# Create Service Principal - the function apps will use this to authenticate to Azure Purview
$secret = $(az ad sp create-for-rbac `
--name $serviceprincipalname `
--role 'Purview Data Curator' `
--query password -o tsv)

$appId = $(az ad sp list --display-name $serviceprincipalname --query [].appId --output tsv)

# Remove SP
#$objectid = $(az ad sp list --display-name $serviceprincipalname --query [].objectId --output tsv)[0]
#az ad sp delete --id $objectid

# Create storage queues
push-location
set-location '.\Infra'
az deployment group create --resource-group $resourceGroupName --template-file .\azurestorage.template.json --parameters "name=$storageaccountname"  "location=$location"
Pop-Location


######## Create function app #########
# Create log analytics workspace
az monitor log-analytics workspace create `
--resource-group $resourceGroupName `
--workspace-name $logAnalyticsWorkspaceName `
--location $location `
--retention-time 180

# Get log analytics workspace ID
$logAnalyticsID = (az monitor log-analytics workspace show `
--resource-group $resourceGroupName `
--workspace-name $logAnalyticsWorkspaceName `
--query id `
--output tsv)

# add app insights extension
az extension add -n application-insights

# create app insights instance
az monitor app-insights component create `
--app $appInsightsName `
--location $location `
--kind web `
--resource-group $resourceGroupName `
--application-type web `
--workspace $logAnalyticsID

# Get App insights instrumentation key
$instrumentationKey = (az monitor app-insights component show `
--app $appInsightsName `
--resource-group $resourceGroupName `
--query instrumentationKey `
--output tsv)

# create key vault
az keyvault create --location $location --name $keyVaultName --resource-group $resourceGroupName

# create secrets

az keyvault secret set --name 'PURVIEWNAME' --vault-name $keyVaultName --value $purviewAccountName
az keyvault secret set --name 'AZURECLIENTID' --vault-name $keyVaultName --value $appId
az keyvault secret set --name 'AZURETENANTID' --vault-name $keyVaultName --value $tenantID
az keyvault secret set --name 'AZURECLIENTSECRET' --vault-name $keyVaultName --value $secret

# create basic app service plan
az appservice plan create --resource-group $resourceGroupName --name $appServicePlanName --is-linux

# Create function app
az functionapp create `
--resource-group $resourceGroupName `
--name $functionAppName `
--storage-account $storageaccountname `
--app-insights $appInsightsName `
--app-insights-key $instrumentationKey `
--assign-identity `
--functions-version 3 `
--plan $appServicePlanName `
--os-type Linux `
--runtime python `
--runtime-version 3.7 

# Get Function App Managed Identity
$functionAppIdentity = (az functionapp show --name $functionAppName --resource-group $resourceGroupName --query identity.principalId --output tsv)

# Grant Key Vault access to Function App Managed identity
az keyvault set-policy --name $keyVaultName --object-id $functionAppIdentity --secret-permissions get

# Get Secret identifiers 
$PURVIEWNAME = '@Microsoft.KeyVault(SecretUri=' + (az keyvault secret show --name 'PURVIEWNAME' --vault-name $keyVaultName --query id --output tsv) + ')'
$AZURECLIENTID = '@Microsoft.KeyVault(SecretUri=' + (az keyvault secret show --name 'AZURECLIENTID' --vault-name $keyVaultName --query id --output tsv) + ')'
$AZURETENANTID = '@Microsoft.KeyVault(SecretUri=' + (az keyvault secret show --name 'AZURETENANTID' --vault-name $keyVaultName --query id --output tsv) + ')'
$AZURECLIENTSECRET = '@Microsoft.KeyVault(SecretUri=' + (az keyvault secret show --name 'AZURECLIENTSECRET' --vault-name $keyVaultName --query id --output tsv) + ')'

# Configure Function App
$storageEndpoint = az storage account show-connection-string --resource-group $resourceGroupName --name  $storageaccountname --query connectionString --output tsv
$glossaryGuid=(az rest --method get --url "https://$purviewAccountName.catalog.purview.azure.com/api/atlas/v2/glossary" --resource "73c2949e-da2d-457a-9607-fcc665198967" | ConvertFrom-Json).guid
$stewardId = az ad user list --upn $stewardupn --query [].objectId --output tsv
$expertId = az ad user list --upn $expertupn --query [].objectId --output tsv
$glossaryOutPutQueue = "purview-glossary-queue"

az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "PURVIEW_NAME=""$PURVIEWNAME"""
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "AZURE_CLIENT_ID=""$AZURECLIENTID"""
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "AZURE_TENANT_ID=""$AZURETENANTID"""
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "AZURE_CLIENT_SECRET=""$AZURECLIENTSECRET"""
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "glossaryOutPutQueue=$glossaryOutPutQueue"
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "expertId=$expertId"
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "stewardId=$stewardId"
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "glossaryGuid=$glossaryGuid"
az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "AzureWebJobsStorage=$storageEndpoint"

# Deploy finction app
$publishFolder = ".\AzureFunctions\*"

# create the zip
$publishZip = "publish.zip"

#remove zip if it exists
if(test-path $publishZip){remove-item $publishZip}

# need to use 7-zip as Powershell uses the wrong encoding for Linux
7z a -mx=9 $publishZip $publishFolder

# deploy the zipped package
az functionapp deployment source config-zip `
--resource-group $resourceGroupName --name $functionAppName --src $publishZip 



#Get the function key
$functionkey = az functionapp function keys list --function-name 'GetBegreper' --name $functionAppName --resource-group $resourceGroupName --query 'default' --output tsv

# construct the url to trigger the import of terms. 
# There are some manual steps that need to be run first 
# 1) Create Glossay Guid
# 2) Load Azure Storage Python module 
# blocking out the next 2 line untill these issues are fixined / automated
#
# $url = "https://$functionAppName.azurewebsites.net/api/GetBegreper?code=$functionkey&search=bulkImport"
# Invoke-RestMethod -Method 'Get' -Uri $url


Install-Module -Name Az -Scope CurrentUser -Repository PSGallery -Force
Install-Module -Name Az.Account -Scope CurrentUser -Repository PSGallery -Force
Install-Module -Name Az.Storage -Scope CurrentUser -Repository PSGallery -Force
Install-Module -Name Az.DataFactory -Scope CurrentUser -Repository PSGallery -Force
Import-Module -Name Az 
Import-Module -Name Az.Account 
Import-Module -Name Az.Storage 
Import-Module -Name Az.Databricks 