import os

def setenv(key, value):
    os.environ[key] = value

def unsetenv(key_prefix):
    for key in os.environ.keys():
        if key.startswith(key_prefix):
            del os.environ[key]
