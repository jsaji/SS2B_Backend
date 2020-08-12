# UTSProctor - UTS Software Studio 2B 2020 - Group 12

UTSProctor is a Flask API for handling user authentication and proctoring functionality.

## Dev Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install all dependencies required for development using the `requirements.txt` file in the project's root folder:

```bash
pip install -r requirements.txt
```
## Connecting to the live db
Download db_link.txt from 41096_SPR_Wednesday/W12/Files and place in proctor-api/proctorapi
It is already included in .gitignore but please be mindful and DO NOT commit this file to a public github repo.

## Running the API locally
Execute the following bash command from the project root folder to start the API server on `localhost:5000/api/`. Note you need to have Python and all dependencies installed first.
```bash
python appserver.py
```
 

## Making database migrations using SQLAlchemy ORM
Create an initial migration file to translate the classes in models.py to SQL that will generate corresponding tables
```bash
python manage.py db migrate
```
Run the migration to upgrade the database with the tables described in the prior step
```bash
python manage.py db upgrade
```

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

Please make sure to update tests as appropriate.

## License
[MIT](https://choosealicense.com/licenses/mit/)
