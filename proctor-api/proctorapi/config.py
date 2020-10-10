
"""
    config.py
    - settings for the flask application object
"""
import os

class BaseConfig(object):
    # ENV VARIABLES
    # When running from cmd/powershell/bash, run from the root directory above proctor-api
    script_dir = os.path.dirname(__file__)
    file_path = os.path.join(script_dir, 'db_link.txt')
    f = open(file_path,"r")
    db_link = f.read()
    f.close() 
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = db_link
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = "dd02dbe50eb41792067d9d650cd3ba58df0c90c6466ccea7"
    