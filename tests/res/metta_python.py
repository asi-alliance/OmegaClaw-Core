import pathlib
import sys
import os

PETTA_PATH = pathlib.Path(os.environ.get("PETTA_PATH"))
if PETTA_PATH:
    PETTA_PYTHON_PATH = PETTA_PATH.joinpath("python")
    if str(PETTA_PYTHON_PATH) not in sys.path:
        sys.path.append(str(PETTA_PYTHON_PATH))

import petta

metta = petta.PeTTa(verbose=True, petta_path=PETTA_PATH)

def python_metta(arg):
    global metta
    rc = metta.process_metta_string(f"!(metta_func {arg})")
    return rc[0]
