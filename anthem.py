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
		logging.info(resource)
		
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
		self.response.headers['Content-Type']='text/plain'
		self.response.write('hey feng')

class MyBaseHandler(webapp2.RequestHandler):
	def get_contact(self):
		# manage contact -- who is using my service?
		# update email and user name
		# this is to keep Google user account in sync with internal Contact model
		user = users.get_current_user()
		me=Contact.get_or_insert(ndb.Key('Contact',user.user_id()).string_id(),
			email=user.email(),
			nickname=user.nickname())
			
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
		me=self.get_contact()

		open_cart=BuyOrderCart.query(ancestor=me.key).filter(BuyOrderCart.status=='Open')
		assert open_cart.count()<2
		if open_cart.count():
			my_cart=open_cart.get() # if there is one
		else:
			# if no such cart, create one
			# we are making this cart and Contact an entity group
			# this will enforce data consistency
			my_cart=BuyOrderCart(terminal_seller=me.key,status='Open',parent=me.key)
			my_cart.owner=me.key
			my_cart.last_modified_by=me.key
			my_cart.shipping_cost=0
			my_cart.put()
		return my_cart
							

class PublishNewBuyOrder(MyBaseHandler):
	def get(self):
		me=self.get_contact()
		if not me.can_be_doc():
			template_values = {}
			template = JINJA_ENVIRONMENT.get_template('/template/Membership_New.html')
			self.response.write(template.render(template_values))
			return		

		# load publish buyorder page
		template_values = {}
		template_values['me']=me
		open_cart=template_values['cart']=self.get_open_cart()
		template = JINJA_ENVIRONMENT.get_template('/template/PublishNewBuyOrder.html')
		self.response.write(template.render(template_values))

	def post(self):
		# Assumption: user hits GET first before POST
		# so we don't need to check contact role anymore
		me=self.get_contact()
		
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
		order.owner=me.key
		order.last_modified_by=me.key
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
		me=self.get_contact()
	
		# load buyorder browse page
		template_values = {}
		template_values['url']=uri_for('buyorder-browse')		
		template_values['me']=me
		open_cart=template_values['cart']=self.get_open_cart()
		template_values['url_login']=users.create_login_url(self.request.url)
		template_values['url_logout']=users.create_logout_url('/')

		# filter buyorder by owner
		# and filter by category
		queries=BuyOrder.query(ndb.AND(BuyOrder.owner==ndb.Key(Contact,owner_id), BuyOrder.queues==cat))
		
		# my open cart
		open_cart=template_values['cart']=self.get_open_cart()
		template_values['url_cart_review']=uri_for('cart-review')
		
		if len(open_cart.fills):
			# cart has some fills already, we will enforce
			# a filter to display only BuyOrders from the same owner
			# RULE -- unique (intermediate-buyer,terminal-seller) OPEN cart rule
			owner_key = open_cart.fills[0].order.get().owner
			queries=queries.filter(BuyOrder.owner==owner_key)
				
		# compose data structure for template
		data=[]
		for q in queries.order(-BuyOrder.created_time).fetch(100):
			d={}
			d['order']=q

			# place holder
			d['filled by me']=0
			data.append(d)		
		template_values['buyorders']=data		
		
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrder.html')
		self.response.write(template.render(template_values))

class BrowseBuyOrderByOwner(MyBaseHandler):
	def get(self,owner_id):
		template_values = {}
		template_values['me']=me=self.get_contact()
		open_cart=template_values['cart']=self.get_open_cart()
		
		# limit to 10
		orders=BuyOrder.query(BuyOrder.owner==ndb.Key(Contact,owner_id))
				
		# group them by "queues"
		queue={}
		for o in orders:
			template_values['owner']=o.owner
			for q in o.queues:
				if queue.has_key(q): queue[q].append(o)
				else: queue[q]=[o]
		
		template_values['cats']=sorted(queue.keys())
		template_values['orders']=queue
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrderByOwner.html')
		self.response.write(template.render(template_values))
		
	def post(self,owner_id):
		# return similar posts from the same owner
		me=self.get_contact()
		template_values = {}
		queries=BuyOrder.query(BuyOrder.owner==ndb.Key(Contact,owner_id))
		
		self.response.write(json.dumps([json.dumps(o.to_dict(),cls=ComplexEncoder) for o in queries]))

