import logging
import sys
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, '/home/username/webhook/')
from app import app as application
