"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""

from flask import Blueprint, jsonify, request, make_response, current_app
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from dateutil import parser
from sqlalchemy import exc
from functools import wraps
from .models import db, User, Exam, ExamRecording, ExamWarning, required_fields
from .services.misc import generate_exam_code, confirm_examiner, pre_init_check, InvalidPassphrase, MissingModelFields
import jwt
import json
import math

api = Blueprint('api', __name__)

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
            is_examiner = confirm_examiner(data['examiner_passphrase'])
            if not is_examiner:
                raise InvalidPassphrase()
            user.is_examiner = True
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except (MissingModelFields, InvalidPassphrase) as e:
        return jsonify({ 'message': e.args }), 400
    except exc.IntegrityError:
        db.session.rollback()
        return jsonify({ 'message': 'User with user_id {} exists.'.format(data['user_id']) }), 409
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

    token = jwt.encode({
        'sub': user.user_id,
        'iat':str(datetime.utcnow()),
        'exp': str(datetime.utcnow() + timedelta(minutes=30))},
        current_app.config['SECRET_KEY'])
    user_id = data['user_id']
    user = User.query.get(user_id)
    return jsonify({ 'user': user.to_dict(), 'token': token.decode('UTF-8') }), 200

@api.route('/examiner/exam/create', methods=('POST',))
def create_exam():
    """
    Creates new exam record
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['exam'], **data)
        code_found = False
        while not code_found:
            potential_login_code = generate_exam_code()
            code_exists = Exam.query.filter_by(login_code=potential_login_code).first()
            if not code_exists:
                data['login_code'] = potential_login_code
                break
        data['duration'] = parser.parse(data['duration']).time()
        exam = Exam(**data)
        db.session.add(exam)
        db.session.commit()
        return jsonify(exam.to_dict()), 201
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam', methods=('GET',))
def get_exam():
    """
    Gets existing exam records, can be filtered with exam_id and login_code.
    Returned results are limited by results_length and page_number.
    """
    try:
        # Gets exam by exam_id or login_code if specified or gets all
        exam_id = request.args.get('exam_id', default=None, type=int)
        login_code = request.args.get('login_code', default=None)
        subject_id = request.args.get('subject_id', default=None)
        exam_name = request.args.get('exam_name', default=None)
        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        if page_number < 1:
            page_number = 1
        if results_length < 1 or results_length > 100:
            results_length = 25
        
        results = Exam.query
        
        if exam_id:
            results = results.filter_by(exam_id=exam_id)
        if subject_id:
            results = results.filter_by(subject_id=subject_id)
        if login_code:
            results = results.filter(Exam.login_code.startswith(login_code))
        if exam_name:
            results = results.filter(Exam.exam_name.startswith(exam_name))
        
        results = results.all()

        # Calculates total number of pages of results
        results_end_index = page_number*results_length
        total_pages = math.ceil(len(results)/results_length)
        results = results[results_end_index-results_length:results_end_index]
        exam_dict = [r.to_dict() for r in results]
        payload = {'exams':exam_dict, 'total_pages': total_pages}

        return jsonify(payload), 200

    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examiner/exam/update', methods=('POST',))
def update_exam(): #arpita to do
    """
    Updates an existing exam record, dependent on whether it has already started
    """
    try:
        print("hola")
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(u.to_dict()), 200
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam/delete/<int:exam_id>', methods=('DELETE',))
def delete_exam(): #arpita to do
    """
    Deletes an existing exam record, dependent on whether it has already started
    """
    try:
        print("hola")
        # try get existing exam
        # check if we're allowed to delete it
        # if yes,
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording/create', methods=('POST',))
def create_exam_recording():
    """
    Creates new exam recording record
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['examrecording'], **data)
        examRecording = ExamRecording(**data)
        db.session.add(examRecording)
        db.session.commit()
        return jsonify(examRecording.to_dict()), 201
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording', methods=('GET',))
def get_exam_recording():
    """
    Gets exam recordings, can be filtered by user_id, exam_id
    Returned results are limited by results_length and page_number.
    """
    try:
        # Obtains parameters
        user_id = request.args.get('user_id', default=None, type=int)
        exam_id = request.args.get('exam_id', default=None, type=int)
        in_progress = request.args.get('in_progress', default=None, type=bool)
        period_start = request.args.get('period_start', default=timedelta(days=10))
        period_end = request.args.get('period_end', default=timedelta(days=10))
        if period_start == timedelta(days=10):
            period_start = None
        if period_end == timedelta(days=10):
            period_end = None
        
        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        # Checks for invalid page_number / results_length
        if page_number < 1:
            page_number = 1
        if results_length < 1 or results_length > 100:
            results_length = 25
        
        results_end_index = page_number*results_length

        results = ExamRecording.query
        if user_id and exam_id:
            # If user_id and exam_id are present, find the specific exam recording
            results = results.filter_by(user_id=user_id, exam_id=exam_id)
        if exam_id:
            # If just exam_id is present, find the exam recordings associated with exam_id
            results = results.filter_by(user_id=user_id, exam_id=exam_id).order_by(ExamRecording.time_started.desc())
        if user_id:
            # If just user_id is present, find the exam recordings associated with user_id
            results = results.filter_by(user_id=user_id).order_by(ExamRecording.time_started.desc())
        if in_progress is not None:
            # If in_progress is defined, get ones that are if true, or past ones if false
            if in_progress:
                results = results.filter(ExamRecording.time_ended is None)
            else:
                results = results.filter(ExamRecording.time_ended is not None)
        if period_start:
            results = results.filter(ExamRecording.time_started >= period_start)
        if period_end:
            results = results.filter(ExamRecording.time_ended <= period_end)

        results = results.order_by(ExamRecording.time_started.desc()).all()
        # Reduces number of results and serialises into string format for payload
        total_pages = math.ceil(len(results)/results_length)
        results = results[results_end_index - results_length:results_end_index]
        exam_recordings = [r.to_dict() for r in results]

        payload = {'exam_recordings':exam_recordings, 'total_pages':total_pages}
        return jsonify(payload), 200

    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    
