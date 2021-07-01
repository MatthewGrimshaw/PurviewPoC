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
from random import randrange
import tempfile


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

    # get the json fron the queue
    res = json.loads(result)
    
    # create empty list for bulk update
    payload_file = []

    glossaryGuid = os.environ.get('glossaryGuid')

    #calculate if it is a single term to be updated or a bulk update
    singleTerm = False
    if len(res['body']) == 1:
        singleTerm = True
    
    # the purviewcli is very verbose in the logs, therefore we need to suppress the output and use logging.warning
    # the createGlossaryItems function is configured to log only warnings in the 'hosts.json' file
    logging.warning("singleTerm: %s" %(singleTerm))

    # parse the json
    for objBody in res['body']:
        termValue = parse_json_recursively(objBody, "termName")
        # Terms name with uppper / lower case combinations can cause the import to fail - set the first character to lower case
        termValue = termValue[0].lower() + termValue[1:]

        if termValue != None:            
            importTerm = True            
            # A term name can't have a period (".") in the Azure purview catalog, so we need to remove it
            termValue = termValue.replace(".", " ")        
            termName = "--termName=" + unicodedata.normalize('NFKD', termValue)

            #check if term already exists in catalog
            sys.argv = ["pv", "search", "query", "--keywords=\"" + re.escape(termValue) +"\""]
            f = io.StringIO()
            with redirect_stdout(f):
                try:                
                     pv.main()
                except:
                    logging.error("failed to search Azure Purview")
                    logging.warning("sys.argv = %s" %(sys.argv))
                    logging.error(sys.exc_info()[0])
                    logging.exception("The exception is:")

            # if the search value is 0 it doesn't exits. If it is greater than Zero we need to parse the JSON for an extact match
            if int(json.loads(f.getvalue())['@search.count']) > 0:
                for element in json.loads(f.getvalue())['value']:
                    qualifiedName = parse_json_recursively(element, 'name')
                    # try all combinations of escaping
                    if qualifiedName != None and (qualifiedName == termValue \
                    or qualifiedName == re.escape(termValue) \
                    or re.escape(qualifiedName) == re.escape(termValue) \
                    or re.escape(qualifiedName) == termValue):
                        importTerm = False
                        logging.warning("term %s already exists and will not be imported" %(termValue))

            # The term will be imported if it doesn't already exist in the catalog
            if importTerm == True:
                # get the description
                definitionValue = parse_json_recursively(objBody, "longDescription")
                if definitionValue != None:
                    definitionName = "--longDescription=" + unicodedata.normalize('NFKD', definitionValue)
                    if singleTerm == False:                        
                        #check termName is not already in the list
                        if termName.replace('"', "") not in json.dumps(payload_file):
                            logging.warning("Term Name %s will be bulk-imported" %(termValue))
                            # append termName and defintionName to the payload file that will be bulk imported 
                            anchor = {"glossaryGuid" : glossaryGuid}
                            json_file = {}
                            json_file['anchor'] = anchor
                            json_file['longDescription'] = definitionName.replace('"', "")                     
                            json_file['name'] = termName.replace('"', "")
                            payload_file.append(json_file)                            
                    elif singleTerm == True:
                        # import a single term straight away
                        sys.argv = ["pv", "glossary", "createTerm", glossaryGuid, termName.replace('"', ""), "--longDescription=" + definitionValue.replace('"', "")]
                        logging.warning("Term Name %s will be imported as a single item" %(termValue))
                        anchor = {"glossaryGuid" : glossaryGuid}
                        json_file = {}
                        json_file['anchor'] = anchor
                        json_file['longDescription'] = definitionName.replace('"', "")                     
                        json_file['name'] = termName.replace('"', "")
                        singlePayload = []
                        singlePayload.append(json_file)
                        
                        fileName = str(randrange(6000)) + 'payload.json'
                        tempFilePath = os.path.join(tempfile.gettempdir(), fileName)
                        f = open(tempFilePath, "w+") 
                        f.write(json.dumps(singlePayload))
                        f.flush()
                        f.close
                        sys.argv = ["pv", "glossary", "createTerm", "--payload-file=" + tempFilePath]
                        logging.warning("Term will be imported: The Arguments are: %s "  %(sys.argv))
                        pv.main()
                else:
                    logging.error("no description found for the term %s" %(termValue))
                          

    logging.warning("Number of items parsed is: %s" %(len(res['body'])))
    # bulk update
    if(len(payload_file) > 0):
        fileName = str(randrange(6000)) + 'payload.json'
        tempFilePath = os.path.join(tempfile.gettempdir(), fileName)
        f = open(tempFilePath, "w+") 
        f.write(json.dumps(payload_file))
        f.flush()
        f.close
        sys.argv = ["pv", "glossary", "createTerms", "--payload-file=" + tempFilePath]
        logging.warning("Term will be imported: The Arguments are: %s "  %(sys.argv))
        pv.main()

        #update purview
        logging.warning("Terms will be imported into the catalog. The arguments are:")
        logging.warning(sys.argv)
        try:            
            f = io.StringIO()
            with redirect_stdout(f):
                pv.main()
            logging.warning("Results of the glossary update are:")
            logging.warning(f.getvalue())
            #add some logging for debugging purposes
            logging.warning("payload length is : %s" %(len(payload_file)))
        except AttributeError as error:
            # Output expected AttributeErrors.
            logging.error("failed to update Azure Purview because of an attribute error")
            logging.exception(error)
            logging.error(sys.exc_info()[0])
        except:
            logging.error("failed to update Azure Purview")
            logging.error(sys.exc_info()[0])
            logging.error("Results of the glossary update are:")
            logging.error(f.getvalue())
            #add some logging for debugging purposes
            logging.warning("payload length is : %s" %(len(payload_file)))
            logging.exception("The exception is:")
