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
from .models import db, User, Exam, ExamRecording, ExamWarning
from .services.misc import generate_exam_code, confirm_examiner, InvalidPassphrase
import jwt
import json
import math

api = Blueprint('api', __name__)

@api.route('/')
def index():
    response = { 'Status': "API is up and running!" }
    return make_response(jsonify(response), 200)


@api.route('/register', methods=('POST',))
def register():
    try:
        data = request.get_json()
        user = User(**data)
        if data.get('examiner_passphrase'):
            is_examiner = confirm_examiner(data['examiner_passphrase'])
            if not is_examiner:
                raise InvalidPassphrase()
            user.is_examiner = True
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500
    except InvalidPassphrase as e:
        return jsonify({ 'message': e.args }), 400


@api.route('/login', methods=('POST',))
def login():
    data = request.get_json()
    user = User.authenticate(**data)

    if not user:
        return jsonify({ 'message': 'Invalid credentials', 'authenticated': False }), 401

    token = jwt.encode({
        'sub': user.email,
        'iat':str(datetime.utcnow()),
        'exp': str(datetime.utcnow() + timedelta(minutes=30))},
        current_app.config['SECRET_KEY'])
    user_id = data['user_id']
    is_admin = User.query.filter_by(user_id=data['user_id']).first().is_admin
    return jsonify({ 'user_id': user_id , 'is_admin': is_admin, 'token': token.decode('UTF-8') }), 200

@api.route('/examiner/exam/create', methods=('POST',))
def create_exam():
    try:
        data = request.get_json()
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
    except exc.SQLAlchemyError as e:
        #db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam', methods=('GET',))
def get_exam():
    try:
        # Gets exam by exam_id or login_code if specified or gets all
        exam_id = request.args.get('exam_id', default=-1, type=int)
        login_code = request.args.get('login_code', default='null')

        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        results = None
        if exam_id == -1 and login_code == 'null':
            results = Exam.query.all()
        else:
            if exam_id != -1:
                results = Exam.query.filter_by(exam_id=exam_id).first()
            elif login_code != 'null':
                results = Exam.query.filter_by(login_code=login_code).first()
            if results is None:
                return jsonify({'message':'Exam not found'}), 404

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
    try:
        data = request.get_json()
        examRecording = ExamRecording(**data)
        db.session.add(examRecording)
        db.session.commit()
        return jsonify(examRecording.to_dict()), 201
    except exc.SQLAlchemyError as e:
        #db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examinee/exam_recording', methods=('GET',))
def get_exam_recording():
    """
    Gets exam recordings - can filter by user_id, exam_id. Returned results are limited by results_length and page_number.
    """
    try:
        # Obtains parameters
        user_id = request.args.get('user_id', default=0, type=int)
        exam_id = request.args.get('exam_id', default=0, type=int)
        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        # Checks for invalid page_number / results_length
        if page_number < 1:
            page_number = 1
        if results_length < 1 or results_length > 100:
            results_length = 25
        
        results_end_index = page_number*results_length

        if user_id and exam_id:
            # If user_id and exam_id are present, find the specific exam recording
            results = ExamRecording.query.filter_by(user_id=user_id, exam_id=exam_id).first()
        elif exam_id:
            # If just exam_id is present, find the exam recordings associated with exam_id
            results = ExamRecording.query.filter_by(user_id=user_id, exam_id=exam_id).order_by(ExamRecording.time_started.desc()).all()
        elif user_id:
            # If just user_id is present, find the exam recordings associated with user_id
            results = ExamRecording.query.filter_by(user_id=user_id).order_by(ExamRecording.time_started.desc()).all()
        else:
            # Else get all exam recordings
            results = ExamRecording.query.order_by(ExamRecording.time_started.desc()).all()

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
    try:
        
        # Gets action, either start or end
        action = request.args.get('action', default='').lower()
        
        data = request.json()
        # Preliminary checks
        if not data.get('exam_recording_id'):
            return jsonify({'message':'No exam_recording_id included in payload'}), 404
        exam_recording_id = data['exam_recording_id']
        exam_recording = ExamRecording.query.get(exam_recording_id)
        if exam_recording is None:
            return jsonify({'message':'Exam recording with exam_recording_id {} not found'.format(exam_recording_id)}), 404
        
        # If start, start the exam recording, if end, end exam recording and save chanegs
        if action == 'start':
            exam_recording.time_started = datetime.utcnow()
        elif action == 'end':
            exam_recording.time_ended = datetime.utcnow()
        else:
            return jsonify({'message':'Include parameter action: start, end'}), 400
        
        db.session.commit()
        
        return jsonify({'message':'Exam recording has '+action+'ed for user_id {}'.format(exam_recording.user_id)}), 200
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_recording/delete/<int:user_id>/<int:exam_id>', methods=('DELETE',))
def delete_exam_recording(user_id, exam_id): 
    try:
        # try get existing exam recording
        # check if we're allowed to delete it
        # if yes,
        # return successful message
        return '', 204
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning/create', methods=('POST',))
def create_exam_warning():
    try:
        data = request.get_json()
        examWarning = ExamWarning(**data)
        print(examWarning.to_dict())
        '''
        db.session.add(examWarning)
        db.session.commit()
        '''
        return '', 201
    except exc.SQLAlchemyError as e:
        #db.session.rollback()
        return jsonify({ 'message': e.args }), 500

