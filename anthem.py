import webapp2
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.api import images
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.blobstore import delete, delete_async

from webapp2 import uri_for,redirect
import os
import urllib
import json
import cgi
import logging
import datetime

import jinja2
from models import *
from myUtil import *

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])

class ServeHandler(blobstore_handlers.BlobstoreDownloadHandler):
	def get(self, resource):
		# resource is actually a blobkey
  		resource = str(urllib.unquote(resource))
  		blob_info = blobstore.BlobInfo.get(resource)
  		self.send_blob(blob_info)
                      
class ComplexEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime.date):
			epoch = datetime.datetime.utcfromtimestamp(0)
			delta = obj - epoch
			return delta.total_seconds()
			#return obj.isoformat()
		elif isinstance(obj,datetime.datetime):
			epoch = datetime.datetime.utcfromtimestamp(0)
			delta = obj - epoch
			return delta.total_seconds()
		elif isinstance(obj,users.User):
			return {'email':obj.email(),'id':obj.user_id(),'nickname':obj.nickname()}
		elif isinstance(obj,ndb.Key):
			if obj.kind()=='Contact':
				contact=obj.get()
				return {'name':contact.nickname,'email':contact.email,'id':contact.key.id()}
			elif obj.kind()=='BuyOrder':
				o=obj.get()
				return {'name':o.name,'description':o.description,'id':o.key.id(),'owner':o.owner}
		else:
			return json.JSONEncoder.default(self, obj)

class MainPage(webapp2.RequestHandler):
	def get(self):
		self.redirect('/buyorder/browse')
		
class MyBaseHandler(webapp2.RequestHandler):
	def __init__(self, request=None, response=None):
		webapp2.RequestHandler.__init__(self,request,response) # extend the base class
		self.template_values={}
		
		self.template_values['me']=self.me=self.get_contact()
		self.template_values['cart']=self.cart=self.get_open_cart()
		self.template_values['url_login']=users.create_login_url(self.request.url)
		self.template_values['url_logout']=users.create_logout_url('/')

	def get_contact(self):
		# manage contact -- who is using my service?
		# update email and user name
		# this is to keep Google user account in sync with internal Contact model
		user = users.get_current_user()
		me=Contact.get_or_insert(ndb.Key('Contact',user.user_id()).string_id(),
			email=user.email(),
			nickname=user.nickname(),
			cash=0)
			
		# initiate membership
		# TODO: this needs to be replaced by a Membership signup page
		if not me.memberships:
			m=Membership(role='Trial')
			m.member_pay(1) # always 1-month free trial
			me.memberships.append(m)
			me.put()
		return me

	def get_open_cart(self):
		# get open cart where terminal_seller == current login user
		# if BuyOrder was creatd with a particular termianl_buyer specified
		# we need to locate the cart that has the matching (terminal_buyer,terminal_seller) pair
		# 
		# RULE -- single OPEN cart per terminal_seller rule
		# open_cart=BuyOrderCart.query(BuyOrderCart.terminal_seller==me.key,BuyOrderCart.status=='Open')
		open_cart=BuyOrderCart.query(ancestor=self.me.key).filter(BuyOrderCart.status=='Open')
		assert open_cart.count()<2
		if open_cart.count():
			my_cart=open_cart.get() # if there is one
		else:
			# if no such cart, create one
			# we are making this cart and Contact an entity group
			# this will enforce data consistency
			my_cart=BuyOrderCart(terminal_seller=self.me.key,status='Open',parent=self.me.key)
			my_cart.owner=self.me.key
			my_cart.last_modified_by=self.me.key
			my_cart.shipping_cost=0
			my_cart.put()
		return my_cart
							
class EditBuyOrder(MyBaseHandler):
	def get(self, order_id):
		order=BuyOrder.get_by_id(int(order_id))
		assert order
		
		# only owner of this order or super can edit
		if order.owner==self.me.key or self.me.can_be_super():
			self.template_values['order']=order
		else:
			return self.response.write('You do not have the right to edit this order.')
				
		template = JINJA_ENVIRONMENT.get_template('/template/PublishNewBuyOrder.html')
		self.response.write(template.render(self.template_values))

class DeleteBuyOrder(MyBaseHandler):
	def post(self, order_id):
		order=BuyOrder.get_by_id(int(order_id))
		assert order
		
		# only owner of this order or super can edit
		if order.owner==self.me.key or self.me.can_be_super():
			if order.filled_qty:
				return self.response.write('There are open shopping orders on this item. You can not delete this.')
			order.key.delete()
			self.response.write('Order has been deleted')
		else:
			return self.response.write('You do not have the right to edit this order.')
				
