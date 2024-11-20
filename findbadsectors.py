'''
Copy a file to new copy on same disk, replacing bad sectors (unreadable) with readable fillers

Helpful for example in large video files, to allow most of file to be played/read even with some broken sectors..
'''
import os

def sectorFix(name, dryrun=False):
    badSectorReplacer = (b'badsector_' * 4096)[:4096]

    outputFilename = '{}{}{}'.format(os.path.dirname(name), os.path.sep, 'fixed-' + os.path.basename(name))
    with open(name, 'rb') as fid, (open("NUL", 'wb') if dryrun else open(outputFilename, 'wb')) as fidOut:
        fid.seek(0, os.SEEK_END)
        eof = fid.tell()
        fid.seek(0)
        fixedSectors = []
        sectorCount = 0
        pos = fid.tell()

        while pos != eof:
            sectorCount+= 1
            try:
                data = fid.read(4096)
                if fidOut:
                    fidOut.write(data)
            except Exception as e:
              print('file {name} has bad sector at block {block}, tell:{tell}, exception:{ex}'.format(
                    name=name,block=pos/4096, tell=fid.tell(), ex=str(e)))
              fixedSectors.append(pos)
              fid.seek(pos + 4096)
              if fidOut:
                    fidOut.write(badSectorReplacer)

            pos = fid.tell()
    return sectorCount, len(fixedSectors)

def search(path):
    badFiles = []
    totalFiles = 0
    totalScannedSectors = 0
    totalBadSectors = 0
    for root, dirs, files in os.walk(path):
        path = root.split(os.sep)
        for filename in files:
            totalFiles += 1
            filePath = os.path.join(root, filename)
            fileSectors, fixedSectors = sectorFix(filePath, True)
            totalScannedSectors += fileSectors
            totalBadSectors += fixedSectors
            if fixedSectors:
                badFiles.append(filePath)

    print("\ncorrupted files:\n{}".format("\n".join(badFiles)))
    print("\nsummary:\ntotal {} bad files out of {}".format(len(badFiles), totalFiles))
    print("total {} bad sectors out of {}, one in {} is corrupted".format(totalBadSectors, totalScannedSectors, totalScannedSectors / totalBadSectors))


if __name__ == '__main__':
    from sys import argv
    if len(argv) == 2:
        sectorFix(argv[1])
    elif argv[1] == "--search":
        search(argv[2])
    else:
        print("usage: {} [--search] path\n* Without search will fix bad sectors in a file, with search will recursively scan and report bad sectors in the path")