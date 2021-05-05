import logging
import urllib.request
import json
import unicodedata
import sys

import azure.functions as func
from azure.storage.queue import (
        QueueService,
        QueueMessageFormat
)

import os, uuid

def parse_json_recursively(json_object, target_key):    
    if type(json_object) is dict:
            for key in json_object:
                if key == target_key:
                    if target_key =='publisher':
                            return(json_object[target_key]['name'], json_object[target_key]['uri'])
                    for k,v in json_object[target_key].items():
                        if type(v) == dict and target_key =='definition':                   
                            if 'nb' in v:
                                return(v['nb'])
                            elif 'nn' in v:
                                return(v['nn'])
                            elif 'nb' in json_object['definition']['sources'][0]['text']:                                    
                                return json_object['definition']['sources'][0]['text']['nb']
                            elif 'nn' in json_object['definition']['sources'][0]['text']:                                    
                                return json_object['definition']['sources'][0]['text']['nn']
                                
                        return(v)
                else:
                    parse_json_recursively(json_object[key], target_key)

def outputQueueData(jsonObj, outputList):
    purview_dict = {}

    nameValue = parse_json_recursively(jsonObj, 'prefLabel')
    if nameValue:            
        purview_dict["termName"] = unicodedata.normalize('NFKD',nameValue)
    else:
        logging.error("could not find the name value")
        return
        
    definitionvalue = parse_json_recursively(jsonObj, 'definition')
    if definitionvalue:
        purview_dict["longDescription"] = unicodedata.normalize('NFKD', definitionvalue)
    else:
        logging.info("could not find the description value")
        
    publishervalue = parse_json_recursively(jsonObj, 'publisher')
    if publishervalue:
        purview_dict["resourceName"] = unicodedata.normalize('NFKD', publishervalue[0])
        purview_dict["resourceUrl"] = unicodedata.normalize('NFKD', publishervalue[1])
    else:
        logging.info("could not find the publisher value")    
    
    try:
        outputList.append(purview_dict)
        del purview_dict
        del jsonObj
    except:
        logging.info("could not append the output list")
        logging.error(sys.exc_info()[0])

    return outputList

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

    begrepUrl = 'https://data.norge.no/api/concepts'
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
            # bulk import all terms from the catalog
            logging.info("The search is: " + search)
            count = 0
            loop = True
            while loop == True:
                # The &size= value can actually go up 1000, but Azure Storage Queues only support max 64kb messages, so 150 seems to be the upper limit
                # The bigger the size, the less messages are written, and the faster they are imported
                xbegrepUrl = begrepUrl + '?page=' + (str(count)) + '&size=145'            
                logging.info("The url is :" + xbegrepUrl)            
                try:
                    with urllib.request.urlopen(xbegrepUrl ) as url:
                        data = json.loads(url.read().decode())
                        pages = int(data['page']['totalPages'])
                        logging.info("pages is : " + str(pages)) 
                        logging.info("count is : " + str(count))
                        logging.info("Loop is : " + str(loop))
                        for jsonObj in data['_embedded']['concepts']:
                            #parse the json 
                            outputQueueData(jsonObj, outputList)                            
                        #write to Azure queue
                        writeToAzureQueue(outputList)
                        totalTerms += len(outputList)
                        outputList.clear()
                        count += 1                            
                        if(count == pages):
                            loop = False
                        del data
                
                except:
                    logging.error("failed to open the url %s" %(begrepUrl))
                    logging.error(sys.exc_info()[0])
                    return func.HttpResponse(
                        "Internal Error in the Function Execution - check the log files for more details",
                        status_code=500
                    )
                    
        else:
            # get a single item          
            begrepUrl = begrepUrl + '/' + search
            logging.info("The search is: " + search)
            logging.info("The url is:" + begrepUrl)
            try:
                with urllib.request.urlopen(begrepUrl ) as url:
                    data = json.loads(url.read().decode())
                    outputQueueData(data, outputList)
                    writeToAzureQueue(outputList)
                    totalTerms += len(outputList)
            except:
                logging.error("failed to open the url %s" %(begrepUrl))
                logging.error(sys.exc_info()[0])
                
                return func.HttpResponse(
                    "Internal Error in the Function Execution - check the log files for more details",
                    status_code=500
                )
        
        #log  
        logging.info("Total terms written to queue storage are: %s" %(totalTerms))    
        return func.HttpResponse(f"Function executed successfully. The term passed to the function was: {search}. The total number of terms written to the queue is: {totalTerms}")
        
    else:        
        return func.HttpResponse(            
             "Pass a valid search value or bulkImport in the query string or in the request body to import terms.",
             status_code=200
        )
 