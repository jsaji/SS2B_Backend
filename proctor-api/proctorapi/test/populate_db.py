import requests
import os, json
import random
from datetime import datetime, timedelta
from dateutil import parser

base_url = 'http://127.0.0.1:8000/api'
script_dir = os.path.dirname(__file__)

def create_json_file(data, new_file_name):
    data_file = os.path.join(script_dir, new_file_name)
    with open(data_file, 'w') as new_file:
        json.dump(data, new_file, indent="", default=str)
    print(data_file + ' successfully generated!')

def populate(endpoint, file_name):
    data_file = os.path.join(script_dir, file_name)

    with open(data_file, 'r') as data:
        items = json.load(data)
        total_items = len(items)
        for i, item in enumerate(items):
            r = requests.post(base_url+endpoint, json=item)
            if r.status_code != 201:
                print('An error occured: ' + r.json()['message'])
                break
            print('{0:.0%} of {1} rows added'.format(i/total_items, total_items), end='\r')
    print()

def populate_users():
    populate('/register', 'user_data.json')

def populate_exams():
    populate('/examiner/exam/create', 'exam_data.json')

def populate_exam_recordings(generate=True):
    if generate:
        generate_exam_recording_data()
    populate('/examinee/exam_recording/create', 'exam_recording_data.json')

def populate_exam_warnings(generate=True):
    if generate:
        generate_exam_warning_data()
    populate('/examiner/exam_warning/create', 'exam_warning_data.json')

def generate_exam_data(days=30):
    # Finds JSON file for exams with raw data i.e. no end_date, and datetime is overly precise
    data_file = os.path.join(script_dir, 'exam_data_raw.json')
    with open(data_file, 'r') as exam_data:
        exams = json.load(exam_data)
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
    create_json_file(exams, 'exam_data.json')

def generate_exam_recording_data():
    exam_recording_json_data = []
    params = {'results_length': 99}
    r1 = requests.get(base_url+'/examiner/exam', params=params)
    r2 = requests.get(base_url+'/examiner/examinee', params=params)
    exams = r1.json()['exams']
    users = r2.json()['users']
    current_datetime = datetime.utcnow()
    for exam in exams:
        number_of_users = random.randint(15, 30)
        random_users = random.sample(range(0, len(users)), number_of_users)
        for user_index in random_users:
            user = users[user_index]
            start_date = parser.parse(exam['start_date'])
            duration = parser.parse(exam['duration']).time()
            time_started, time_ended = generate_time_period(start_date, duration)
            if time_ended <= current_datetime:
                exam_recording = {'user_id':user['user_id'],
                                    'exam_id':exam['exam_id'],
                                    'time_started': time_started,
                                    'time_ended': time_ended}
                exam_recording_json_data.append(exam_recording)
    create_json_file(exam_recording_json_data, 'exam_recording_data.json')
            
def generate_time_period(start_date, duration):
    offset = [random.randint(1, 20), random.randint(1, 23), random.randint(1, 58), random.randint(1, 58)]
    duration_scale = [random.uniform(0.6, 1), random.uniform(0, 1)]
    time_started = start_date + timedelta(days=offset[0], hours=offset[1], minutes=offset[2], seconds=offset[3])
    time_ended = time_started + timedelta(hours=duration.hour*duration_scale[0], minutes=duration.minute*duration_scale[1])
    return time_started.replace(tzinfo=None), time_ended.replace(tzinfo=None, microsecond=0)

def generate_exam_warning_data():
    warning_descriptions = ['Used mobile phone during exam',
                            'Used books in closed book exam',
                            'Communicated with someone in the room during the exam',
                            'Used notes in closed book exam',
                            'Used calculator when it is not allowed',
                            'Used tablet during exam',
                            'Used an external laptop during exam']
    
    exam_warnings = []
    count = [0, 0, 0, 0]
    params = {'results_length': 50, 'page_number': 1}
    end = False
    while not end:
        r = requests.get(base_url+'/examinee/exam_recording', params=params)
        exam_recordings = r.json()['exam_recordings']
         
        total_exam_recordings = len(exam_recordings)

        for exam_recording in exam_recordings:
            exam_recording_id = exam_recording['exam_recording_id']
            time_started = parser.parse(exam_recording['time_started'])
            time_ended = parser.parse(exam_recording['time_ended'])
            time_range = time_ended - time_started
            number_of_warnings = random.choices([0,1,2,3], weights=(50, 25, 15, 10), k=1)[0]
            count[number_of_warnings] += 1
            for i in range(number_of_warnings):
                warning_time = (time_started + time_range/(3-i)).replace(tzinfo=None)
                description = warning_descriptions[random.randint(0, len(warning_descriptions)-1)]
                exam_warning = {'exam_recording_id':exam_recording_id,
                                'description':description,
                                'warning_time':warning_time}
                exam_warnings.append(exam_warning)

        params['page_number'] += 1
        end = total_exam_recordings < params['results_length'] 
    
    print('Created {0} with 0 warnings, {1} with 1 warning, {2} with 2 warnings, {3} with 3 warnings'.format(*count))
    print('Total: {0} no warnings, {1} with warnings'.format(count[0], sum(count)-count[0]))
    create_json_file(exam_warnings, 'exam_warning_data.json')

populate_users()
populate_exams()
populate_exam_recordings()
populate_exam_warnings()