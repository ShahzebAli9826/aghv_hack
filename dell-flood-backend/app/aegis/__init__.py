import sys
import os
aegis_dir = os.path.dirname(os.path.abspath(__file__))
if aegis_dir not in sys.path:
    sys.path.insert(0, aegis_dir)