class PublishNewBuyOrder(MyBaseHandler):
	def get(self):
		if not self.me.can_be_doc():
			template = JINJA_ENVIRONMENT.get_template('/template/Membership_New.html')
			self.response.write(template.render(self.template_values))
			return		

		# this is used to differentiate new order vs. editing an existing one
		# since we are reusing this template HTML
		self.template_values['order']=None
		
		template = JINJA_ENVIRONMENT.get_template('/template/PublishNewBuyOrder.html')
		self.response.write(template.render(self.template_values))

	def post(self):
		# Assumption: user hits GET first before POST
		# so we don't need to check contact role anymore
		
		# create a new buyorder
		client_email=self.request.POST['client'].strip()
		product=self.request.POST['product'].strip()
		description=self.request.POST['description'].strip()
		qty=int(self.request.POST['qty'])
		price=float(self.request.POST['price'])
		image=self.request.POST['url'].strip()
		
		# manage contact -- who is the client, optional
		buyer=None
		if client_email: # if not blank
			b_query=Contact.query(Contact.email==client_email)
			if b_query.count():
				assert b_query.count()==1 # email is unique throughout system!
				buyer=b_query.get()
			else: 
				# no contact yet, create one
				# Note: crearting a Contact this way will 
				buyer=Contact(email=client_email)
				m=Membership(role='Client')
				m.member_pay(0)
				buyer.memberships.append(m)
				buyer.put()
				
		# create a new buy order and add to store
		order=BuyOrder()
		order.owner=self.me.key
		order.last_modified_by=self.me.key
		if buyer: # buyer info is optional at post
			order.terminal_buyer=buyer.key
		order.name=product
		order.description=description
		order.price=float(price)
		order.qty=int(qty)
		order.image=image
		order.put()
		self.response.write('0')

class BrowseBuyOrderByOwnerByCat(MyBaseHandler):
	def get(self,owner_id,cat):
		# load buyorder browse page
		self.template_values['url']=uri_for('buyorder-browse')		

		# filter buyorder by owner
		# and filter by category
		queries=BuyOrder.query(ndb.AND(BuyOrder.owner==ndb.Key(Contact,owner_id), BuyOrder.queues==cat))
		
		# my open cart
		self.template_values['url_cart_review']=uri_for('cart-review')
		
		if len(self.cart.fills):
			# cart has some fills already, we will enforce
			# a filter to display only BuyOrders from the same owner
			# RULE -- unique (intermediate-buyer,terminal-seller) OPEN cart rule
			owner_key = self.cart.fills[0].order.get().owner
			queries=queries.filter(BuyOrder.owner==owner_key)
				
		# compose data structure for template
		data=[]
		for q in queries.order(-BuyOrder.created_time).fetch(100):
			d={}
			d['order']=q

			# place holder
			d['filled by me']=0
			data.append(d)		
		self.template_values['buyorders']=data		
		
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrder.html')
		self.response.write(template.render(self.template_values))

class BrowseBuyOrderByOwner(MyBaseHandler):
	def get(self,owner_id):
		# limit to 10
		orders=BuyOrder.query(BuyOrder.owner==ndb.Key(Contact,owner_id))
				
		# group them by "queues"
		queue={}
		for o in orders:
			self.template_values['owner']=o.owner
			
			# category as dict key
			for q in o.queues:
				if queue.has_key(q): queue[q].append(o)
				else: queue[q]=[o]
		
		self.template_values['cats']=sorted(queue.keys())
		self.template_values['orders']=queue
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrderByOwner.html')
		self.response.write(template.render(self.template_values))
		
	def post(self,owner_id):
		# return similar posts from the same owner
		queries=BuyOrder.query(BuyOrder.owner==ndb.Key(Contact,owner_id))
		self.response.write(json.dumps([json.dumps(o.to_dict(),cls=ComplexEncoder) for o in queries]))

class BrowseBuyOrderById(MyBaseHandler):
	def get(self,order_id):
		self.template_values['order']=order=BuyOrder.get_by_id(int(order_id))
		assert order
		
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrderById.html')
		self.response.write(template.render(self.template_values))

