from flask import jsonify
from .service import SportService

class SportEndpoints:
    def __init__(self, db_engine):
        self.service = SportService(db_engine)

    # GET /api/sports
    def get_sports(self):
        try:
            sports = self.service.list_sports()
            return jsonify(sports), 200
        except Exception:
            return jsonify({"message": "Failed to get sports"}), 500
