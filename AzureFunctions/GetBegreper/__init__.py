import logging
import rdflib
import json
import unicodedata
import sys

import azure.functions as func
from azure.storage.queue import (
        QueueService,
        QueueMessageFormat
)

import os, uuid

def writeToAzureQueue(outputList):
        # send the output to the queue
        logging.info("outputqueueLength = %s" %(str(len(outputList))))      
        connect_str = os.getenv("AzureWebJobsStorage")
        queue_name = os.getenv("glossaryOutPutQueue")
        queue_service = QueueService(connection_string=connect_str)
        queue_service.encode_function = QueueMessageFormat.binary_base64encode
        queue_service.decode_function = QueueMessageFormat.binary_base64decode             
        queue_service.put_message(queue_name, json.dumps(outputList).encode('utf-8'))

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')
    
    outputList = []
    totalTerms = 0  
    search = req.params.get('search')
    if not search:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            search = req_body.get('search')

    if search:
        if search.lower() == 'bulkimport':
            begrepUrl = 'https://concepts.fellesdatakatalog.digdir.no/collections'
            # bulk import all terms from the catalog
            logging.info("The search is: " + search)
                    
        else:
            # get a single item          
            begrepUrl = 'https://fellesdatakatalog.digdir.no/api/concepts/' + '/' + search
            logging.info("The search is: " + search)
            logging.info("The url is:" + begrepUrl)            
        
        #create graph and parse url
        g = rdflib.Graph()
        g.parse(begrepUrl)

        # Query the returned data
        try:
            query = g.query("""PREFIX ns1:    <https://data.norge.no/vocabulary/skosno#>
                      SELECT DISTINCT  ?concept ?label ?subject
                      WHERE
                      {                             
                          ?concept a skos:Concept .
                          ?concept skosxl:prefLabel/skosxl:literalForm ?label .
                          ?concept <http://difi.no/skosno#betydningsbeskrivelse>/rdfs:label ?subject .
                          FILTER NOT EXISTS {?concept ns1:definisjon/rdfs:label ?xsubject .}
                          FILTER NOT EXISTS {?concept <http://difi.no/skosno#betydningsbeskrivelse>/dct:source/rdfs:label ?ysubject .}
                      }
                      """)
            for res in query:
                purview_dict = {}
                purview_dict["termName"] = res.label
                purview_dict["longDescription"] = res.subject
                outputList.append(purview_dict)
                totalTerms +=1
            
            query = g.query("""PREFIX ns1:    <https://data.norge.no/vocabulary/skosno#>
                      SELECT DISTINCT  ?concept ?label ?subject
                      WHERE
                      {                             
                          ?concept a skos:Concept .
                          ?concept skosxl:prefLabel/skosxl:literalForm ?label .
                          ?concept <http://difi.no/skosno#betydningsbeskrivelse>/dct:source/rdfs:label ?subject .
                          FILTER NOT EXISTS {?concept ns1:definisjon/rdfs:label ?xsubject .}
                          
                      }
                      """)
            for res in query:
                purview_dict = {}
                purview_dict["termName"] = res.label
                purview_dict["longDescription"] = res.subject
                outputList.append(purview_dict)
                totalTerms +=1
            
            query = g.query("""PREFIX ns1:    <https://data.norge.no/vocabulary/skosno#>
                      SELECT DISTINCT  ?concept ?label ?subject
                      WHERE
                      {                             
                          ?concept a skos:Concept .
                          ?concept skosxl:prefLabel/skosxl:literalForm ?label .
                          ?concept ns1:definisjon/rdfs:label ?subject .
                          FILTER NOT EXISTS {?concept <http://difi.no/skosno#betydningsbeskrivelse>/dct:source/rdfs:label ?xsubject .}
                                                    
                      }
                      """)
            for res in query:
                purview_dict = {}
                purview_dict["termName"] = res.label
                purview_dict["longDescription"] = res.subject
                outputList.append(purview_dict)
                totalTerms +=1
        
        except:
            logging.error("failed to parse the url %s" %(begrepUrl))
            logging.error(sys.exc_info()[0])
                
            return func.HttpResponse(
                    "Internal Error in the Function Execution - check the log files for more details",
                    status_code=500
                )
        
        #log  
        logging.info("Total terms written to queue storage are: %s" %(totalTerms))

        # write terms to queue in batches of 75 so that the queue ites are not too large
        chunk_size = 75
        for i in range(0, len(outputList), chunk_size):
            chunk = outputList[i:i+chunk_size]    
            # process chunk of size <= chunk_size 
            writeToAzureQueue(chunk)

        return func.HttpResponse(f"Function executed successfully. The term passed to the function was: {search}. The total number of terms written to the queue is: {totalTerms}")
        
    else:        
        return func.HttpResponse(            
             "Pass a valid search value or bulkImport in the query string or in the request body to import terms.",
             status_code=200
        )