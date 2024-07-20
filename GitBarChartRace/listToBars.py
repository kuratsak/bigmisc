import sys
from utils import makeBarCharts
import os

def main(argv):
    if len(argv) != 3:
        print("usage: {} [input lines path] [output bar charts path]\n\nhad:\n{}".format(os.path.basename(argv[0]), repr(argv)))
        return -1
    
    makeBarCharts(argv[1], argv[2])
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))