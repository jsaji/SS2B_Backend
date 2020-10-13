"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""
from flask import Blueprint, jsonify, request, make_response, current_app, render_template, Response
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from werkzeug.datastructures import FileStorage
from urllib3.exceptions import MaxRetryError
import requests
from dateutil import parser
from sqlalchemy import exc, func
from functools import wraps
from .models import db, User, Role, UserRoles, Exam, ExamRecording, ExamWarning, required_fields
from .services.misc import generate_exam_code, confirm_examiner, pre_init_check, InvalidPassphrase, MissingModelFields, datetime_to_str, parse_datetime
import jwt
import traceback
import json
import math
from PIL import Image
import cv2
import os
import numpy
import pickle
import face_recognition

api = Blueprint('api', __name__)

ODAPI_URL = 'http://127.0.0.1:5000/'

MAX_WARNING_COUNT = 3

@api.route('/')
def index():
    """
    API health check
    """
    response = { 'Status': "API is up and running!" }
    return make_response(jsonify(response), 200)

@api.route('/register', methods=('POST',))
def register():
    """
    Register new users, examiners or examineers
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['user'], **data)
        user = User(**data)
        if data.get('examiner_passphrase'):
            verified_examiner = confirm_examiner(data['examiner_passphrase'])
            if not verified_examiner:
                raise InvalidPassphrase()
            user.is_examiner = True
            examiner_role = Role.query.filter_by(name='Examiner').first()
            user.roles.append(examiner_role)
        else:
            examinee_role = Role.query.filter_by(name='Examinee').first()
            user.roles.append(examinee_role)
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except (MissingModelFields, InvalidPassphrase) as e:
        return jsonify({ 'message': e.args }), 400
    except exc.IntegrityError as e:
        print(e)
        db.session.rollback()
        return jsonify({ 'message': 'User with id {} exists.'.format(data['user_id']) }), 409
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/login', methods=('POST',))
def login():
    """
    Login for existing users
    """
    data = request.get_json()
    user = User.authenticate(**data)

    if not user:
        return jsonify({ 'message': 'Invalid credentials', 'authenticated': False }), 401
    
    token = jwt.encode(
        {
        'exp': datetime.now() + timedelta(minutes=90),
        'iat': datetime.now(),
        'sub': user.user_id
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256')
    print(token)
    user_id = data['user_id']
    user = User.query.get(user_id)
    return jsonify({ 'user': user.to_dict(), 'token': token.decode('UTF-8') }), 200

@api.route('/examiner/exam/create', methods=('POST',))
def create_exam():
    """
    Creates new exam record
    """
    try:
        # decode token and check role for access control
        data = request.get_json()
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
    
        if examiner:
            # Checks if data has required fields - throws exception if not
            pre_init_check(required_fields['exam'], **data)

            code_found = False
            while not code_found:
                # Generates unique exam code until one is found that does not already exist
                potential_login_code = generate_exam_code()
                code_exists = Exam.query.filter_by(login_code=potential_login_code).first()
                if not code_exists:
                    data['login_code'] = potential_login_code
                    break
            exam = Exam(**data)
            if exam.start_date > exam.end_date:
                raise Exception('Exam end_date precedes Exam start_date')
            db.session.add(exam)
            db.session.commit()
            return jsonify(exam.to_dict()), 201
        
        return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam', methods=('GET',))
def get_exam():
    """
    Gets existing exam records, can be filtered with exam_id and login_code.
    Returned results are limited by results_length and page_number.
    """
    try:
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        user = is_user(user_id)
        if user:
            # Query to run
            exams = []
            if examiner:
                results_query = db.session.query(Exam, func.count(ExamRecording.exam_id)).\
                                outerjoin(ExamRecording, ExamRecording.exam_id==Exam.exam_id).\
                                group_by(Exam.exam_id)
                # Filters query results using request params
                results, next_page_exists = filter_results(results_query, Exam)
                
                for e, er_count in results:
                    exams.append({
                        **e.to_dict(),
                        'exam_recordings':er_count
                    })
            else:
                login_code = request.args.get('login_code', default=None)
                results = Exam.query.filter_by(login_code=login_code).\
                                    filter(Exam.start_date <= datetime.utcnow()).\
                                    filter(Exam.end_date >= datetime.utcnow()).all()
                next_page_exists = False
                for e in results:
                    exams.append({
                        **e.to_dict(),
                        'exam_recordings':0
                    })
            return jsonify({'exams':exams, 'next_page_exists': next_page_exists}), 200

        return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except (Exception, exc.SQLAlchemyError) as e:
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examiner/exam/update', methods=('POST',))
def update_exam():
    """
    Updates an existing exam record, dependent on whether it has already started
    """
    try:
        data = request.get_json()
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)

        if examiner:
            if not data.get('exam_id'):
                return jsonify({'message':'No exam_id included in payload'}), 400

            exam_id = data['exam_id']
            exam = Exam.query.get(exam_id)
            
            if exam is None:
                return jsonify({'message':'Exam with id {} not found'.format(exam_id)}), 404
            
            if exam.start_date > datetime.utcnow():
                if data.get('exam_name'):
                    exam.exam_name = data['exam_name']  
                if data.get('subject_id'):
                    exam.subject_id = data['subject_id']
                if data.get('start_date'):
                    start_date = parse_datetime(data['start_date'])
                    if start_date < datetime.utcnow():
                        raise Exception('Exam start_date has passed')
                    exam.start_date = start_date
                if data.get('end_date'):
                    end_date = parse_datetime(data['end_date'])
                    if end_date < datetime.utcnow():
                        raise Exception('Exam end_date has passed')
                    exam.end_date = end_date
                if data.get('duration'):
                    exam.duration = parse_datetime(data['duration']).time()
                if data.get('document_link'):
                    exam.document_link = data['document_link']

                if exam.start_date > exam.end_date:
                    raise Exception('Exam end_date precedes Exam start_date.')

                #db.session.commit()

                return jsonify(exam.to_dict()), 200

            raise Exception('Cannot update an Exam that has already started.')
        return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 400

@api.route('/examiner/exam/delete/<int:exam_id>', methods=('DELETE',))
def delete_exam(exam_id):
    """
    Deletes an existing exam record, dependent on whether it has already started
    """
    try:
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        
        if examiner:
            exam = Exam.query.get(exam_id)
            if exam:
                if exam.start_date > datetime.utcnow():
                    db.session.delete(exam)
                    db.session.commit()
                    return jsonify(exam.to_dict()), 200
                return jsonify({'message':['Exam with id {} cannot be deleted as it has already started.'.format(exam_id)]}), 405
            return jsonify({'message':['Exam with id {} could not be found'.format(exam_id)]}), 404
        else:
             return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording/create', methods=('POST',))
def create_exam_recording():
    """
    Creates new exam recording record
    """
    try:
        data = request.get_json()
        user_id = authenticate_token(request)
        user = is_user(user_id)

        if user:
            pre_init_check(required_fields['examrecording'], **data)
            # Checks for existing recordings or if exam has already ended - can be overrided to create new recording if authorised
            existing_recording = ExamRecording.query.filter_by(user_id=data['user_id'], exam_id=data['exam_id']).first()
            exam = Exam.query.get(data['exam_id'])
            if existing_recording:
                examiner = User.authenticate(**data)
                if not (examiner and examiner.is_examiner):
                    return jsonify({'message':("The exam has been previously attempted. "
                                                "Contact an administrator to override.")}), 401
            if not exam:
                return jsonify({'message':("The exam does not exist.")}), 401
            elif exam.end_date <= datetime.utcnow():
                return jsonify({'message':("The exam has already ended. "
                                            "Contact an administrator to override.")}), 401
            elif exam.start_date >= datetime.utcnow():
                return jsonify({'message':("The exam has not started. "
                                            "Contact an administrator to override.")}), 401
            
            # Creates exam recording
            exam_recording = ExamRecording(**data)
            exam_recording.time_started = datetime.utcnow()
            db.session.add(exam_recording)
            db.session.commit()
            return jsonify(exam_recording.to_dict()), 201
        
        return jsonify({'user_id': user_id, 'message': "access denied, invalid user." }), 403
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording', methods=('GET',))
def get_exam_recording():
    """
    Gets exam recordings, can be filtered by user_id, exam_id
    Returned results are limited by results_length and page_number.
    """
    try:
        # Users can get their own exam recordings, if they're an examiner they can get all of them
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        getting_own_results = is_self(user_id)

        if examiner or getting_own_results:
            results_query = db.session.query(User, Exam, ExamRecording, func.count(ExamWarning.exam_recording_id)).\
                            filter(User.user_id==ExamRecording.user_id).\
                            filter(Exam.exam_id==ExamRecording.exam_id).\
                            outerjoin(ExamWarning, ExamWarning.exam_recording_id==ExamRecording.exam_recording_id).\
                            group_by(ExamRecording.exam_recording_id)
                            
            results, next_page_exists = filter_results(results_query, ExamRecording)

            exam_recordings = []
            in_progress = request.args.get('in_progress', default=None, type=int)
            if in_progress is not None: in_progress = in_progress==1
            for u, e, er, ew_count in results:
                updated = False
                duration = e.duration
                # If exam recording has not ended (or does not have a time_ended value)
                if er.time_ended is None:
                    # Check if the time now has surpassed the latest possible finish time (recording start time + exam duration)
                    latest_finish_time = er.time_started + timedelta(hours=duration.hour, minutes=duration.minute)
                    if latest_finish_time <= datetime.utcnow():
                        # If so, set the value to latest possible time
                        updated = True
                        er.time_ended = latest_finish_time
                # Check so that when querying by in_progress = 1 / True, we dont include recordings that added time_ended to
                if not (updated and in_progress):
                    exam_recordings.append({
                        'exam_recording_id':er.exam_recording_id,
                        'user_id':u.user_id,
                        'first_name':u.first_name,
                        'last_name':u.last_name,
                        'exam_id':e.exam_id,
                        'exam_name':e.exam_name,
                        'login_code':e.login_code,
                        'duration':e.duration.strftime("%H:%M:%S"),
                        'subject_id':e.subject_id,
                        'time_started':datetime_to_str(er.time_started),
                        'time_ended':datetime_to_str(er.time_ended),
                        'video_link':er.video_link,
                        'warning_count':ew_count
                    })
            db.session.commit()

            return jsonify({'exam_recordings':exam_recordings, 'next_page_exists':next_page_exists}), 200
        
        return jsonify({'user_id': user_id, 'message': "access denied, invalid user." }), 403
    except (Exception, exc.SQLAlchemyError) as e:
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examinee/exam_recording/update', methods=('POST',))
def update_exam_recording():
    """
    Updates existing exam recording record, limited by the parameter action (end, video_link)
    """
    try:
        data = request.get_json()
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        getting_own_results = is_self(user_id)
        if examiner or getting_own_results:
            if not data.get('exam_recording_id') or not data.get('action'):
                return jsonify({'message':'No exam_recording_id / action included in payload'}), 400

            action = data['action']
            exam_recording_id = data['exam_recording_id']
            exam_recording = ExamRecording.query.get(exam_recording_id)
            if exam_recording is None:
                return jsonify({'message':'Exam recording with id {} not found'.format(exam_recording_id)}), 404
            
            if action == 'end':
                # If end, end exam recording
                if exam_recording.time_ended is not None:
                    return jsonify({'message':'Exam recording with id {} has already ended'.format(exam_recording_id)}), 400
                exam_recording.time_ended = datetime.utcnow()
            elif action == 'update_link':
                # If update video link, do so
                if not data.get('video_link'):
                    return jsonify({'message':'No video_link included in payload'}), 400
                exam_recording.video_link = data['video_link']
            else:
                return jsonify({'message':'Include parameter action: end, update_link'}), 400
            
            db.session.commit()
            
            return jsonify(exam_recording.to_dict()), 200
        
        return jsonify({'user_id': user_id, 'message': "access denied, invalid user." }), 403
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_recording/<int:exam_recording_id>', methods=('DELETE',))
def delete_exam_recording(exam_recording_id):
    """
    Deletes existing exam recording record.
    """
    try:
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        if examiner:
            exam_recording = ExamRecording.query.get(exam_recording_id)
            if exam_recording:
                db.session.delete(exam_recording)
                db.session.commit()
                return jsonify(exam_recording.to_dict()), 200
            return jsonify({'message':'Exam recording with id {} could not be found'.format(exam_recording_id)}), 404
        return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/create', methods=('POST',))
def create_exam_warning():
    """
    Creates new exam warning record
    """
    try:
        data = request.get_json()
        user_id = User.decode_auth_token(data['token'])
        examiner = is_examiner(user_id)

        if examiner:
            pre_init_check(required_fields['examwarning'], **data)
            prev_warnings = ExamWarning.query.filter_by(exam_recording_id=data['exam_recording_id']).all()
            exam_warning = ExamWarning(**data)
            db.session.add(exam_warning)
            # Checks how many previous warnings for the same exam
            if len(prev_warnings) == MAX_WARNING_COUNT-1:
                # If the new warning reaches the limit, end the exam if still in progress
                exam_recording = ExamRecording.query.get(data['exam_recording_id'])
                if exam_recording.time_ended is None:
                    exam_recording.time_ended = datetime.utcnow()
                    # End livestream somehow here
                
            db.session.commit()
            return jsonify({**exam_warning.to_dict(), 'warning_count':(len(prev_warnings)+1)}), 201
        
        return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning', methods=('GET',))
def get_exam_warning():
    """
    Gets existing exam warning records, can be filtered with exam_warning_id, exam_recording_id, warning_time.
    Returned results are limited by results_length and page_number.
    """
    try:
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        getting_own_results = is_self(user_id)
        if examiner or getting_own_results:
            results_query = db.session.query(User, Exam, ExamRecording, ExamWarning).\
                        filter(User.user_id==ExamRecording.user_id).\
                        filter(Exam.exam_id==ExamRecording.exam_id).\
                        filter(ExamWarning.exam_recording_id==ExamRecording.exam_recording_id).\
                        filter(User.is_examiner==False)

            # Filters results
            results, next_page_exists = filter_results(results_query, ExamWarning)

            payload = []
            
            for u, e, er, ew in results:
                payload.append({
                    'user_id':u.user_id,
                    'first_name':u.first_name,
                    'last_name':u.last_name,
                    'exam_id':e.exam_id,
                    'exam_name':e.exam_name,
                    'subject_id':e.subject_id,
                    'exam_recording_id':er.exam_recording_id,
                    'time_started':datetime_to_str(er.time_started),
                    'time_ended':datetime_to_str(er.time_ended),
                    'video_link':er.video_link,
                    'exam_warning_id':ew.exam_warning_id,
                    'warning_time':datetime_to_str(ew.warning_time),
                    'description':ew.description
                })

            return jsonify({'exam_warnings':payload, 'next_page_exists':next_page_exists}), 200
        else:
            return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except (Exception, exc.SQLAlchemyError) as e:
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/update', methods=('POST',))
def update_exam_warning():
    """
    Updates existing exam warning record.
    """
    try:
        data = request.get_json()
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)

        if examiner:
            if not data.get('exam_warning_id'):
                return jsonify({'message':'No exam_warning_id included in payload'}), 400

            exam_warning_id = data['exam_warning_id']
            exam_warning = ExamWarning.query.get(exam_warning_id)
            if exam_warning is None:
                return jsonify({'message':'Exam warning with id {} not found'.format(exam_warning_id)}), 404
            
            if data.get('description'): exam_warning.description = data['description']
            if data.get('warning_time'): exam_warning.warning_time = parser.parse(data['warning_time']).replace(tzinfo=None)
            db.session.commit()

            return jsonify(exam_warning.to_dict()), 200
        else:
            return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/delete/<int:exam_warning_id>', methods=('DELETE',))
def delete_exam_warning(exam_warning_id):
    """
    Deletes existing exam warning record.
    """
    try:
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)

        if examiner:
            exam_warning = ExamWarning.query.get(exam_warning_id)
            if exam_warning:
                db.session.delete(exam_warning)
                db.session.commit()
                return jsonify(exam_warning.to_dict()), 200
            return jsonify({ 'message': 'Exam warning with id {} could not be found'.format(exam_warning_id)}), 404
        else:
            return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/examinee', methods=('GET',))
def get_examinee():
    """
    Gets existing user records, can be filtered with user_id, first_name and last_name.
    Returned results are limited by results_length and page_number.
    """
    try:
        user_id = authenticate_token(request)
        examiner = is_examiner(user_id)
        getting_own_results = is_self(user_id)
        if examiner or getting_own_results:
            results_query = db.session.query(User, func.count(ExamRecording.user_id)).\
                            outerjoin(ExamRecording, ExamRecording.user_id==User.user_id).\
                            group_by(User.user_id)

            results, next_page_exists = filter_results(results_query, User)
            users = []
            for u, er_count in results:
                users.append({
                    **u.to_dict(),
                    'exam_recordings':er_count
                })
            return jsonify({'users':users, 'next_page_exists':next_page_exists}), 200
        
        return jsonify({'user_id': user_id, 'message': ['access denied, not examiner']}), 403
    except (Exception, exc.SQLAlchemyError) as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/deskcheck', methods=('POST',))
def deskcheck():
    """
    Detects unallowed objects in an image (.png, .jpg, etc)
    and returns object classes, confidence levels and coordinates on the image
    """
    try:
        user_id = authenticate_token(request)
        user = is_user(user_id)

        if user:
            # Checks if image file is received
            if request.files.get('image'):
                # Image is of type FileStorage, so it can be read directly
                image = request.files['image']
                files = [('image', image.read())]
                # Sends request to ODAPI
                r = requests.post(ODAPI_URL+'detections', files=files)
                if r.status_code == 200:
                    # Return json of request to client
                    data = r.json()
                    return jsonify(data), 200
                raise Exception("Unsuccessful attempt to detect objects")
            return jsonify({ 'message': 'No image sent' }), 400
        
        return jsonify({'user_id': user_id, 'message': "access denied, invalid user." }), 403
    except (MaxRetryError, requests.ConnectionError, requests.ConnectTimeout) as e:
        return jsonify({ 'message': 'Could not connect to ODAPI.' }), 500
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/upload_face', methods=('POST',))
def upload_face():
    try:
        data = request.get_json()
        user_id = authenticate_token(request)
        user = is_user(user_id)

        if True or user:
            # Checks request has image and user_id
            if None in (request.files.get('image'), request.form.get('user_id')):
                return jsonify({'message':['No user_id / image included in payload']}), 400
            # Checks user has registered
            user_id = request.form["user_id"]
            if not is_user(user_id):
                return jsonify({'message':['User needs to be registered to upload image']}), 400
            # Creates image dir if not existing
            image = request.files["image"]
            image_name = image.filename
            if not os.path.isdir('images'):
                os.mkdir('images/')
            path = 'images/'+str(user_id)
            # Creates new folder for user if not existing
            if not os.path.isdir(path):
                os.mkdir(path)
            # Removes existing files within user folder then saves image
            for root, dirs, files in os.walk(path):
                for file in files:
                    os.remove(os.path.join(root, file))
            img = Image.open(image)
            img = img.convert('RGB')
            img.save(path+"/face.jpg")
            
            return jsonify({'message':'Face image for user {} uploaded successfully'.format(user_id)}), 200
        
        return jsonify({'user_id': user_id, 'message':['access denied, invalid user'] }), 403
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'message': e.args}), 500

@api.route('/examinee/face_authentication', methods=('POST',))
def face_authentication():
    try:
        data = request.get_json()
        user_id = authenticate_token(request)
        user = is_user(user_id)

        if user:        
            if None in (request.files.get('image'), request.form.get('user_id')):
                return jsonify({'message':['No user_id / image included in payload']}), 400
            image = request.files["image"]
            user_id = request.form["user_id"]
            image_name = image.filename
            image.save(os.path.join(os.getcwd(), image_name))
            image1 = face_recognition.load_image_file(image_name)
            face_local1 = face_recognition.face_locations(image1)
            positive_id = False
            if face_local1:
                image1_encode = face_recognition.face_encodings(image1, face_local1)[0]

                for root, dirs, files in os.walk('images/' + str(user_id)):
                    for file in files:
                        if file.endswith("png") or file.endswith("jpg"):
                            path = os.path.join(root, file)
                            image2 = face_recognition.load_image_file(path)
                            image2_encode = face_recognition.face_encodings(image2) [0]

                            result = face_recognition.compare_faces([image1_encode], image2_encode)
                            positive_id = bool(result[0])
                                
            os.remove(image_name)
            return jsonify({'user_id': user_id, 'positive_id': positive_id}), 200
        else:
            return jsonify({'user_id': user_id, 'message': ['access denied, invalid user.'] }), 403
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'message': e.args}), 500

def get_request_args():
    """
    Gets various request args
    """
    args = {}
    args['user_id'] = request.args.get('user_id', default=None, type=int)
    args['is_examiner'] = request.args.get('is_examiner', default=None, type=int)
    if args['is_examiner'] is not None: args['is_examiner'] = args['is_examiner']==1
    args['first_name'] = request.args.get('first_name', default=None)
    args['last_name'] = request.args.get('last_name', default=None)

    args['exam_warning_id'] = request.args.get('exam_warning_id', default=None, type=int)
    args['exam_recording_id'] = request.args.get('exam_recording_id', default=None, type=int)
    args['in_progress'] = request.args.get('in_progress', default=None, type=int)
    if args['in_progress'] is not None: args['in_progress'] = args['in_progress']==1
    args['exam_id'] = request.args.get('exam_id', default=None, type=int)
    args['subject_id'] = request.args.get('subject_id', default=None, type=int)
    args['login_code'] = request.args.get('login_code', default=None)
    args['exam_name'] = request.args.get('exam_name', default=None)

    args['warning_count'] = request.args.get('warning_count', default=None, type=int)
    args['min_warnings'] = request.args.get('min_warnings', default=None, type=int)
    args['max_warnings'] = request.args.get('max_warnings', default=None, type=int)

    args['period_start'] = request.args.get('period_start', default=timedelta(days=10))
    args['period_end'] = request.args.get('period_end', default=timedelta(days=10))
    if args['period_start'] == timedelta(days=10): args['period_start'] = None
    if args['period_end'] == timedelta(days=10): args['period_end'] = None
    args['order_by'] = request.args.get('order_by', default='default').lower()
    args['order'] = request.args.get('order', default='desc').lower()
    
    args['page_number'] = request.args.get('page_number', default=1, type=int)
    args['results_length'] = request.args.get('results_length', default=25, type=int)
    if args['page_number'] < 1: args['page_number'] = 1
    if args['results_length'] < 1: args['results_length'] = 1

    return args

def filter_results(results, main_class=None):
    """
    Filters results and orders them - takes in query and main_class to perform specific actions
    """
    # Gets request parameters/arguments
    args = get_request_args()
    # Big block of ifs to filter
    if args['user_id']: results = results.filter(User.user_id==args['user_id'])
    if args['first_name']: results = results.filter(User.first_name.startswith(args['first_name']))
    if args['last_name']: results = results.filter(User.last_name.startswith(args['last_name']))
    if args['is_examiner'] is not None: results = results.filter(User.is_examiner==args['is_examiner'])

    if args['exam_warning_id']: results = results.filter(ExamWarning.exam_warning_id==args['exam_warning_id'])
    if args['exam_recording_id']: results = results.filter(ExamRecording.exam_recording_id==args['exam_recording_id'])
    if args['subject_id']: results = results.filter(Exam.subject_id==args['subject_id'])
    if args['exam_name']: results = results.filter(Exam.exam_name.startswith(args['exam_name']))

    if main_class == ExamWarning:
        if args['period_start']: results = results.filter(ExamWarning.warning_time >= args['period_start'])
        if args['period_end']: results = results.filter(ExamWarning.warning_time <= args['period_end'])
        
        if args['order_by'] == 'something':
            pass
        else:
            if args['order'] == 'asc': results = results.order_by(ExamWarning.warning_time.asc())
            else: results = results.order_by(ExamWarning.warning_time.desc())

    elif main_class == ExamRecording:
        if args['exam_id']: results = results.filter(ExamRecording.exam_id==args['exam_id'])
        if args['warning_count']: results = results.having(func.count(ExamWarning.exam_recording_id)==args['warning_count'])
        if args['min_warnings']: results = results.having(func.count(ExamWarning.exam_recording_id)>=args['min_warnings'])
        if args['max_warnings']: results = results.having(func.count(ExamWarning.exam_recording_id)<=args['max_warnings'])
        if args['period_start']: results = results.filter(ExamRecording.time_started >= args['period_start'])
        if args['period_end']: results = results.filter(ExamRecording.time_ended <= args['period_end'])
        if args['in_progress']==1: results = results.filter(ExamRecording.time_ended == None)
        elif args['in_progress']==0: results = results.filter(ExamRecording.time_ended < datetime.utcnow())
        if args['order_by'] == 'time_ended':
            if args['order'] == 'asc': results = results.order_by(ExamRecording.time_ended.asc())
            else: results = results.order_by(ExamRecording.time_ended.desc())
        else:
            if args['order'] == 'asc': results = results.order_by(ExamRecording.time_started.asc())
            else: results = results.order_by(ExamRecording.time_started.desc())

    elif main_class == Exam:
        if args['exam_id']: results = results.filter(Exam.exam_id==args['exam_id'])
        if args['login_code']: results = results.filter(Exam.login_code.startswith(args['login_code']))
        if args['period_start']: results = results.filter(Exam.start_date >= args['period_start'])
        if args['period_end']: results = results.filter(Exam.end_date <= args['period_end'])
        if args['in_progress'] == 'true': results = results.filter(Exam.end_date >= datetime.utcnow(), Exam.start_date <= datetime.utcnow())
        elif args['in_progress'] == 'false': results = results.filter(Exam.end_date <= datetime.utcnow())
        if args['order_by'] == 'end_date':
            if args['order'] == 'asc': results = results.order_by(Exam.end_date.asc())
            else: results = results.order_by(Exam.start_date.desc())
        elif args['order_by'] == "exam_name":
            if args['order'] == 'asc': results = results.order_by(Exam.exam_name.asc())
            else: results = results.order_by(Exam.exam_name.desc())
        elif args['order_by'] == "subject_id":
            if args['order'] == 'asc': results = results.order_by(Exam.subject_id.asc())
            else: results = results.order_by(Exam.subject_id.desc())
        else:
            if args['order'] == 'asc': results = results.order_by(Exam.start_date.asc())
            else: results = results.order_by(Exam.start_date.desc())

    elif main_class == User:
        if args['order_by'] == 'first_name':
            if args['order'] == 'asc': results = results.order_by(User.first_name.asc())
            else: results = results.order_by(User.first_name.desc())
        elif args['order_by'] == 'last_name':
            if args['order'] == 'asc': results = results.order_by(User.last_name.asc())
            else: results = results.order_by(User.last_name.desc())
        else:
            if args['order'] == 'asc': results = results.order_by(User.user_id.asc())
            else: results = results.order_by(User.user_id.desc())

    # Calculates offset to limit the number of results returned
    offset = (args['page_number']-1)*args['results_length']
    results = results[offset:offset+args['results_length']+1]
    # Determines if next page exists, and deletes last extra row if it does
    next_page_exists = len(results) == args['results_length']+1
    if next_page_exists: del results[-1]

    return results, next_page_exists
    
def is_examiner(user_id):
    role_id = UserRoles.query.filter_by(user_id=user_id).value('role_id')
    return role_id == 1

def is_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return user is not None

def authenticate_token(request):
    try:
        token = request.headers.get('Authorization')
        #print(token)
        user_id = User.decode_auth_token(token)

        return user_id
    except Exception as e:
        #print(e)
        return jsonify({'message': e.args})
    
def is_self(user_id):
    """
    Checks if a user is getting their own results, returns true for auth
    """
    query_user_id = request.args.get('user_id', default=None, type=int)
    return user_id==query_user_id and user_id is not None