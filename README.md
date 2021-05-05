# PurviewPoC
This repository will automate the creation of an Azure Purview account and provide an example of how to integrate with other data catalogs using Azure Functions.

Azure Functions are used to extract Glossary terms (begreper) from the Norweigian National Data Catalog (data.norge.no) and import them into Azure Purview.

A function is also provided to extract data from Purview with the aim of inserting it into another data catalog.



The conceptual Architecture is demonstrated below:

![Screenshot](architecture.png)

&nbsp;
&nbsp;
&nbsp;

The Azure Purview Starter kit will be installed to create some test data in the Purview Account: https://github.com/Azure/Purview-Samples

&nbsp;
&nbsp;
&nbsp;

To deploy this solution start by cloning the repository:

- git clone https://github.com/MatthewGrimshaw/PurviewPoC

- Install the Azuzre CLI : https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

