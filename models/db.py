from pymongo import MongoClient

try:
    from mainconfig import MONGO_URL
except Exception as e:
    MONGO_URL = 'mongodb://localhost:27017/'


mongoClient = MongoClient(MONGO_URL)
db = mongoClient['report']

# createIndex https://velopert.com/560
db.mac.create_index([('date', 1), ('mac', 1)])