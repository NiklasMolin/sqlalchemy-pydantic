import os
from pathlib import Path
os.environ["PYTEST"] = "YES"

if Path("./validation.db").exists():
    os.remove(Path("./validation.db").absolute())
