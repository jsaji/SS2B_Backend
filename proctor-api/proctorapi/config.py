
"""
    config.py
    - settings for the flask application object
"""


class BaseConfig(object):
    
    f= open("proctor-api/db_link.txt","r")
    db_link = f.read()
    f.close()
    # NEED TO USE ENV VARIABLES HERE
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = db_link
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = "dd02dbe50eb41792067d9d650cd3ba58df0c90c6466ccea7"
    