class BrowseBuyOrder(MyBaseHandler):
	def get(self):
		if not self.me.can_be_nur():
			template = JINJA_ENVIRONMENT.get_template('/template/Membership_New.html')
			self.response.write(template.render(self.template_values))
			return		
	
		# load buyorder browse page
		self.template_values['url']=uri_for('buyorder-browse')		

		# filters
		# filter by owner id
		try:
			owner_id=self.request.GET['owner']
		except:
			owner_id=None
		self.template_values['owner_id']=owner_id
			
		# filter by Name or Description string match
		try:
			nd=self.request.GET['nd']
		except:
			nd=None

		# list of buyorder to browse
		if owner_id:
			queries=BuyOrder.query(BuyOrder.owner==ndb.Key(Contact,owner_id))
		elif nd:
			# this will be OR tag test, meaning that any tag is in the ND list will be True
			queries=BuyOrder.query(BuyOrder.tags.IN(tokenize(nd)))
		else:
			queries=BuyOrder.query()
		
		# my open cart
		self.template_values['url_cart_review']=uri_for('cart-review')
		
		if len(self.cart.fills):
			# cart has some fills already, we will enforce
			# a filter to display only BuyOrders from the same owner
			# RULE -- unique (intermediate-buyer,terminal-seller) OPEN cart rule
			owner_key = self.cart.fills[0].order.get().owner
			queries=queries.filter(BuyOrder.owner==owner_key)
				
		# compose data structure for template
		data=[]
		for q in queries.order(-BuyOrder.created_time).fetch(100):
			d={}
			d['order']=q

			# place holder
			d['filled by me']=0
			data.append(d)		
		self.template_values['buyorders']=data		
		
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrder.html')
		self.response.write(template.render(self.template_values))
		
	def post(self):
		# Assumption: user has already hit GET before he can evern POST
		# so we don't need to check Contact here
		
		# add a new buyorder fill to cart 
		buyorder_id=self.request.POST['id']
		price=float(self.request.POST['price'])
		qty=int(self.request.POST['qty']) # allowing negative!

		# get BuyOrder instance
		buyorder=BuyOrder.get_by_id(int(buyorder_id))
		assert buyorder
		
		# we have established an OPEN cart
		existing=False		
		for i in xrange(len(self.cart.fills)):
			f=self.cart.fills[i]
			if f.order==buyorder.key:
				# it's already in the cart, just update qty
				existing=True
				f.qty+=qty
				f.last_modified_by=me.key
				break
				
		if not existing:
			# if not existing, create a new fill and add to cart
			# default client_price = price so you will break-even
			f=BuyOrderFill(order=buyorder.key,price=price,qty=qty,client_price=price)
			f.owner=self.me.key
			f.last_modified_by=self.me.key
			self.cart.fills.append(f)
			self.cart.broker=buyorder.owner
			
		# update cart
		self.cart.put()
		self.response.write(json.dumps(self.cart.to_dict(),cls=ComplexEncoder))

class ApproveCart(MyBaseHandler):
	def post(self,owner_id,cart_id):
		# wow! getting entity directly from key
		# remember that NDB key is a PATH!
		# further, Contact id is String, where everything else id is an INT.
		# this is a big gotcha.
		cart=ndb.Key('Contact',owner_id,'BuyOrderCart',int(cart_id)).get()
		assert cart
		assert cart.broker==self.me.key
		
		batch=[]
		action=self.request.POST['action']
		if action.lower()=='submit for approval':
			cart.status='In Approval'
		elif action.lower()=='approve' and cart.status=='In Approval':
			cart.status='Ready for Processing'
			
			# update buyorder filled qty
			for f in cart.fills:
				order=f.order.get()
				order.approved_qty+=f.qty
				batch.append(order)
			ndb.put_multi(batch)
			
			# TODO: send email to all parties here
			
		elif action.lower()=='reject' and cart.status=='In Approval':
			cart.status='Rejected'
			# TODO: send email to all parties here
			
		else:
			# TODO: give an assert now
			raise Exception('Unknown path')
				
		cart.last_modified_by=self.me.key
		cart.put()
		self.response.write('0')
		
