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

def makeBarCharts(inputCsv, outputCsv, dateColumn=0, valueColumn=1, maximumLines=340):
    import csv
    from collections import defaultdict
    from tqdm import tqdm as tq
    # Read the input file
    
    with open(inputCsv, 'rt', encoding='latin1') as infile:
        reader = csv.reader(infile)
        data = list(reader)
    
    # calculate unification to reach reasonable amount of lines
    totalLines = len(data)
    updatesPerStep = max(int(totalLines / maximumLines), 1)
    print('updates per step: {}'.format(updatesPerStep))
    
    # Track unique values
    valueList = []
    
    # Initialize a dictionary to keep track of counts
    counts = defaultdict(int)

    outputData = []
    
    # Process each date and value
    for index,row in tq(enumerate(data)):
        date, value = row[dateColumn], row[valueColumn]

        if value not in counts:
            valueList += [value]

        counts[value] += 1

        # only add every X lines (don't update for every 1 commit)
        if 0 == (index % updatesPerStep):
            row = [date] + [counts[val] for val in valueList]
            outputData.append(row)
    
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