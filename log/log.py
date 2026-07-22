import sys
import logging


logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def bot_log(msg: str):
    logging.log(level=logging.INFO, msg=msg)