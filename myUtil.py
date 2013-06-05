import babel.dates
import urllib

CAT={
	'ipad':['electronic','computer','gadget','personal device','portable computer'],
	'iphone':['electronic','computer','gadget','personal device','portalble computer'],
	'poster':['art','interior design','decoration'],
	'g-shock':['watch','sport watch','fashion'],
	'bounty':['supply','cleaning','paper towel'],
	'lcd':['computer','display','monitor','electronic'],
	'redhat':['software','linux'],
	'software':['software','programming'],
	'kitty':['toy','decoration'],
}

def categorization(words):
	c=[]
	for w in words:
		if w.lower() in CAT: c+=CAT[w.lower()]
	if len(c)==0: c=['uncategoried']
	return list(set(c))

def format_datetime(value, format='medium'):
	if format == 'full':
		format="EEEE, d. MMMM y 'at' HH:mm"
	elif format == 'medium':
		format="EE dd.MM.y HH:mm"
	return babel.dates.format_datetime(value, format)

