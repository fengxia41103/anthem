from google.appengine.ext import ndb
from google.appengine.api.users import User
import datetime
from dateutil.relativedelta import relativedelta
from secrets import *
from myUtil import *

#######################################
#
# User management models
#
#######################################
class Membership(ndb.Model):
	# StructuredProperty within a Contact
	created_time=ndb.DateTimeProperty(auto_now_add=True)
	
	# membership payments
	monthly_payment=ndb.ComputedProperty(lambda self: MONTHLY_MEMBERSHIP_FEE[self.role])
	last_payment_amount=ndb.FloatProperty()
	last_payment_received_date=ndb.DateProperty()
	
	# must be float since cancellation can result in a partial month
	last_payment_cover_month=ndb.FloatProperty()
	payment_to_date=ndb.FloatProperty(default=0) # accumulative
	
	# membership service role
	role=ndb.StringProperty(default='Nur',choices=['Nur','Doc','Client','Super','Trial'])
	
	# as of writing, ComputedProperty does not support Date, 5/30/2013	
	expiration_date=ndb.DateProperty()
	
	# auto detect whether memship can be active based on last_payment information
	is_active=ndb.ComputedProperty(lambda self: datetime.date.today()<=self.expiration_date)

	def member_pay(self,num_of_month,amount=None):
		# if amount specified, use the amount
		# otherwise, use a calculation
		if amount:
			# this essential is an override
			# eg. promotion of a special term or rate
			self.last_payment_amount=amount
		else:
			self.last_payment_amount=num_of_month*self.monthly_payment
			
		self.last_payment_received_date=datetime.date.today()
		self.last_payment_cover_month=num_of_month
		self.payment_to_date+=self.last_payment_amount
		
		# calculated from last_payment_cover_month
		# int() will have an effect of giving out extra time for free
		# this is ok since UI will pass in integer values anway.
		if num_of_month:
			self.expiration_date=self.last_payment_received_date+relativedelta( months = +int(self.last_payment_cover_month))
		else:
			# if num_of_month==0, we are actually setting up this member for the first time 
			# but want to keep it inactive, so we set expiration_date to Yesterday, ha.
			self.expiration_date=self.last_payment_received_date+relativedelta(days=-1)
			
	def member_cancel(self):
		# if member decides to cancel prior to its natural expiration
		# we will calculate a refund if any
		# and the self.last_payment_cover_month will be NEGATIVE!
		# so we can use this as an indicator for cancellation
		remaining=relativedelta(datetime.date.today(),self.expiration_date)
		in_month=remaining.years*12+remainings.months
		refund=self.last_payment_amount*(in_month/self.last_payment_cover_month)
		
		# this will set is_active=False, which equals to deactivating this memebership!
		self.last_payment_cover_month -=in_month
		self.last_payment_received_date=datetime.date.today()
		self.payment_to_date-=refund
		self.expiration_date=datetime.date.today()
						
class Billing(ndb.Model):
	# StructuredProperty within a Contact
	name_on_account=ndb.StringProperty() # billing person's name, this can be different from the user who uses this payment
	address=ndb.StringProperty() # billing address
	media=ndb.StringProperty(default='Manual',choices=['MasterCard','Visa','PayPal','Manual'])
	account_number=ndb.StringProperty() # account #, credit card #, and so on
	expiration_date=ndb.DateProperty() # user manual setup
	secret=ndb.StringProperty() # key code, whatever else
	is_default=ndb.BooleanProperty()

class Contact(ndb.Model):
	# key_name will be the user_id()
	email=ndb.StringProperty() # user email
	nickname=ndb.StringProperty() # user name
	communication=ndb.PickleProperty(default={'phone':''}) # a dict

	# a Contact can sign up multiple membership kinds
	memberships=ndb.StructuredProperty(Membership,repeated=True)
	is_active=ndb.ComputedProperty(lambda self: any([m.is_active for m in self.memberships]))
	
	# a Contact can have multiple billing methods
	# we only need one working to proceed a charge
	billing_methods=ndb.StructuredProperty(Billing,repeated=True)
	
	# we don't need to know its residential
	shipping_address=ndb.StringProperty()
	
	# shipping method preference
	# write whatever you want
	# eg. state, carrier, 
	shipping_preference=ndb.StringProperty()
	
	# payment method preference
	# write whatever you want
	payment_preference=ndb.StringProperty()
	
	def can_be_doc(self):
		# if a Doc membership is Active
		return (self.is_active and any([m.role in ['Doc','Super','Trial'] for m in self.memberships]))

	def can_be_nur(self):
		# if a Nur membership is Active
		return (self.is_active and any([m.role in ['Nur','Super','Trial'] for m in self.memberships]))

	def can_be_client(self):
		# if a Client membership is Active
		return (self.is_active and any([m.role in ['Client','Super','Trial'] for m in self.memberships]))
	

