from google.appengine.ext import ndb
from google.appengine.api.users import User

class Contact(ndb.Model):
	user_id=ndb.StringProperty() # user id
	email=ndb.StringProperty() # user email
	nickname=ndb.StringProperty() # user name
	shipping_address=ndb.StringProperty()
	phone=ndb.PickleProperty() # a list

class MyBaseModel(ndb.Model):
	# two time stamps
	created_time=ndb.DateTimeProperty(auto_now_add=True)
	last_modified_time=ndb.DateTimeProperty(auto_now=True)
	
	# object owner tied to a Contact
	owner=ndb.KeyProperty(kind='Contact')
	last_modified_by=ndb.KeyProperty(kind='Contact')

class Billing(MyBaseModel):
	name_on_account=ndb.StringProperty() # billing person's name, this can be different from the user who uses this payment
	address=ndb.StringProperty() # billing address
	media=ndb.StringProperty() # MasterCard, Visa, payPay, whatever else
	account_number=ndb.StringProperty() # account #, credit card #, and so on
	expiration_date=ndb.DateProperty()
	secret=ndb.StringProperty() # key code, whatever else

class AccountingSlip(MyBaseModel):
	payor=ndb.KeyProperty(kind='Contact')
	receiver=ndb.KeyProperty(kind='Contact')
	type=ndb.StringProperty() # in ['withdraw', 'deposit']
	amount=ndb.FloatProperty()
		
class BuyOrder(MyBaseModel):
	terminal_buyer=ndb.KeyProperty(kind='Contact') # optional
	name=ndb.StringProperty()
	description=ndb.StringProperty()
	image=ndb.StringProperty()
	qty=ndb.IntegerProperty()
	price=ndb.FloatProperty()
	payable=ndb.ComputedProperty(lambda self: self.qty*self.price)

	tags=ndb.ComputedProperty(lambda self: list(set([f for f in self.name.lower().split(' ')]+[f for f in self.description.lower().split(' ')])), repeated=True)
	
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
	terminal_seller=ndb.KeyProperty(kind='Contact')
	terminal_buyer=ndb.KeyProperty(kind='Contact')
	
	status=ndb.StringProperty()
	shipping_status=ndb.StringProperty()
	shipping_carrier=ndb.StringProperty()
	
	# a cart has multiple fills
	fills=ndb.StructuredProperty(BuyOrderFill,repeated=True)
	
	# some status
	payable=ndb.ComputedProperty(lambda self: sum([f.payable for f in self.fills]))
	receivable=ndb.ComputedProperty(lambda self:sum([f.receivable for f in self.fills]))
	profit=ndb.ComputedProperty(lambda self: self.receivable-self.payable)
	gross_margin=ndb.FloatProperty() # since payable can be 0, division will fail, so set value manually
			
	# a cart has multiple bank slips
	account_slips=ndb.StructuredProperty(AccountingSlip,repeated=True)

	
