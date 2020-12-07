import os

def read(name):
    with open(name, 'rb') as fid:
        return fid.read()

def write(name, data):
    with open(name, "wb") as fid:
        fid.write(data)

WINDOW = 128
DELIMITER = '\x05'

BACKUP_NAME = 'sh.mcd.specialbak'

COUNTER_FINISHED = 'ZBIIMKHNON'

def main():
    saveat = '{}\\AppData\\LocalLow\\SUPERHOT_Team\\SHMCD'.format(os.environ['userprofile'])
    print 'assuming superhot save dir at {}'.format(saveat)
    os.chdir(saveat)
    d = read('sh.mcd')
    print 'backing up sh.mcd into {}'.format(BACKUP_NAME)
    write(BACKUP_NAME, d)
    
    #method No. 1
    i = len(d)-WINDOW
    while i > 0:
        upperBlob = d[i:i+WINDOW]
        if (upperBlob.isalpha() and upperBlob.isupper()):
            break
        i -= 1

    if i > 0:
        print 'found blob upper text {}'.format(d[i:i+WINDOW])
        i += WINDOW

    #method 2
    elif i == 0:
        i = d.rfind('JTAN')

    else:
        print 'wtf? i is negative? i: {} len(d): {}'.format(i, len(d))

    endOfUPPERTEXT = i

    lengthFix = d.find(DELIMITER, endOfUPPERTEXT)
    start = d.find('ZB', lengthFix)
    end = d.find(DELIMITER, start)
    dn = d[:start] + COUNTER_FINISHED + d[end:]

    print 'string before: {}'.format(repr(d[start-1:end+1]))
    print 'string after:  {}'.format(repr(dn[start-1:end+1 + len(dn) - len(d)]))

    print 'positions: start {} end {} lengthFix {} endOfUPPERTEXT {}'.format(start, end, lengthFix, endOfUPPERTEXT)

    b = bytearray(dn)
    print 'fixing length: ', len(dn) - len(d)
    b[lengthFix] += len(dn) - len(d)
    write('sh.mcd', b)
    os.system('pause')

if __name__ == '__main__':
    main()