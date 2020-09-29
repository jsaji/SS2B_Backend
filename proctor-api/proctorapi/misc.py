import os
import random
import string
from datetime import datetime
from dateutil import parser

def parse_datetime(input_var):
    if isinstance(input_var, str):
        return parser.parse(input_var).replace(tzinfo=None)
    elif input_var is None:
        return input_var
    return input_var.replace(tzinfo=None)

def datetime_to_str(datetime_obj):
    if datetime_obj:
        return datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
    return None

charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!0123456789'

def pre_init_check(required_fields, **kwargs):
        missing_fields = []
        for field in required_fields:
            if not kwargs.get(field):
                missing_fields.append(field)
        if len(missing_fields):
            raise MissingModelFields(missing_fields)

def generate_exam_code(allowed_chars=charset, str_size=12):
    return ''.join(random.choice(allowed_chars) for x in range(str_size))

def confirm_examiner(entered_passphrase):
    try:
        # script_dir = os.path.dirname(__file__)
        # file_path = os.path.join(script_dir, 'examiner_passphrase.txt')
        # with open(file_path, 'r') as f:
            # examiner_passphrase = f.read()
        examiner_passphrase = "test123"
        return examiner_passphrase == entered_passphrase
    except FileNotFoundError as e:
        print(e.args)
        raise

class InvalidPassphrase(Exception):
    def __init__(self):
        super().__init__("Invalid examiner passphrase")

class MissingModelFields(Exception):
    def __init__(self, field):
        super().__init__("The model is missing {} field(s)".format(field))