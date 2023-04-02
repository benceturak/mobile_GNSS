import sys, os
#sys.path.append(os.path.join(os.path.dirname(os.path.dirname(sys.path[0])), 'UBXParser', 'src'))
sys.path.append('../')
from mobile_GNSS.common import config
sys.path.append(config.importRoot)
print(sys.path)
from UBXParser.src import UBXParser
#from UBXparser import UBXparser

print("OK")
