# endpoints/sprt/sportEndpoints.py
from flask import request, jsonify
from endpoints.sport.sportModel import SportModel

class SportEndpoints:
    def __init__(self, db_engine):
        self.sportModel = SportModel(db_engine)

    # GET /api/sports
    def get_sports(self):
        try:
            sports = self.sportModel.get_sports()
            return jsonify(sports), 200
        except Exception as e:
            return jsonify({"message": "Failed to get sports"}), 500
