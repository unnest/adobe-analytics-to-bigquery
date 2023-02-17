import logging
from typing import Dict
from import_adobe_analytics.main import cloud_handler

logging.basicConfig(level=logging.INFO)


data: Dict = {}
context: Dict = {}

cloud_handler(data)