class BrowseBuyOrder(MyBaseHandler):
	def get(self):
		me=self.get_contact()
		if not me.can_be_nur():
			template_values = {}
			template = JINJA_ENVIRONMENT.get_template('/template/Membership_New.html')
			self.response.write(template.render(template_values))
			return		
	
		# load buyorder browse page
		template_values = {}
		template_values['url']=uri_for('buyorder-browse')		
		template_values['me']=me
		template_values['url_login']=users.create_login_url(self.request.url)
		template_values['url_logout']=users.create_logout_url('/')

		# filters
		# filter by owner id
		try:
			owner_id=self.request.GET['owner']
		except:
			owner_id=None
		template_values['owner_id']=owner_id
			
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
		open_cart=template_values['cart']=self.get_open_cart()
		template_values['url_cart_review']=uri_for('cart-review')
		
		if len(open_cart.fills):
			# cart has some fills already, we will enforce
			# a filter to display only BuyOrders from the same owner
			# RULE -- unique (intermediate-buyer,terminal-seller) OPEN cart rule
			owner_key = open_cart.fills[0].order.get().owner
			queries=queries.filter(BuyOrder.owner==owner_key)
				
		# compose data structure for template
		data=[]
		for q in queries.order(-BuyOrder.created_time).fetch(100):
			d={}
			d['order']=q

			# place holder
			d['filled by me']=0
			data.append(d)		
		template_values['buyorders']=data		
		
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrder.html')
		self.response.write(template.render(template_values))
		
	def post(self):
		# Assumption: user has already hit GET before he can evern POST
		# so we don't need to check Contact here
		me=self.get_contact()
		
		# add a new buyorder fill to cart 
		buyorder_id=self.request.POST['id']
		price=float(self.request.POST['price'])
		qty=int(self.request.POST['qty']) # allowing negative!

		# get BuyOrder instance
		buyorder=BuyOrder.get_by_id(int(buyorder_id))
		assert buyorder!=None
		
		# there is one and only one open cart		
		my_cart=self.get_open_cart()
		assert my_cart!=None
			
		# we have established an OPEN cart
		existing=False		
		for i in xrange(len(my_cart.fills)):
			f=my_cart.fills[i]
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
			f.owner=me.key
			f.last_modified_by=me.key
			my_cart.fills.append(f)
			my_cart.broker=buyorder.owner
			
		# update cart
		my_cart.put()
		
		self.response.write(json.dumps(my_cart.to_dict(),cls=ComplexEncoder))

