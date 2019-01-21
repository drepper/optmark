import sys
import json
import gzip
import functools

def read_passes(tree):
	result = {}
	for e in tree:
		result[e['id']] = e['name']
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

colors = { 'success': '\x1b[1;37;42m', 'failure': '\x1b[1;41m', 'note': '\x1b[1;37;44m' }
coloroff = '\x1b[0m'

inlwhat = { 'Inlining': 1, 'will not early inline:': 3, 'not inlinable:': 3, 'Considering inline candidate': 1 }

def handle(tree):
	passes = read_passes(tree[1])

	files = {}
	for r in tree[2]:
		if 'location' in r:
			l = r['location']
			if not l['file'].startswith('/'):
				fn = l['file']
				if not fn in files:
					files[fn] = []
				linedata = { 'line': l['line'], 'column': l['column'], 'kind': r['kind'], 'what': r['message'][0].strip() }
				if linedata['what'] in inlwhat:
					linedata['inlfunction'] = r['message'][inlwhat[linedata['what']]]['symtab_node']
				files[fn].append(linedata)
				# print(r.keys())
				# print(r['message'])
		elif 'impl_location' in r:
			pass
		else:
			print("unexpected record {}".format(r))
			sys.exit(1)
	for fn,locs in files.items()	:
		locs = sorted(locs, key=functools.cmp_to_key(loc_compare))
		itloc = iter(locs)
		try:
			loc = next(itloc) if itloc else None
		except StopIteration:
			loc = None
		with open(fn, 'r') as srcfile:
			lines = srcfile.readlines()
			lastline = { 'line': 0, 'column': 0, 'what': [] }
			for i in range(len(lines)):
				print('{:5}: {}'.format(i+1, lines[i].rstrip()))
				while loc and loc['line'] == i+1:
					if 'inlfunction' in loc:
						s = "Inlining " + loc['inlfunction']
					else:
						s = loc['what']
					doprint = False
					if loc['line'] != lastline['line'] or loc['column'] != lastline['column']:
						lastline = { 'line': loc['line'], 'column': loc['column'], 'what': [ s ] }
						doprint = True
					else:
						doprint = True
						for w in lastline['what']:
							if s == w:
								doprint = False
								break
					if doprint:
						print('{}      {}^ {}{}'.format(colors[loc['kind']], " "*(loc['column']-1), s, coloroff))
					try:
						loc = next(itloc) if itloc else None
					except StopIteration:
						loc = None
			# print('{}: {}: {}:'.format(fn, l['line'], l['column']))

fname = 'number.cc.opt-record.json.gz'

with gzip.GzipFile(fname, 'r') as z:
	data = z.read()
	j = json.loads(data.decode('utf-8'))
	handle(j)
