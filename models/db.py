from pymongo import MongoClient
from bson.objectid import ObjectId
# https://stackoverflow.com/questions/7846001/what-is-the-correct-way-to-query-mongodb-for-id-using-string-by-using-python

try:
    from mainconfig import MONGO_URL
except Exception as e:
    MONGO_URL = 'mongodb://localhost:27017/'


mongoClient = MongoClient(MONGO_URL)
db = mongoClient['report']

# createIndex https://velopert.com/560
db.mac.create_index([('date', 1), ('mac', 1)])


class BasicModel:
    def __init__(self, model):
        self.collection = db[model]

    def get_by_id(self, _id=''):
        try:
            data = self.collection.find_one({'_id': ObjectId(_id)})
        except Exception as e:
            data = None
            print(e)
        return data


