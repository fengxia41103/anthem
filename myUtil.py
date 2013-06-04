
CAT={
	'ipad':['electronic','computer','gadget','personal device','portable computer'],
	'iphone':['electronic','computer','gadget','personal device','portalble computer'],
	'poster':['art','interior design','decoration'],
	'g-shock':['watch','sport watch','fashion'],
	'bounty':['supply','cleaning','paper towel']
}

def categorization(words):
	c=[]
	for w in words:
		if w.lower() in CAT: c+=CAT[w.lower()]
	return list(set(c))