class ReviewCart(MyBaseHandler):
	def get(self):
		cart_id=int(self.request.GET['cart'])

		try:
			owner_id=self.request.GET['owner']
			owner_key=ndb.Key('Contact',owner_id)
			cart=BuyOrderCart.get_by_id(cart_id,parent=owner_key)
		except:		
			cart=BuyOrderCart.get_by_id(cart_id,parent=self.me.key)
		if not cart:
			self.template_values['cart']=None
		
		else:
			assert cart

			self.template_values['shipping_methods']=SHIPPING_METHOD
			self.template_values['cart']=cart
			self.template_values['url']=uri_for('cart-review')
			
			# to save label file using BlobStore
			self.template_values['shipping_form_url']=upload_url=blobstore.create_upload_url('/cart/shipping/%s' % (cart.key.id()))
			
			# serve label file if any
			if cart.shipping_label:
				self.template_values['shipping_label']='/blob/serve/%s/'% cart.shipping_label
			else:
				self.template_values['shipping_label']=None
			
		template = JINJA_ENVIRONMENT.get_template('/template/ReviewCart.html')
		self.response.write(template.render(self.template_values))
	
	def post(self):
		cart_id=int(self.request.POST['cart'])
		cart=BuyOrderCart.get_by_id(cart_id,parent=self.me.key)
		assert cart
		status='0'
		
		if self.request.POST.has_key('action'):
			action=self.request.POST['action']
			id=int(self.request.POST['id'])
			obj=self.request.POST['kind']
			batch=[]
			
			if obj=='BuyOrderFill':
				# NOTE: these can only be allowed when cart is still OPEN!
				
				matching_key=ndb.Key('BuyOrder',id)
				
				# we allow remove fill from cart
				if action=='remove':
					new_fills=[f for f in cart.fills if f.order!=matching_key]
					cart.fills=new_fills
					
				# update client price
				elif action=='update client price':
					price=float(self.request.POST['price'])
					for f in cart.fills:
						if f.order!=matching_key: continue
						f.client_price=price
				
				# update fill price
				elif action=='update fill price':
					price=float(self.request.POST['price'])
					for f in cart.fills:
						if f.order!=matching_key: continue
						f.price=price

				# update fill qty
				elif action=='update fill qty':
					qty=int(self.request.POST['qty'])
					for f in cart.fills:
						if f.order!=matching_key: continue
						# update order's filled qty
						order=f.order.get()
						order.filled_qty+= (qty-f.qty)
						batch.append(order)
						
						# update fill
						f.qty=qty
						
				# update affected order's if qty changed
				ndb.put_multi(batch)
			
			# update cart
			cart.put()
			self.response.write(status)

class BankingCart(MyBaseHandler):
	def get(self):
		self.template_values['url']=uri_for('cart-banking')
		self.template_values['review_url']=uri_for('cart-review')		
		
		carts=BuyOrderCart.query(ancestor=self.me.key)
		
		# payable carts
		payable_carts=carts.filter(BuyOrderCart.payable_balance>0)
		if self.request.GET.has_key('seller'):
			seller_id=self.request.GET['seller']
			payable_carts=payable_carts.filter(BuyOrderCart.terminal_seller==ndb.Key('Contact',seller_id))
		self.template_values['payable_carts']=payable_carts
		self.template_values['sellers']=set([c.terminal_seller for c in payable_carts])
		
		# receivable carts
		receivable_carts=carts.filter(BuyOrderCart.receivable_balance>0)
		if self.request.GET.has_key('client'):
			client_id=self.request.GET['client']
			receivable_carts=receivable_carts.filter(BuyOrderCart.terminal_buyer==ndb.Key('Contact',client_id))				
		self.template_values['receivable_carts']=receivable_carts
		self.template_values['clients']=set([c.terminal_buyer for c in receivable_carts if c.terminal_buyer])
		
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/BankingCart.html')
		self.response.write(template.render(self.template_values))
	
	def post(self):
		status='0'
		
		action=self.request.POST['action']
		data=json.loads(self.request.POST['data'])
		payable_bundle=[]
		receivable_bundle=[]
		
		if action=='payable':
			for d in data:
				cart=BuyOrderCart.get_by_id(int(d['id']),parent=self.me.key)
				assert cart
				slip=AccountingSlip()
				slip.amount=float(d['amount'])
				slip.party_a=self.me.key
				slip.party_b=cart.terminal_seller
				slip.money_flow='a-2-b'
				slip.last_modified_by=self.me.key
				payable_bundle.append(slip)
		elif action=='receivable':
			for d in data:
				cart=BuyOrderCart.get_by_id(int(d['id']),parent=self.me.key)
				assert cart
				slip=AccountingSlip()
				slip.amount=float(d['amount'])
				slip.party_a=self.me.key
				slip.party_b=cart.terminal_buyer
				slip.money_flow='b-2-a'
				slip.last_modified_by=self.me.key
				receivable_bundle.append(slip)
		
		# write slips to data store		
		ndb.put_multi(payable_bundle+receivable_bundle)
		
		# update cart
		for slip in payable_bundle:
			cart.payout_slips.append(slip.key)
		for slip in receivable_bundle:
			cart.payin_slips.append(slip.key)
		cart.put()
		
		# return status
		self.response.write(status)
	
class ManageBuyOrderCart(MyBaseHandler):
	def get(self):
		self.template_values['review_url']=uri_for('cart-review')		
		
		# get all carts that belong to this user
		# these are ones user has file as a Nur
		self.template_values['my_carts']=BuyOrderCart.query(ancestor=self.me.key).filter(BuyOrderCart.status!='Open')

		# get all carts that this user is the broker
		# these are ones need approval
		self.template_values['broker_carts']=BuyOrderCart.query(BuyOrderCart.broker==self.me.key).filter(BuyOrderCart.status!='Closed')
		
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageBuyOrderCart.html')
		self.response.write(template.render(self.template_values))
	
		
