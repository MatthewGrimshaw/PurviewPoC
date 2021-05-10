import logging
import json
import azure.functions as func
import os
import subprocess
import sys
import importlib
from docopt import docopt
from purviewcli import __version__
from purviewcli.cli import cli as pv
import re
import unicodedata
import io
from contextlib import redirect_stdout

def parse_json_recursively(json_object, target_key):    
    if type(json_object) is dict and json_object:
            for key in json_object:
                if key == target_key:
                    return(json_object[key])
                    break
                else:
                    parse_json_recursively(json_object[key], target_key)
   

def main(msg: func.QueueMessage):
    result = json.dumps({
        'id': msg.id,
        'body': msg.get_json(),
        'expiration_time': (msg.expiration_time.isoformat()
                            if msg.expiration_time else None),
        'insertion_time': (msg.insertion_time.isoformat()
                           if msg.insertion_time else None),
        'time_next_visible': (msg.time_next_visible.isoformat()
                              if msg.time_next_visible else None),
        'pop_receipt': msg.pop_receipt,
        'dequeue_count': msg.dequeue_count
    })
    
    # get the json
    res = json.loads(result)
    
    # create empty lists for bulk update
    listTermName = []
    listdefinitionName = []
    listresourceName= []
    listresourceUrlName = []

    glossaryGuid = "--glossaryGuid=" + os.environ.get('glossaryGuid')

    #calculate if it is a single term to be updated or a bulk update
    singleTerm = False
    if len(res['body']) == 1:
        singleTerm = True

    # parse the json
    for objBody in res['body']:
        termValue = parse_json_recursively(objBody, "termName")

        if termValue != None:
            importTerm = True            
            termName = "--termName=" + unicodedata.normalize('NFKD', termValue)

            #check if term already exists in catalog
            sys.argv = ["pv", "search", "advanced", "--keywords=\"" + re.escape(termValue) +"\""]
            f = io.StringIO()
            with redirect_stdout(f):
                pv.main()

            #output = subprocess.run(["pv", "search", "advanced", "--keywords=" + re.escape(termValue)], stdout=subprocess.PIPE)
            #decodedOutput = (output.stdout).decode('"unicode_escape"')
            #if re.search('\"name\": \"' + re.escape(termValue) + '\"', decodedOutput):
            
            #check the '@search.count' tag in the search result - it it is 0 then then term doen't exist in the catalog
            if json.loads(f.getvalue())['@search.count'] == 0:                
                listTermName.append(termName.replace('"', ""))
                logging.info("Term Name %s will be bulk-imported" %(termValue))
            else:
                importTerm = False  
                      
        else:
            logging.error("could not retrieve the name value from the JSON")

        
        definitionValue = parse_json_recursively(objBody, "longDescription")
        if definitionValue != None:
            definitionName = "--longDescription=" + unicodedata.normalize('NFKD', definitionValue)
            if importTerm == True and singleTerm == False:            
                listdefinitionName.append(definitionName.replace('"', ""))
            elif importTerm == True and singleTerm == True:
                sys.argv = ["pv", "glossary", glossaryGuid, termName.replace('"', ""), "--longDescription=" + definitionValue.replace('"', "")]
                logging.info("Term Name %s will be imported as a single item" %(termValue))  
            
        else:
            logging.info("Could not retreive the longDescription value")

        # parse the json
        resourceNameValue = parse_json_recursively(objBody, "resourceName")
        if resourceNameValue != None:
            resourceName = "--resourceName=" + unicodedata.normalize('NFKD', resourceNameValue)
            if importTerm == True and singleTerm == True:
                sys.argv += [resourceName.replace('"', "")]            
        else:
            logging.info("Could not retreive the resourceName value")

        # parse the json 
        resourceUrlValue = parse_json_recursively(objBody, "resourceUrl")
        if resourceUrlValue != None:
            resourceUrl = "--resourceUrl=" + unicodedata.normalize('NFKD', resourceUrlValue)
            if importTerm == True and singleTerm == True:
                sys.argv += [resourceUrl.replace('"', "")]
                expertId = "--expertId=" + os.environ.get('expertId')
                sys.argv += [expertId]
                stewardId = "--stewardId=" + os.environ.get('stewardId')
                sys.argv += [stewardId]  
                #import 
                logging.info("Term will be imported: The Arguments are: %s "  %(sys.argv))
                pv.main()
        else:
            logging.info("Could not retreive the resourceUrl value")

    logging.info("Number of items parsed is: %s" %(len(res['body'])))
    # bulk update
    if(len(listTermName) > 0):
        sys.argv = ["pv", "glossary", "createTerms", glossaryGuid.replace('"', "")]
        #iterate through lists to get values
        for ltn in listTermName:
            sys.argv += [ltn.replace(".", " ")]
        for ldn in listdefinitionName:
            sys.argv += [ldn.replace(".", " ")]        
        #update purview
        logging.info("Terms will be imported into the catalog. The arguments are:")
        logging.info(sys.argv)
        try:            
            f = io.StringIO()
            with redirect_stdout(f):
                pv.main()
            logging.info("Results of the glossary update are:")
            logging.info(f.getvalue())
        except AttributeError as error:
            # Output expected AttributeErrors.
            logging.error("failed to update Azure Purview because of an attribute error")
            logging.exception(error)
            logging.error(sys.exc_info()[0])
            logging.error(error)
        except:
            logging.error("failed to update Azure Purview")
            logging.error(sys.exc_info()[0])

    