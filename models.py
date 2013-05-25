from google.appengine.ext import ndb

class MyBaseModel(ndb.Model):
	# two time stamps
	created_time=ndb.DateTimeProperty(auto_now_add=True)
	last_modified_time=ndb.DateTimeProperty(auto_now=True)
	
	# object owner tied to login user
	owner=ndb.StringProperty()
	last_modified_by=ndb.StringProperty()
	
class BuyOrderFill(MyBaseModel):
	# seller fill
	qty=ndb.IntegerProperty()
	price=ndb.FloatProperty()
	payable=ndb.ComputedProperty(lambda self: self.qty*self.price)
	
	# broker fill
	client_price=ndb.FloatProperty()
	receivable=ndb.ComputedProperty(lambda self: self.client_price*self.qty)
	
	# status
	status=ndb.StringProperty(repeated=True)
	
	# accounting
	over_short=ndb.ComputedProperty(lambda self: self.receivable-self.payable)
	gross_margin=ndb.ComputedProperty(lambda self: self.over_short/self.payable*100.0)
	
			
class BuyOrderCart(MyBaseModel):
	buyer=ndb.StringProperty()
	client=ndb.StringProperty()
	
	# a cart has multiple fills
	fills=ndb.StructuredProperty(BuyOrderFill,repeated=True)
	
class BuyOrder(MyBaseModel):
	# standard fields
	name=ndb.StringProperty()
	description=ndb.StringProperty()
	image=ndb.StringProperty()
	qty=ndb.IntegerProperty()
	price=ndb.FloatProperty()

	# an order has multiple carts
	carts=ndb.StructuredProperty(BuyOrderCart,repeated=True)