@api.route('/examinee/exam_recording/update', methods=('POST',))
def update_exam_recording():
    """
    Updates existing exam recording record, limited by the parameter action (start, end, video_link)
    """
    try:
        
        # Gets action, either start or end
        action = request.args.get('action', default='').lower()
        
        data = request.json()
        # Preliminary checks
        if not data.get('exam_recording_id'):
            return jsonify({'message':'No exam_recording_id included in payload'}), 400
        
        exam_recording_id = data['exam_recording_id']
        exam_recording = ExamRecording.query.get(exam_recording_id)
        if exam_recording is None:
            return jsonify({'message':'Exam recording with exam_recording_id {} not found'.format(exam_recording_id)}), 404
        
        # If start, start the exam recording, if end, end exam recording and save chanegs
        if action == 'start':
            exam_recording.time_started = datetime.utcnow()
        elif action == 'end':
            exam_recording.time_ended = datetime.utcnow()
        elif action == 'video_link':
            if not data.get('video_link'):
                return jsonify({'message':'No video_link included in payload'}), 400
            exam_recording.video_link = data['video_link']
        else:
            return jsonify({'message':'Include parameter action: start, end'}), 400
        
        db.session.commit()
        
        return jsonify({'message':'Exam recording has '+action+'ed for user_id {}'.format(exam_recording.user_id)}), 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_recording/delete/<int:exam_recording_id>', methods=('DELETE',))
