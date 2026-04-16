def counts(lines):
    """
    count occurrences across a log or dataset.
    Equal weight for every line, if you need to include some kind of score per line, use weightCounts.

    Example:
    called X
    called Y
    called Z
    called Y
    called Y
    called Z

    totals will be: X:1, Y:3, Z:1
    """
    if isinstance(lines, str):
        lines = lines.splitlines()

    return weightCounts(['1 ' + str(line) for line in lines])

def weightCounts(lines):
    """
    count occurrences with weighting across a log or dataset 
    useful for things like timed logs that "write hit count" per log line.

    Example:
    3 called X
    6 called Y
    4 called X
    15 called Z
    1 called Y
    1 called Y

    totals will be X:7, Y:8, Z:15 instead of a single weight per line.
    """
    from collections import Counter
    if isinstance(lines, str):
        lines = lines.splitlines()

    counter = Counter()
    for line in lines:
        count, text = line.split(maxsplit=1)
        counter[text] += int(count)
    
    return counter