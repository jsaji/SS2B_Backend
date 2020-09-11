"""
api.py
- provides the API endpoints for consuming and producing
  REST requests and responses
"""
from flask import Blueprint, jsonify, request, make_response, current_app, render_template, Response
from flask_cors import CORS, cross_origin
from datetime import datetime, timedelta
from sqlalchemy import exc
from functools import wraps
from PIL import Image
from .models import db, User
import cv2
import jwt
import os
import numpy
import pickle
import face_recognition

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
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201
    except exc.SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({ 'message': e.args }), 500


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
    user_id = User.query.filter_by(user_id=data['user_id']).first().user_id
    confirm_examiner = User.query.filter_by(user_id=data['user_id']).first().confirm_examiner
    return jsonify({ 'user_id': user_id , 'confirm_examiner': confirm_examiner, 'token': token.decode('UTF-8') }), 200


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
            user = User.query.filter_by(user_id=data['sub']).first()
            if not user:
                raise RuntimeError('User not found')
            return f(user, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify(expired_msg), 401 # 401 is Unauthorized HTTP status code
        except (jwt.InvalidTokenError, Exception) as e:
            print(e)
            return jsonify(invalid_msg), 401

    return _verify

@api.route('face_authentication', methods=('POST',))
def face_authentication():
    image = request.files["image"]
    user_id = request.form["user_id"]
    image_name = image.filename
    image.save(os.path.join(os.getcwd(), image_name))
    image1 = face_recognition.load_image_file(image_name)
    face_local1 = face_recognition.face_locations(image1)
    image1_encode = face_recognition.face_encodings(image1, face_local1) [0]

    for root, dirs, files in os.walk('images/' + str(user_id)):
        for file in files:
            if file.endswith("png") or file.endswith("jpg"):
                path = os.path.join(root, file)
                image2 = face_recognition.load_image_file(path)
                image2_encode = face_recognition.face_encodings(image2) [0]

                result = face_recognition.compare_faces([image1_encode], image2_encode)

                if result[0]:
                    os.remove(image_name)
                    return jsonify({'user_id': user_id, 'positive_id': True}), 200

    os.remove(image_name)
    return jsonify({'message': 'Student not found', 'positive_id': False}), 500