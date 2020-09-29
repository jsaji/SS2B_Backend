
"""
    config.py
    - settings for the flask application object
"""


class BaseConfig(object):
    # ENV VARIABLES    
    db_link = "mysql://dronegp_ss2b:8PR7FThX@115.70.228.70:3306/dronegp_ses2b"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = db_link
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = "dd02dbe50eb41792067d9d650cd3ba58df0c90c6466ccea7"
    