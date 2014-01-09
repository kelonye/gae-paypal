import os
import sys
import yaml
from datetime import datetime, date, tzinfo, timedelta
from google.appengine.ext import ndb
from google.appengine.ext import deferred
from google.appengine.api import urlfetch

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), 'lib')
))

import lib as paypal

with open('conf.yml', 'r') as f:
    conf = yaml.load(f)

paypal.user = conf['facilitator']
paypal.password = conf['password']
paypal.signature = conf['signature']