@api.route('/examiner/exam_warning', methods=('GET',))
def get_exam_warning():
    try:
        exam_warning_id = request.args.get('exam_warning_id', default=-1, type=int)
        if exam_warning_id==-1:
            return jsonify({ 'message': 'Parameter exam_warning_id is required' }), 404

        exam_warning = ExamWarning.query.get('exam_warning_id')
        if exam_warning is None:
            return jsonify({ 'message':'Exam warning with exam_warning_id {} not found'.format(exam_warning_id)}), 404

        return jsonify(exam_warning.to_dict()), 200
    except exc.SQLAlchemyError as e:
        #db.session.rollback()
        return jsonify({ 'message': e.args }), 500
        
    
@api.route('/examiner/exam_warning/update', methods=('POST',))
def update_exam_warning(): #arpita to do
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
    try:
        # Potential parameters to filter by
        user_id = request.args.get('user_id', default=-1, type=int)
        exam_id = request.args.get('exam_id', default=-1, type=int)
        in_progress = request.args.get('in_progress', default=None, type=bool)
        #period_start = request.args.get('period_start', default=None, type=toDate)
        #period_end = request.args.get('period_end', default=None, type=datetime)
        has_warnings = request.args.get('has_warnings', default=None, type=bool)

        page_number = request.args.get('page_number', default=1, type=int)
        results_length = request.args.get('results_length', default=25, type=int)

        

        # Base query
        results = db.session.query(
            User, ExamRecording, Exam, ExamWarning
            ).filter(
                User.user_id == ExamRecording.user_id
            ).filter(
                ExamRecording.exam_id == Exam.exam_id
            ).filter(
                ExamRecording.exam_recording_id == ExamWarning.exam_recording_id
            )
        
        if user_id != -1:
            results = results.filter_by(User.user_id==user_id)
        if exam_id != -1:
            results = results.filter_by(Exam.exam_id==exam_id)
        '''
        if in_progress is not None:
            if in_progress:
                results = results.filter_by(ExamRecording.time_started < datetime.utcnow() and ExamRecording.time_ended is None)
            else:
                results = results.filter_by(ExamRecording.time_ended is not None)
        if has_warnings is not None:
            if has_warnings:
                results = results.filter_by(ExamWarning.exam_warning_id is not None)
            else:
                results = results.filter_by(ExamWarning.exam_warning_id is None)
        
        if period_start:
            results = results.filter_by(ExamRecording.time_started > period_start)
        if period_end:
            results = results.filter_by(ExamRecording.time_ended < period_end)
        '''
        results_end_index = page_number*results_length
        total_pages = math.ceil(len(results)/results_length)
        results = results[results_end_index - results_length:results_end_index]
        return_payload = [[r[0].to_dict(), r[1].to_dict(), r[2].to_dict()] for r in results]

        return jsonify(return_payload), 200
    except exc.SQLAlchemyError as e:
        #db.session.rollback()
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
