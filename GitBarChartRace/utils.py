def weightCounts(a):
    a = a if isinstance(a, list) else a.split('\n')
    from collections import Counter
    from tqdm import tqdm as tq
    c = Counter()
    [c.update({i[i.find(' ')+1:] : int(i[:i.find(' ')])}) for i in tq(a)]
    print('{}\ntotal:{}'.format('\n'.join([str(i) for i in sorted(c.items(), key=lambda k: k[1]) if i[1] > 0][-30:]), sum(i[1] for i in c.items())))

    return c

def counts(a):
    a = a if isinstance(a, list) else a.split('\n')
    b = ['1 ' + i for i in a]
    return weightCounts(b)

CLEANUP_AUTHORS = [i.lower() for i in [
'Cloud User',
'Cyber Author',
]]

def isInteresting(author):
    return all(i not in author.lower() for i in CLEANUP_AUTHORS)

def makeBarCharts(inputCsv, outputCsv, dateColumn=0, authorColumn=1, hashColumn=2, countsColumn=3, targetColumn=4, maximumLines=600):
    import csv
    from collections import defaultdict
    from tqdm import tqdm as tq
    # Read the input file

    #files, insertions, deletions
    defaultStats = [0, 0, 0]
    
    with open(inputCsv, 'rt', encoding='latin1') as infile:
        reader = csv.reader(infile)
        data = []
        for line in tq(list(reader)):
            if len(line) == 0:
                pass
            elif line[0].startswith('20'):
                data.append(line[:countsColumn] + defaultStats + line[countsColumn:])
            elif 'files changed' in line[0] or 'file changed' in line[0]:
                stats = [int(i.strip().split()[0]) for i in line]
                
                # remove deletions from insertion count
                if len(stats) == 3:
                    stats[1] = max(100, stats[1] - stats[2])

                # ignore giant generated shit or unprofessional commits
                stats = [min(i, 5000) for i in stats]

                data[-1][countsColumn:countsColumn+len(stats)] = stats
            else:
                raise Exception('unknown line: {}'.format(line))

    # data cleanup (duplicates and unsanitized data)
    data = sorted(tq(data), key=lambda k: repr(k))
    uniqueItems = []
    lastItem = None
    for ind, line in enumerate(data):
        # remove randomness from author names
        authorName = line[authorColumn].lower()\
            .replace('cr-','')\
            .replace('@cybereason.com','')\
            .replace('_', ' ')\
            .replace('.', ' ')\
            .title()
        line[authorColumn] = authorName

        # avoid duplicates
        if lastItem != line:
            uniqueItems.append(line)
            lastItem = line


    print('total lines:{}, unique lines:{}'.format(len(data), len(uniqueItems)))

    data = [item for item in uniqueItems if isInteresting(item[authorColumn])]

    print('\n'.join(repr(i) for i in data[:5]))

    
    # calculate unification to reach reasonable amount of lines
    totalLines = len(data)
    updatesPerStep = max(int(totalLines / maximumLines), 1)
    print('updates per step: {}'.format(updatesPerStep))

    # let leaders slowly go down
    updatesPerDecay = int(updatesPerStep*2)
    decayedLeaders = 30
    
    # Track unique values
    valueList = []
    
    # Initialize a dictionary to keep track of counts
    counts = defaultdict(int)

    outputData = []
    
    # Process each date and value
    for index,row in tq(enumerate(data)):
        # date,author,hash,insertions,deletions,title
        date, author = row[dateColumn], row[authorColumn]

        # add missing author
        if author not in counts:
            valueList += [author]

        #count with weight if necessary
        if targetColumn is not None:
            counts[author] += row[targetColumn]
        else:
            counts[author] += 1

        # only add every X lines (don't update for every 1 commit)
        if 0 == (index % updatesPerStep):
            dataRow = [date] + [counts[val] for val in valueList]
            outputData.append(dataRow)

        # decay old contributions
        if 0 == (index % updatesPerDecay):
            for item, count in sorted(counts.items(), key=lambda k: k[1])[-decayedLeaders:]:
                counts[item] = int((count+1) * 88 / 100)

    # some extra padding of final line at the end
    dataRow = [date] + [counts[val] for val in valueList]
    outputData.extend([dataRow]*20)
    
    # Initialize the output data with headers
    headers = [["date"] + valueList]

    # if filling is needed before:
    # lineLength = len(headers)
    # outputData = headers + [i + ([0]*(lineLength-len(i))) for i in tq(outputData)]
    outputData = headers + outputData

    # Write the output file
    with open(outputCsv, 'w', newline='') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(outputData)


# git commands:
# git log --since '01/01/2024' --until '04/09/2024' --oneline | wc -l
# git log --since '01/01/2024' --until '04/09/2024' --oneline
# git show <hash_value> --stat

# history line
# git log --reverse "--pretty=%as,%an,%h,%s" >sample.csv