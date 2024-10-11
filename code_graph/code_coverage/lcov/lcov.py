import os
import sys
from ...graph import Graph

def lcovparse(content):
    # clean and strip lines
    assert 'end_of_record' in content, 'lcov file is missing "end_of_record" line(s)'
    files = filter(lambda f: f != '', content.strip().split("end_of_record"))

    records = [] 

    for f in files:
        record = _part(f)
        if record is not None:
            records.append(record)

    return records

def _part(chunk):
    # search for TN: marker
    lines = chunk.split('\n')

    idx = 0
    for l in lines:
        if l.startswith("TN:"):
            break
        idx += 1

    if idx == len(lines):
        return None

    # remove all lines prior to 'TN:' marker
    lines = lines[idx:]

    report = {
        "test": None,
        "file": None,
        "stats": {},
        "lines": [],
        "functions": [],
        "branches": []
    }

    for l in lines:
        _line(l, report)

    return report

def _line(l, report):
    """
    http://ltp.sourceforge.net/test/coverage/lcov.readme.php#10
    """
    if l == '':
        return None

    method, content = tuple(l.strip().split(':', 1))
    content = content.strip()
    if method == 'TN':
        # test title
        report["test"] = content

    elif method == 'SF':
        # file name
        report["file"] = content

    elif method == 'LF':
        # lines found
        report['stats']['lines'] = int(content)

    elif method == 'LH':
        # line hit
        report['stats']['hit'] = int(content)

    elif method == 'DA':
        if 'null' not in content:
            content = content.split(',')
            line, hit = int(content[0]), int(content[1])
            report['lines'].append(dict(line=line, hit=hit))

    #--------------------------------------------------------------------------
    # Functions
    #--------------------------------------------------------------------------

    elif method == 'FNF':
        # functions found
        report["stats"]["fn_found"] = int(content)

    elif method == 'FNH':
        report["stats"]["fn_hit"] = int(content)

    elif method == 'FN':
        line, name = content.split(',', 1)
        report['functions'].append(dict(line=int(line), name=name))

    elif method == 'FNDA':
        # function names
        # FNDA:75,get_user
        hit, name = content.split(',', 1)
        if hit not in (None, '-', ''):
            for fn in report['functions']:
                if fn['name'] == name:
                    fn['hit'] = int(hit)

    #--------------------------------------------------------------------------
    # Branches
    #--------------------------------------------------------------------------

    elif method == 'BRF':
        report['stats']['br_found'] = int(content)

    elif method == 'BRH':
        report['stats']['br_hit'] = int(content)

    elif method == 'BRDA':
        # branch names
        # BRDA:10,1,0,1
        line, block, branch, taken = content.split(',', 3)
        report['branches'].append(dict(
            line=int(line),
            block=int(block),
            branch=int(branch),
            taken=0 if taken == '-' else int(taken)))

    else:
        sys.stdout.write("Unknown method name %s" % method)

def process_lcov(repo: str, lcov_file: str) -> None:
    # create report from coverage lcov file
    #with open("./coverage.lcov", "r") as file:
    with open(lcov_file, "r") as file:
        content = file.read()  # Reads the entire file as a single string

    report = lcovparse(content)
    #print(f"report: {report}")

    prefix = "/__w/FalkorDB/FalkorDB/src" # prefix to remove
    g = Graph(repo)

    # Process report
    for r in report:
        file_path = r['file']
        file_path = file_path[len(prefix):]

        print(f"Updating file: {file_path}")

        stats = r['stats']
        lines = stats['lines']
        hit   = stats['hit']
        hit_percentage = hit / lines

        ext  = os.path.splitext(file_path)[1]
        path = os.path.dirname(file_path)
        name = os.path.basename(file_path)

        g.set_file_coverage(path, name, ext, hit_percentage)

        # Process functions
        # for each function compute its coverage
        if hit_percentage == 1:
            # the entire file is covered
            continue

    #for file in report:
    #    file_name = file['file']
    #    print(f"file_name: {file_name}")
    #    print(f"lines: {file['stats']['lines']}")
    #    print(f"hists: {file['stats']['hit']}")
    #    for line in file['lines']:
    #        print(f"line number: {line['line']}, hits: {line['hit']}")

#{
#    'test': '',
#    'file': 'falkordb/falkordb.py',
#    'stats': {
#        'lines': 42,
#        'hit': 35
#    },
#    'lines': [
#        {'line': 1, 'hit': 1},
#        {'line': 2, 'hit': 1},
#        {'line': 3, 'hit': 1},
#        {'line': 4, 'hit': 1},
#        {'line': 5, 'hit': 1},
#        {'line': 8, 'hit': 1},
#        {'line': 9, 'hit': 1}
#    ],
#    'functions': [],
#    'branches': []
#}


if __name__ == '__main__':
    process_lcov("src", "./falkordb.lcov")
