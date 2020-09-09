import requests
import os, json
import random
from datetime import datetime, timedelta
from dateutil import parser

base_url = 'http://127.0.0.1:8000/api'
script_dir = os.path.dirname(__file__)

def populate(endpoint, file_name):
    data_file = os.path.join(script_dir, file_name)

    with open(data_file, 'r') as data:
        items = json.load(data)
        for item in items:
            print(item)
            r = requests.post(base_url+endpoint, json=item)
            print(r.status_code)

def populate_users():
    populate('/register', 'user_data.json')

def populate_exams():
    populate('/examiner/exam/create', 'exam_data.json')

def populate_exam_recordings():
    users_file = os.path.join(script_dir, 'user_data.json')
    exams_file = os.path.join(script_dir, 'exam_data.json')
    users_data = open(users_file, 'r')
    exams_data = open(exams_file, 'r')
    exams = json.load(exams_data)
    users = json.load(users_data)
    
    for user in users:
        random_exams = random.sample(range(0, len(exams)), 30)
        
    users_data.close()
    exams_data.close()

def add_end_datetime(minutes=0, days=0):
    if days:
        # Finds JSON file for exams with raw data i.e. no end_date, and datetime is overly precise
        data_file = os.path.join(script_dir, 'exam_data_raw.json')
        with open(data_file, 'r') as exam_data:
            exams = json.load(exam_data)
            new_file_location = os.path.join(script_dir, 'exam_data.json')
            with open(new_file_location, 'w') as new_file:
                for e in exams:
                    # Discards precision of datetime's minutes, seconds & microseconds and rounds to nearest half hour
                    start_date = parser.parse(e['start_date'])
                    discard = timedelta(minutes=start_date.minute%30, seconds=start_date.second, microseconds=start_date.microsecond )
                    start_date -= discard
                    if discard >= timedelta(minutes=15):
                        start_date += timedelta(minutes=30)
                    # Adds 10 days to start_date to form end_date
                    e['end_date'] = '{}'.format(start_date + timedelta(days=days))
                    e['start_date'] = '{}'.format(start_date)
                # Saves new JSON file
                json.dump(exams, new_file, indent="")
    elif minutes:
        # Finds JSON file for exam_recordings
        data_file = os.path.join(script_dir, 'exam_recordings_raw.json')
        with open(data_file, 'r') as exam_data:
            exams = json.load(exam_data)
            new_file_location = os.path.join(script_dir, 'exam_data.json')
            with open(new_file_location, 'w') as new_file:
                for e in exams:
                    start_date = parser.parse(e['start_date'])
                    e['end_date'] = '{}'.format(start_date + timedelta(days=days))
                json.dump(exams, new_file, indent="")

populate_exams()