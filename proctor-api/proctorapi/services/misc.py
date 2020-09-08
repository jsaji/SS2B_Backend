

def confirm_examiner(entered_passphrase):
    try:
        script_dir = os.path.dirname(__file__)
        file_path = os.path.join(script_dir, 'examiner_passphrase.txt')
        with open(file_path) as f:
            examiner_passphrase = f.read()
            return examiner_passphrase == entered_passphrase
    except FileNotFoundError as e:
        print(e.args)
        raise

class InvalidPassphrase(Exception):
    def __init__(self):
        super().__init__("Invalid examiner passphrase")