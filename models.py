from google.appengine.ext import ndb
from google.appengine.api.users import User

class MyBaseModel(ndb.Model):
	# two time stamps
	created_time=ndb.DateTimeProperty(auto_now_add=True)
	last_modified_time=ndb.DateTimeProperty(auto_now=True)
	
	# object owner tied to login user
	owner=ndb.UserProperty()
	last_modified_by=ndb.UserProperty()

class Billing(MyBaseModel):
	name_on_account=ndb.StringProperty() # billing person's name, this can be different from the user who uses this payment
	address=ndb.StringProperty() # billing address
	media=ndb.StringProperty() # MasterCard, Visa, payPay, whatever else
	account_number=ndb.StringProperty() # account #, credit card #, and so on
	expiration_date=ndb.DateProperty()
	secret=ndb.StringProperty() # key code, whatever else
	
class Contact(MyBaseModel):
	user=ndb.UserProperty() # we create a User for each contact regardless
	shipping_address=ndb.StringProperty()
	phone=ndb.PickleProperty() # a list
	
class AccountingSlip(MyBaseModel):
	type=ndb.StringProperty()
	amount=ndb.FloatProperty()
		
class BuyOrder(MyBaseModel):
	terminal_buyer=ndb.UserProperty() # optional
	name=ndb.StringProperty()
	description=ndb.StringProperty()
	image=ndb.StringProperty()
	qty=ndb.IntegerProperty()
	price=ndb.FloatProperty()
	payable=ndb.ComputedProperty(lambda self: self.qty*self.price)

class BuyOrderFill(MyBaseModel):
	# buyoreder reference
	order=ndb.KeyProperty(kind='BuyOrder')
	
	# seller fill
	qty=ndb.IntegerProperty()
	price=ndb.FloatProperty()
	
	# computed payable
	payable=ndb.ComputedProperty(lambda self: self.qty*self.price)
	
	# broker fill
	client_price=ndb.FloatProperty()
	receivable=ndb.ComputedProperty(lambda self: self.client_price*self.qty)
	
	# accounting
	over_short=ndb.ComputedProperty(lambda self: self.receivable-self.payable)
	gross_margin=ndb.ComputedProperty(lambda self: self.over_short/self.payable*100.0)

class BuyOrderCart(MyBaseModel):	
	terminal_seller=ndb.UserProperty()
	terminal_buyer=ndb.UserProperty()
	
	status=ndb.StringProperty()
	shipping_status=ndb.StringProperty()
	shipping_carrier=ndb.StringProperty()
	
	# a cart has multiple fills
	fills=ndb.StructuredProperty(BuyOrderFill,repeated=True)
	
	# a cart has multiple bank slips
	account_slips=ndb.StructuredProperty(AccountingSlip,repeated=True)
