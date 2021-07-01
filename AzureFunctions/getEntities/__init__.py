import logging
import azure.functions as func
import sys
import importlib
from docopt import docopt
from purviewcli import __version__
from purviewcli.cli import cli as pv
import io
import re
import os
from contextlib import redirect_stdout
import json
from datacatalogtordf import Catalog, Dataset

def entitySearch(search):
    keywords = "--keywords=" + search   
    sys.argv = ["pv", "search", "advanced",  keywords.replace('"', "")]
    logging.info(sys.argv)
    
    f = io.StringIO()
    with redirect_stdout(f):
        pv.main()
    out = f.getvalue()
    return(out)


def main(req: func.HttpRequest, msg: func.Out[str]) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    search = req.params.get('search')
    if not search:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            search = req_body.get('search')

    assetType = req.params.get('assetType')
    if not assetType:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            search = req_body.get('assetType')

    entityType = req.params.get('entityType')
    if not entityType:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            search = req_body.get('entityType')

    if search:
        
        logging.info(search)
        logging.info(assetType)
        logging.info(entityType)

        # search purview
        value = entitySearch(search)

        if int(json.loads(value)['@search.count']) > 0:
            logging.info(json.loads(value)['@search.count'])
        else:
            logging.info("Nothing was returned from the search")
            return func.HttpResponse(
             "This HTTP triggered function executed successfully, but no search criteria was returned from the Purview catalog. Pass a search in the query string or in the request body for a response.",
             status_code=200
        )

        #parse the response
        objToexport = []
        score = 0
        #loop through all of the results and filter on the assetType and entityType
        
        jsonObj = json.loads(value)
        
        for obj in jsonObj['value'] :
            if (obj['assetType'][0] == assetType) and (obj['entityType'] == entityType):       
                #if there are multiple objects returned, select the one with the highest score
                if (obj['@search.score'] > score):
                    objToexport = obj
                    score = obj['@search.score']

        # return function if not match has been found in the data returned from Purview
        if(len(objToexport) == 0):
            logging.info("No match was found in the Purview catalog for the search, assetType and entityType combination entityType: {0} {1} {2} ".format(search, assetType, entityType))
            return func.HttpResponse(
             f"No match was found in the Purview catalog for search : {search}  assetType: {assetType} entityType: {entityType} ",
             status_code=200
        )

        publisher = os.environ.get('publisher')
        logging.info(objToexport['assetType'])
        logging.info(objToexport['entityType']) 
        logging.info(objToexport['@search.score'])
        logging.info(objToexport['qualifiedName'])
        logging.info(objToexport['name'])
        logging.info(publisher)
        logging.info(score)

        # Create catalog object
        catalog = Catalog()
        catalog.identifier = objToexport['qualifiedName']
        catalog.title = {"en": objToexport['name']}
        catalog.publisher = publisher

        # Create a dataset:
        dataset = Dataset()
        dataset.identifier = objToexport['qualifiedName']
        dataset.title = {"nb": objToexport['name'], "en": objToexport['name']}
        #
        # Add dataset to catalog:
        catalog.datasets.append(dataset)

        # get rdf representation in turtle (default)
        rdf = catalog.to_rdf()
        logging.info(rdf.decode())


        # write the rdf to Azure storage
        msg.set(rdf.decode())

        # return the function 
        return func.HttpResponse(f"The HTTP triggered function for {search} executed successfully. The assetType provided was: {assetType} and the entityType was: {entityType }")

    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully, but no search criteria was supplied. Pass a search in the query string or in the request body for a response.",
             status_code=200
        )
