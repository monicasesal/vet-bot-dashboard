# Conecta la BD y exporta db

import os
from pymongo import MongoClient
import ssl
from dotenv import load_dotenv

load_dotenv()

cliente = MongoClient(os.getenv("MONGO_URI"), tls=True, tlsAllowInvalidCertificates=True)

db = cliente["vetbot_db"]