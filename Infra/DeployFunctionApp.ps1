# variables - these need to be updated
$SubscriptionID = '<>'
$suffix = '<>' ## 


#### no need to change anything below this line ####
$suffix = $suffix.ToLower()
$resourceGroupName = $suffix + 'PurviewPoC'
$functionAppName = $suffix + 'azurefunctionapp'


#Check 7-Zip is installed
$7zipPath = "$env:ProgramFiles\7-Zip\7z.exe"
if(test-path $7zipPath){
  Set-Alias 7z $7zipPath
}else{
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

#allow AZ CLI extensions to be installed
az config set extension.use_dynamic_install=yes_without_prompt

#login to azure
az login 
az account set --subscription $subscriptionID 


$functionAppName = $functionAppName.substring(0,23)
az functionapp show --name $functionAppName --resource-group $resourceGroupName --query state

# Deploy function app
$publishFolder = ".\AzureFunctions\*"

# create the zip
$publishZip = "publish.zip"

#remove zip if it exists
if(test-path $publishZip){remove-item $publishZip}

# need to use 7-zip as Powershell uses the wrong encoding for Linux
7z a -mx=9 $publishZip $publishFolder

# deploy the zipped package
az functionapp deployment source config-zip `
--resource-group $resourceGroupName --name $functionAppName --src $publishZip --build-remote $true