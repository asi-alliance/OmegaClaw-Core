!(import! &self ./res/metta_python.py)

(= (metta_func $x) $x)

!(test (py-call (metta_python.python_metta SomeSymbol)) SomeSymbol)
