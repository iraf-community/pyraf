####
#	The usual debugging style assertion routines
####

Assertion = "Assertion Failed"
Die = "Die"

def assert(*args):
	from utils import seq_to_str
	if not args[0]:
		if len(args) == 1:
			raise Assertion, args[1]+"()"
		else:
			raise Assertion, args[1]+"(): " + seq_to_str(args[2:])

def die(*args):
	from utils import seq_to_str
	if len(args) == 1:
		raise Die, args[0]+"()"
	else:
		m = seq_to_str(args[1:])
		raise Die, args[0]+"(): " + m