class ManageBuyOrder(MyBaseHandler):
	def get(self):
		# get all carts that belong to this user
		self.template_values['carts']=carts=BuyOrderCart.query(ancestor=self.me.key)
		self.template_values['review_url']=uri_for('cart-review')		
		self.template_values['browse_url']=uri_for('buyorder-browse')		
		
		# get new BuyOrders that are available to me		
		if self.me.can_be_nur():
			orders=BuyOrder.query().fetch(100)
		if self.me.can_be_doc():
			orders+=BuyOrder.query(BuyOrder.owner==me.key)
		self.template_values['orders']=orders
		
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageBuyOrder.html')
		self.response.write(template.render(self.template_values))
	
				
class ShippingCart(blobstore_handlers.BlobstoreUploadHandler):
	def post(self, cart_id):
		user = users.get_current_user()
		me=Contact.get_or_insert(ndb.Key('Contact',user.user_id()).string_id(),
			email=user.email(),
			nickname=user.nickname())

		cart=BuyOrderCart.get_by_id(int(cart_id),parent=me.key)
		assert cart
		
		cart.shipping_carrier=self.request.POST['shipping-carrier']
		cart.shipping_tracking_number=[f.strip() for f in self.request.POST['shipping-tracking'].split(',') if len(f.strip())>0]
		cart.shipping_cost=float(self.request.POST['shipping-cost'])
		cart.shipping_num_of_package=int(self.request.POST['shipping-package'])
		cart.shipping_created_date=datetime.date.today()
		
		# shipping label is optional
		# thin about USPS
		try:
			#cart.shipping_label=self.request.get('shipping-label')
			uploads=self.get_uploads('shipping-label')
			blob_info = uploads[0]
			if cart.shipping_label:
				# if there is existing
				# delete this from blobstore
				# NOTE: blobstore can not overwrite, but can delte
				delete_async(cart.shipping_label)
			
			# now save new blob key
			cart.shipping_label=blob_info.key()
		except:
			pass
			
		cart.shipping_date=datetime.datetime.strptime(self.request.get('shipping-date'),'%Y-%m-%d').date()
		cart.shipping_status='Shipment Created'
		cart.put()	
		
		self.response.write('0')

class MyUserBaseHandler(MyBaseHandler):
	def __init__(self, request=None, response=None):
		MyBaseHandler.__init__(self,request,response) # extend the base class
		self.signed_memberships=[m.role for m in self.me.memberships]	
		self.eligible_new_memberships=[x for x in MONTHLY_MEMBERSHIP_FEE if x not in self.signed_memberships]


class ManageUserMembership(MyUserBaseHandler):
	def get(self):
		self.template_values['membership_options']={x:MONTHLY_MEMBERSHIP_FEE[x] for x in self.eligible_new_memberships}
			
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageUserMembership.html')
		self.response.write(template.render(self.template_values))

class ManageUserMembershipNew(MyUserBaseHandler):
	def post(self):
		data=json.loads(self.request.body)
		
		valid=all([r['role'] in self.eligible_new_memberships for r in data])
		if not valid:
			# if UI is built right, we should never hit here
			# validate that no duplicate role can be created for a user
			self.response.write('-1')
			return
		
		# create a member request and inactive membership
		for r in data:
			member_req=MembershipRequest(user=self.me.key,role=r['role'],start_date=datetime.datetime.strptime(r['start date'],'%Y-%m-%d').date())
			member_req.put()
			
		self.response.write('0')
		
class ManageUserContact(MyBaseHandler):
	def get(self):
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageUserContact.html')
		self.response.write(template.render(self.template_values))

	def post(self):
		self.me.communication=self.request.POST
		self.me.put()
		self.response.write('0')

class ManageUserContactPreference(MyBaseHandler):
	def post(self):
		self.me.shipping_preference=self.request.POST['shipping']
		self.me.payment_preference=self.request.POST['payment']
		self.me.put()
		self.response.write('0')

class ReportBuyOrderPopular(MyBaseHandler):
	def get(self, in_days):
		# get all shopping carts
		# including open ones within the last [in_days]
		carts=BuyOrderCart.query(ancestor=self.me.key).filter(BuyOrderCart.age<=int(in_days)*24*3600)
		
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ReportBuyOrderPopular.html')
		self.response.write(template.render(self.template_values))
		
