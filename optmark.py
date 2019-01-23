#! /usr/bin/env python3
import sys
import json
import gzip
import functools
import getopt


def read_passes(tree):
    result = {}
    for e in tree:
        result[e['id']] = e['name']
        if 'children' in e:
            result = { **result, **read_passes(e['children']) }
    return result


def loc_compare(rec1, rec2):
    if rec1['line'] < rec2['line']:
        return -1
    if rec1['line'] > rec2['line']:
        return 1
    if rec1['column'] < rec2['column']:
        return -1
    if rec1['column'] > rec2['column']:
        return 1
    if rec1['kind'] == 'success':
        return -1 if rec2['kind'] != 'success' else 0
    if rec2['kind'] == 'success':
        return 1
    if rec1['kind'] == 'failure':
        return -1 if rec2['kind'] != 'failure' else 0
    if rec2['kind'] == 'failure':
        return 1
    return 0


colors = { 'success': '\x1b[1;37;42m', 'failure': '\x1b[1;41m', 'note': '\x1b[1;37;44m', 'scope': '\x1b[45m' }
coloroff = '\x1b[0m'

inlwhat = { 'Inlining': 1, 'Inlined': 1, 'will not early inline:': 3, 'not inlinable:': 3, 'Considering inline candidate': 1 }


def handle(root, tree, relative, interesting):
    passes = read_passes(tree[1])

    files = {}
    for r in tree[2]:
        if 'location' in r:
            l = r['location']
            if not relative or not l['file'].startswith('/'):
                fn = l['file']
                if len(interesting) == 0 or fn in interesting:
                    if not fn in files:
                        files[fn] = []
                    linedata = { 'line': l['line'], 'column': l['column'], 'kind': r['kind'], 'what': r['message'][0].strip() if len(r['message']) > 0 else '** no message **' }
                    if linedata['what'] in inlwhat:
                        linedata['inlfunction'] = r['message'][inlwhat[linedata['what']]]['symtab_node']
                    if 'pass' in r and r['pass'] in passes:
                        linedata['pass'] = passes[r['pass']]
                    files[fn].append(linedata)
        elif 'impl_location' in r:
            pass
        else:
            print("unexpected record {}".format(r))
            sys.exit(1)
    for fn,locs in files.items()    :
        locs = sorted(locs, key=functools.cmp_to_key(loc_compare))
        itloc = iter(locs)
        try:
            loc = next(itloc) if itloc else None
        except StopIteration:
            loc = None
        with open(root + fn, 'r') as srcfile:
            lines = srcfile.readlines()
            lastline = { 'line': 0, 'column': 0, 'what': [] }
            for i in range(len(lines)):
                print('{:5}: {}'.format(i+1, lines[i].rstrip()))
                while loc and loc['line'] == i+1:
                    if 'inlfunction' in loc:
                        s = "Inlining " + loc['inlfunction']
                    else:
                        s = loc['what']
                    if 'pass' in loc:
                        s += ' ({} pass)'.format(loc['pass'])
                    doprint = True
                    if loc['line'] != lastline['line'] or loc['column'] != lastline['column']:
                        lastline = { 'line': loc['line'], 'column': loc['column'], 'what': [ ] }
                    else:
                        for w in lastline['what']:
                            if s == w:
                                doprint = False
                                break
                    if doprint:
                        lastline['what'].append(s)
                        print('{}{}^ {}{}'.format(colors[loc['kind']], " "*(loc['column']+5), s, coloroff))
                    try:
                        loc = next(itloc) if itloc else None
                    except StopIteration:
                        loc = None


def usefile(root, fname, relative, interesting):
    try:
        with gzip.GzipFile(fname, 'r') as z:
            data = z.read()
            j = json.loads(data.decode('utf-8'))
            try:
                handle(root, j, relative, interesting)
            except BrokenPipeError:
                pass
        return True
    except OSError:
        return False


def usage(argv):
    print("Usage: {} [-r ROOT] [--relative] [--root ROOT] OPTRECORD [SRCFILE]...".format(argv[0]))


if __name__ == '__main__':
    fname = ''
    root = ''
    relative = False
    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'r:', [ 'root=', 'relative' ])
    except getopt.GetoptError as err:
        print(err)
        usage(sys.argv)
        sys.exit(1)
    for opt, arg in optlist:
        if opt == '-r' or opt == '--root':
            root = arg
            if not root.endswith('/'):
                root += '/'
        elif opt == '--relative':
            relative = True
        else:
            assert False, "unknown option"
    if len(args) == 0:
        usage(sys.argv)
        sys.exit(3)
    fname = args[0]
    interesting = args[1:]

    if not usefile(root, fname, relative, interesting) and not usefile(root, root + fname, relative, interesting):
        print("cannot find opt-record file `{}'".format(fname))
        sys.exit(4)
