import os

def read(name):
    with open(name, 'rb') as fid:
        return fid.read()

def write(name, data):
    with open(name, "wb") as fid:
        fid.write(data)

BLOB_END = 'JTANKJTANKJTANKJTANH@TAN'
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
    
    lengthFix = d.find(DELIMITER, d.rfind(BLOB_END) + len(BLOB_END)) + 3
    start = d.find('ZB', lengthFix)
    end = d.find(DELIMITER, start)
    dn = d[:start] + COUNTER_FINISHED + d[end:]

    print 'string before: {}'.format(repr(d[start-1:end+1]))
    print 'string after:  {}'.format(repr(dn[start-1:end+1 + len(dn) - len(d)]))

    b = bytearray(dn)
    print 'fixing length: ', len(dn) - len(d)
    b[lengthFix] += len(dn) - len(d)
    write('sh.mcd', b)

if __name__ == '__main__':
    main()