class ReviewCart(MyBaseHandler):
	def get(self):
		template_values = {}
		cart_id=int(self.request.GET['cart'])
		
		me=self.get_contact()
		cart=BuyOrderCart.get_by_id(cart_id,parent=me.key)
		assert cart!=None		

		template_values['shipping_methods']=SHIPPING_METHOD
		template_values['me']=me		
		template_values['cart']=cart
		template_values['url']=uri_for('cart-review')
		
		# to save label file using BlobStore
		template_values['shipping_form_url']=upload_url=blobstore.create_upload_url('/cart/shipping/%s' % (cart.key.id()))
		
		# serve label file if any
		if cart.shipping_label:
			template_values['shipping_label']='/blob/serve/%s/'% cart.shipping_label
		else:
			template_values['shipping_label']=None
		
		template = JINJA_ENVIRONMENT.get_template('/template/ReviewCart.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		template_values = {}
		cart_id=int(self.request.POST['cart'])
		me=self.get_contact()
		cart=BuyOrderCart.get_by_id(cart_id,parent=me.key)
		assert cart!=None		
		status='0'
		
		if self.request.POST.has_key('action'):
			action=self.request.POST['action']
			id=int(self.request.POST['id'])
			obj=self.request.POST['kind']
			
			if obj=='BuyOrderFill':
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
						f.qty=qty
			
			# approval process
			elif obj=='BuyOrderCart':
				if action.lower()=='submit for approval':
					cart.status='In Approval'
				elif action.lower()=='approve' and cart.status=='In Approval':
					cart.status='Ready for Processing'
					
					# TODO: send email to seller here
				elif action.lower()=='reject' and cart.status=='In Approval':
					cart.status='Rejected'
					# TODO: send email to seller here
				else:
					# TODO: give an assert now
					raise Exception('Unknown path')	
			# update cart
			cart.put()
			self.response.write(status)

class BankingCart(MyBaseHandler):
	def get(self):
		template_values = {}
		me=self.get_contact()
		template_values['me']=me		
		template_values['url']=uri_for('cart-banking')
		template_values['review_url']=uri_for('cart-review')		
		
		carts=BuyOrderCart(parent=me.key).query()
		
		# payable carts
		payable_carts=carts.filter(BuyOrderCart.payable_balance>0)
		if self.request.GET.has_key('seller'):
			seller_id=self.request.GET['seller']
			payable_carts=payable_carts.filter(BuyOrderCart.terminal_seller==ndb.Key('Contact',seller_id))
		template_values['payable_carts']=payable_carts
		template_values['sellers']=set([c.terminal_seller for c in payable_carts])
		
		# receivable carts
		receivable_carts=carts.filter(BuyOrderCart.receivable_balance>0)
		if self.request.GET.has_key('client'):
			client_id=self.request.GET['client']
			receivable_carts=receivable_carts.filter(BuyOrderCart.terminal_buyer==ndb.Key('Contact',client_id))				
		template_values['receivable_carts']=receivable_carts
		template_values['clients']=set([c.terminal_buyer for c in receivable_carts if c.terminal_buyer])
		
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/BankingCart.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		template_values = {}
		me=self.get_contact()
		status='0'
		
		action=self.request.POST['action']
		data=json.loads(self.request.POST['data'])
		payable_bundle=[]
		receivable_bundle=[]
		
		if action=='payable':
			for d in data:
				cart=BuyOrderCart.get_by_id(int(d['id']),parent=me.key)
				assert cart!=None
				slip=AccountingSlip()
				slip.amount=float(d['amount'])
				slip.party_a=me.key
				slip.party_b=cart.terminal_seller
				slip.money_flow='a-2-b'
				slip.last_modified_by=me.key
				payable_bundle.append(slip)
		elif action=='receivable':
			for d in data:
				cart=BuyOrderCart.get_by_id(int(d['id']),parent=me.key)
				assert cart!=None
				slip=AccountingSlip()
				slip.amount=float(d['amount'])
				slip.party_a=me.key
				slip.party_b=cart.terminal_buyer
				slip.money_flow='b-2-a'
				slip.last_modified_by=me.key
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

class ManageUserProfile(MyBaseHandler):
	def get(self):
		template_values = {}
		template_values['me']=me=self.get_contact()
		template_values['membership_options']=MONTHLY_MEMBERSHIP_FEE
			
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageUserProfile.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		me=self.get_contact()
		
class ManageBuyOrderCart(MyBaseHandler):
	def get(self):
		template_values = {}
		template_values['me']=me=self.get_contact()
		template_values['review_url']=uri_for('cart-review')		
		open_cart=template_values['cart']=self.get_open_cart()
		
		# get all carts that belong to this user
		template_values['my_carts']=carts=BuyOrderCart.query(ancestor=me.key)

		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageBuyOrderCart.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		me=self.get_contact()

class ManageBuyOrder(MyBaseHandler):
	def get(self):
		template_values = {}
		template_values['me']=me=self.get_contact()
		
		# get all carts that belong to this user
		template_values['carts']=carts=BuyOrderCart.query(ancestor=me.key)
		template_values['review_url']=uri_for('cart-review')		
		template_values['browse_url']=uri_for('buyorder-browse')		
		
		# get new BuyOrders that are available to me		
		if me.can_be_nur():
			orders=BuyOrder.query().fetch(100)
		if me.can_be_doc():
			orders+=BuyOrder.query(BuyOrder.owner==me.key)
		template_values['orders']=orders
		
		# render
		template = JINJA_ENVIRONMENT.get_template('/template/ManageBuyOrder.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		me=self.get_contact()
		
class ShippingCart(blobstore_handlers.BlobstoreUploadHandler):
	def post(self, cart_id):
		user = users.get_current_user()
		me=Contact.get_or_insert(ndb.Key('Contact',user.user_id()).string_id(),
			email=user.email(),
			nickname=user.nickname())

		cart=BuyOrderCart.get_by_id(int(cart_id),parent=me.key)
		assert cart!=None
		
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
			logging.info(uploads)
				
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
