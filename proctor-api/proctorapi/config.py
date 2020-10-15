
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
    SQLALCHEMY_DATABASE_URI = ''
    FTP_DOMAIN = ''
    FTP_USER = ''
    FTP_PASSWD = ''
    SECRET_KEY = ''
    with open(file_path, "r") as conn_file:
        lines = conn_file.read().split('\n')
        SQLALCHEMY_DATABASE_URI = lines[0]
        FTP_DOMAIN = lines[1]
        FTP_USER = lines[2]
        FTP_PASSWD = lines[3]
        SECRET_KEY = lines[4]

    DEBUG = True
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    