def delete_exam_recording(exam_recording_id):
    """
    Deletes existing exam recording record.
    """
    try:
        exam_recording = ExamRecording.query.get(exam_recording_id)
        if exam_recording:
            db.session.delete(exam_recording)
            db.session.commit()
            return '', 204
        return jsonify({'message':'Exam recording with id {} could not be found'}), 404
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/create', methods=('POST',))
def create_exam_warning():
    """
    Creates new exam warning record
    """
    try:
        data = request.get_json()
        pre_init_check(required_fields['examwarning'], **data)
        exam_warning = ExamWarning(**data)
        db.session.add(exam_warning)
        db.session.commit()
        return jsonify(exam_warning.to_dict()), 201
    except MissingModelFields as e:
        return jsonify({ 'message': e.args }), 400
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning', methods=('GET',))
def get_exam_warning():
    """
    Gets existing exam warning records, can be filtered with exam_warning_id, exam_recording_id, period_start and period_end.
    Returned results are limited by results_length and page_number.
    """
    try:
        exam_warning_id = request.args.get('exam_warning_id', default=None, type=int)
        exam_recording_id = request.args.get('exam_recording_id', default=None, type=int)
        period_start = request.args.get('period_start', default=timedelta(days=10))
        period_end = request.args.get('period_end', default=timedelta(days=10))
        
        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        if period_start == timedelta(days=10):
            period_start = None
        if period_end == timedelta(days=10):
            period_end = None

        if page_number < 1:
            page_number = 1
        if results_length < 1 or results_length > 100:
            results_length = 25
        
        results = ExamWarning.query
        if exam_warning_id:
            results = results.filter_by(exam_warning_id=exam_warning_id)
        if exam_recording_id:
            results = results.filter_by(exam_recording_id=exam_recording_id)
        if period_start:
            results = results.filter(ExamWarning.warning_time >= period_start)
        if period_end:
            results = results.filter(ExamWarning.warning_time <= period_end)

        results = results.all()
        results_end_index = page_number*results_length
        total_pages = math.ceil(len(results)/results_length)
        results = results[results_end_index-results_length:results_end_index]
        exam_warnings = [r.to_dict() for r in results]

        return jsonify({'exam_warnings':exam_warnings, 'total_pages':total_pages}), 200
    except exc.SQLAlchemyError as e:
        #db.session.rollback()
        return jsonify({ 'message': e.args }), 500
        
    
@api.route('/examiner/exam_warning/update', methods=('POST',))
def update_exam_warning(): #arpita to do
    """
    Updates existing exam warning record.
    """
    try:
        # try get data
        # find the existing model
        # return successful message
        # return jsonify(u.to_dict()), 200
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/delete', methods=('DELETE',))
def delete_exam_warning(): #arpita to do
    """
    Deletes existing exam warning record.
    """
    try:
        exam_warning_id = request.args.get('exam_warning_id', default=-1, type=int)
        if exam_warning_id==-1:
            return jsonify({ 'message': 'Parameter exam_warning_id is required' }), 404
        # try get existing exam recording
        # check if we're allowed to delete it
        # if yes,
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


@api.route('/examiner/examinee', methods=('GET',))
def get_examinee():
    """
    Gets existing user records, can be filtered with user_id, first_name and last_name.
    Returned results are limited by results_length and page_number.
    """
    try:
        # Potential parameters to filter by
        user_id = request.args.get('user_id', default=None, type=int)
        first_name = request.args.get('first_name', default=None)
        last_name = request.args.get('last_name', default=None)

        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        if page_number < 1:
            page_number = 1
        if results_length < 1 or results_length > 100:
            results_length = 25

        results = User.query
                
        if user_id:
            results = results.filter_by(user_id=user_id)
        if first_name:
            results = results.filter(User.first_name.startswith(first_name))
        if last_name:
            results = results.filter(User.last_name.startswith(last_name))
        results = results.all()

        results_end_index = page_number*results_length
        total_pages = math.ceil(len(results)/results_length)
        results = results[results_end_index - results_length:results_end_index]
        users = [r.to_dict() for r in results]
        return jsonify({'users':users, 'total_pages':total_pages}), 200
    except exc.SQLAlchemyError as e:
        return jsonify({ 'message': e.args }), 500


# This is a decorator function which will be used to protect authentication-sensitive API endpoints
def token_required(f):
    @wraps(f)
    def _verify(*args, **kwargs):
        auth_headers = request.headers.get('Authorization', '').split()

        invalid_msg = {
            'message': 'Invalid token. Registeration and / or authentication required',
            'authenticated': False
        }
        expired_msg = {
            'message': 'Expired token. Reauthentication required.',
            'authenticated': False
        }

        if len(auth_headers) != 2:
            return jsonify(invalid_msg), 401

        try:
            token = auth_headers[1]
            data = jwt.decode(token, current_app.config['SECRET_KEY'])
            user = User.query.filter_by(email=data['sub']).first()
            if not user:
                raise RuntimeError('User not found')
            return f(user, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify(expired_msg), 401 # 401 is Unauthorized HTTP status code
        except (jwt.InvalidTokenError, Exception) as e:
            print(e)
            return jsonify(invalid_msg), 401

    return _verify
