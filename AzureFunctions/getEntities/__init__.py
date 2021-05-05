import logging
import azure.functions as func
import sys
import importlib
from docopt import docopt
from purviewcli import __version__
from purviewcli.cli import cli as pv
import io
from contextlib import redirect_stdout
import json

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

    if search:
        
        logging.info(search)
        value = entitySearch(search)
        logging.info(value)
        #msg.set('{"message":"value"}')
        msg.set(value)
        return func.HttpResponse(f"The HTTP triggered function for {search} executed successfully.")

    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully, but no search criteria was supplied. Pass a search in the query string or in the request body for a response.",
             status_code=200
        )
