import os

def load_env():
    """
    A simple function to load key-value pairs from a .env file into environment variables.
    """
    # Get the absolute path of the current working directory
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current script
    file_path = os.path.join('/app', '.env')  # Build the path to the .env file in the app/ directory

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} file not found")

    with open(file_path, "r") as file:
        for line in file:
            # Strip whitespace and ignore comments/empty lines
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = map(str.strip, line.split("=", 1))
                os.environ[key] = value