#######################################
#
# Abstract models
#
#######################################
class MyBaseModel(ndb.Model):
	# two time stamps
	created_time=ndb.DateTimeProperty(auto_now_add=True)
	last_modified_time=ndb.DateTimeProperty(auto_now=True)
	
	# object owner tied to a Contact
	owner=ndb.KeyProperty(kind='Contact')
	last_modified_by=ndb.KeyProperty(kind='Contact')
		
#######################################
#
# Financial transaction models
#
#######################################
class AccountingSlip(MyBaseModel):
	party_a=ndb.KeyProperty(kind='Contact')
	party_b=ndb.KeyProperty(kind='Contact')
	#method=ndb.KeyProperty(kind='Billing') # transaction method
	money_flow=ndb.StringProperty(choices=['a-2-b','b-2-a']) # who gives the amount to whom
	amount=ndb.FloatProperty()


#######################################
#
# Business transaction models
#
#######################################
class BuyOrder(MyBaseModel):
	terminal_buyer=ndb.KeyProperty(kind='Contact') # optional
	name=ndb.StringProperty()
	description=ndb.TextProperty()
	image=ndb.StringProperty()
	qty=ndb.IntegerProperty()
	price=ndb.FloatProperty()
	payable=ndb.ComputedProperty(lambda self: self.qty*self.price)

	# tags is a string list tokenized self.name and self.description by white space
	# tags are all lower case!
	# TODO: use NLTK package to be intelligent
	tags=ndb.ComputedProperty(lambda self: tokenize(self.name), repeated=True)
	
	# category keywords
	# we are to be smart about this property so user doesn't need to input
	# instead, we will parse the tags and look for keywords that internally will map to a particular category
	# category keywords will function as tags when searching
	queues=ndb.ComputedProperty(lambda self: categorization(self.tags), repeated=True,indexed=True)
	
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
	gross_margin=ndb.ComputedProperty(lambda self: self.over_short/self.payable*100.0 if self.payable else 0)

class BuyOrderCart(MyBaseModel):	
	terminal_seller=ndb.KeyProperty(kind='Contact')
	terminal_buyer=ndb.KeyProperty(kind='Contact')
	broker=ndb.KeyProperty(kind='Contact')

	# these flags should be MANUALLY set by each party of this transaction as an acknowledgement!
	buyer_reconciled=ndb.BooleanProperty(default=False)
	seller_reconciled=ndb.BooleanProperty(default=False)
	
	# shipping related
	status=ndb.StringProperty(choices=['Open','In Approval','Ready for Processing','Rejected','Closed','In Shipment'],default='Open')
	shipping_status=ndb.StringProperty(choices=['Shipment Created','Carrier Picked Up','In Route','Delivery Confirmed by Carrier','Buyer Reconciled','Incomplete Packages'])
	shipping_carrier=ndb.StringProperty(choices=SHIPPING_METHOD)
	shipping_cost=ndb.FloatProperty()
	shipping_num_of_package=ndb.IntegerProperty()
	
	# allowing multiple tracking numbers
	shipping_tracking_number=ndb.StringProperty(repeated=True)
	shipping_created_date=ndb.DateProperty() # when the info was entered  by user
	shipping_date=ndb.DateProperty() # actual shipping date by user
	#shipping_label=ndb.BlobProperty() # allowing one label file
	shipping_label=ndb.BlobKeyProperty()
	
	# a cart has multiple fills
	fills=ndb.StructuredProperty(BuyOrderFill,repeated=True)
	
	# some status
	payable=ndb.ComputedProperty(lambda self: sum([f.payable for f in self.fills]))
	receivable=ndb.ComputedProperty(lambda self:sum([f.receivable for f in self.fills]))
	profit=ndb.ComputedProperty(lambda self: self.receivable-self.payable-self.shipping_cost)
	gross_margin=ndb.ComputedProperty(lambda self: self.profit/self.payable*100.0 if self.payable else 0)
			
	# a cart has multiple bank slips
	# owner of BuyOrder is always "a"
	# payout: terminal seller is "b", slip is a-2-b, thus a cost to the broker
	# payin: termian client is "b", slip is b-2-a, thus an income to the broker
	payout_slips=ndb.KeyProperty(kind='AccountingSlip',repeated=True)
	payin_slips=ndb.KeyProperty(kind='AccountingSlip',repeated=True)
	payout=ndb.ComputedProperty(lambda self: sum([p.get().amount for p in self.payout_slips]))
	payin=ndb.ComputedProperty(lambda self: sum([p.get().amount for p in self.payin_slips]))
	payable_balance=ndb.ComputedProperty(lambda self: self.payable-self.payout)
	receivable_balance=ndb.ComputedProperty(lambda self: self.receivable-self.payin)
	
	# this is what we actually earned based on payin and payout
	realized_profit=ndb.ComputedProperty(lambda self: self.payin-self.payout)
	realized_gross_margin=ndb.ComputedProperty(lambda self: self.realized_profit/self.payout*100.0 if self.payout else 0)	
