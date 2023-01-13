import sys

from django.conf import settings

# import lotus

# current_lotus = lotus
# og_path = sys.path.copy()
# sp_path = [s for s in sys.path if "site-package" in s][0]
# sys.path.insert(0, sp_path)
# del sys.modules["lotus"]
# import lotus

# sys.modules["lotus_python"] = lotus
# import lotus_python

# # del sys.modules["lotus"]
# sys.modules["lotus"] = current_lotus
# sys.path = og_path

# LOTUS_HOST = settings.LOTUS_HOST
# LOTUS_API_KEY = settings.LOTUS_API_KEY
# if LOTUS_HOST and LOTUS_API_KEY:
#     lotus_python.api_key = LOTUS_API_KEY
#     lotus_python.host = LOTUS_HOST
