# PurviewPoC

## This repository will automate the creation of an Azure Purview account and provide an example of how to integrate with other data catalogs using Azure Functions

&nbsp;
&nbsp;

Azure Functions are used to extract Glossary terms (begreper) from the Norweigian National Data Catalog (data.norge.no) and import them into Azure Purview. A function is also provided to extract data from Purview with the aim of inserting it into another data catalog.

&nbsp;
&nbsp;

The conceptual Architecture is demonstrated below:

![Architecture](/Images/architecture.png)

&nbsp;
&nbsp;
&nbsp;

The Azure Purview Starter kit will be installed to create some test data in the Purview Account: https://github.com/Azure/Purview-Samples

&nbsp;
&nbsp;
&nbsp;

## To deploy this solution, start by cloning the repository:

- git clone https://github.com/MatthewGrimshaw/PurviewPoC

&nbsp;
&nbsp;

Install the required prerequites before you run the setup script:

- Install the Azuzre CLI : https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

- Install 7 Zip from https://www.7-zip.org/

- Install or Update the Azure Powershell Modules:

```powershell
Install-Module -Name Az -Scope CurrentUser -Repository PSGallery -Force
Install-Module -Name Az.Account -Scope CurrentUser -Repository PSGallery -Force
Install-Module -Name Az.Storage -Scope CurrentUser -Repository PSGallery -Force
Install-Module -Name Az.DataFactory -Scope CurrentUser -Repository PSGallery -Force
Import-Module -Name Az 
Import-Module -Name Az.Account 
Import-Module -Name Az.Storage 
Import-Module -Name Az.DataFactory 
```

&nbsp;
&nbsp;

correct variables in script Infra\CreateInfra.ps1

![variables](/Images/variables.PNG)

&nbsp;
&nbsp;

Run the powershell script 'CreateInfra.ps1'. There will be multiple authentication pop-ups during the course of the scripts execution

&nbsp;
&nbsp;

## Post Installation

&nbsp;
&nbsp;

The Azure Storage python module does not seem to be loading correctly into the Function App at the moment. To workaround this problem, once the 'CreateInfra.ps1' script has finished running, please do the following:

- log into Kudo and start a bash shell (In the Azure Portal -> Resource Group -> Function App -> )Development Tools -> Advanced Tools -> Go)

- Run the following command : 'python3 -m pip install azure-storage-queue==2.1.0'

![Kudo](/Images/Kudo.PNG)

&nbsp;
&nbsp;

## Azure Purview Glossary

&nbsp;
&nbsp;

It seems that the Purview Glossary creation does not complete untill the first user logs in. Once the 'CreateInfra.ps1' script has finished running, log into Azure Purview (Azure Portal -> Resource Group -> Purview Account -> Purview Studio) and click the glossary icon on the left menu.  This will generate the correct glossary guid, and you can then run the follwoing lines of code:

&nbsp;
&nbsp;

```powershell
$glossaryGuid=(az rest --method get --url "https://$purviewAccountName.catalog.purview.azure.com/api/atlas/v2/glossary" --resource "73c2949e-da2d-457a-9607-fcc665198967" | ConvertFrom-Json).guid

az functionapp config appsettings set --name $functionAppName --resource-group $resourceGroupName --settings "glossaryGuid=$glossaryGuid"
```

&nbsp;
&nbsp;

## Runing the Functions

&nbsp;
&nbsp;

Log onto the Function in the Azure Portal and retrieve the Function Key (Azure Portal -> Resource Group -> Function App - > Functions - Function Name (GetBegreper)) and press on the 'Get Function Url' button

&nbsp;
&nbsp;

![FunctionUrl](/Images/FunctionURL.png)

&nbsp;
&nbsp;

Enter the FunctionURl into a browser and append with a search term:

&nbsp;
&nbsp;

- To retrieve a single term enter: &search='< guid for search term from Data.Norge.no >'
- To retrieve all terms enter : &search=bulkImport

&nbsp;
&nbsp;

or run the following code to import all terms:

&nbsp;
&nbsp;

```powershell
#Get the function key
$functionkey = az functionapp function keys list --function-name 'GetBegreper' --name $functionAppName --resource-group $resourceGroupName --query 'default' --output tsv

# construct the url to trigger the import of terms
$url = "https://$functionAppName.azurewebsites.net/api/GetBegreper?code=$functionkey&search=bulkImport"

Invoke-RestMethod -Method 'Get' -Uri $url
```

&nbsp;
&nbsp;

### Exporting Data sets

&nbsp;
&nbsp;

call the 'getEntities' function with the following sytax:

https://functionappname.azurewebsites.net/api/getEntities?code=$functionkey>&search=<datasetname>&assetType=<assetTypeName>&entityName=<entityName>

&nbsp;
&nbsp;

for example:

http://<functionappname>.azurewebsites.net/api/getEntities?code=<functionkey>/api/getEntities?search=mattazuresqldb&assetType=Azure SQL Database&entityType=azure_sql_db


## Legal Notices
Microsoft and any contributors grant you a license to the Microsoft documentation and other content in this repository under the Creative Commons Attribution 4.0 International Public License, see the LICENSE file, and grant you a license to any code in the repository under the MIT License.

Microsoft, Windows, Microsoft Azure and/or other Microsoft products and services referenced in the documentation may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries. The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks. Microsoft's general trademark guidelines can be found at http://go.microsoft.com/fwlink/?LinkID=254653.

Privacy information can be found at https://privacy.microsoft.com/en-us/

Microsoft and any contributors reserve all other rights, whether under their respective copyrights, patents, or trademarks, whether by implication, estoppel, or otherwise. &nbsp;