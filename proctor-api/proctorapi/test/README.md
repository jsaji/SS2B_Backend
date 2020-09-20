# Test Stuff Folder

This folder contains test related scripts and data.

## How to use populate_db.py

NOTE: Make sure the desired db has the required schema and is empty.

Run the script and it will insert users and exams into the db. From these two, it generates exam recordings and exam warnings.
Exam recordings and exam warnings need to be generated because they rely on user_id and exam_id (foreign keys).