"""
application.py
- creates a Flask app instance and registers the database object
"""

from flask import Flask
from flask_cors import CORS


def create_app(app_name='OBJECT_DETECTION_API'):
    app = Flask(app_name)
    CORS(app)
    app.config.from_object('objectdetection.config.BaseConfig')

    from objectdetection.api import api
    app.register_blueprint(api, url_prefix="/api")

    from objectdetection.models import db
    db.init_app(app)

    return app
