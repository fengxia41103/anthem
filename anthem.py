from google.appengine.api import users

import os
import urllib
import json
import cgi
import logging
import datetime

import jinja2
import webapp2
from models import *

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])
        
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
				return {'name':contact.nickname,'email':contact.email,'id':contact.user_id}
		else:
			return json.JSONEncoder.default(self, obj)

class MainPage(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type']='text/plain'
		self.response.write('hey feng')

class PublishNewBuyOrder(webapp2.RequestHandler):
	def get(self):
		# load publish buyorder page
		template_values = {}
	
		template = JINJA_ENVIRONMENT.get_template('/template/PublishNewBuyOrder.html')
		self.response.write(template.render(template_values))

	def post(self):
		# create a new buyorder
		client_email=self.request.POST['client'].strip()
		product=self.request.POST['product'].strip()
		description=self.request.POST['description'].strip()
		qty=int(self.request.POST['qty'])
		price=float(self.request.POST['price'])
		image=self.request.POST['url'].strip()
		
		# manage contact -- who is posting this WTB? usually a DOC
		creator=users.get_current_user()
		me=Contact.get_or_insert(ndb.Key('Contact',creator.user_id()).string_id())		
		
		# update email and user name
		# this is to keep Google user account in sync with internal Contact model
		me.email=creator.email()
		me.nickname=creator.nickname()
		me.put()
		
		# manage contact -- who is the client, optional
		buyer=None
		if client_email: # if not blank
			b_query=Contact.query(Contact.email==client_email)
			if b_query.count():
				assert b_query.count()==1 # email is unique throughout system!
				buyer=b_query.get()
			else: # no contact yet, create one
				buyer=Contact(email=client_email)
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

class ListBuyOrder(webapp2.RequestHandler):
	def post(self):
		filter=self.request.get('filter')
		
		# list of buyorder to browse
		queries=BuyOrder.query().order(-BuyOrder.created_time).fetch(100)
		data=[]
		for q in queries:
			d=q.to_dict()
			d['id']=q.key.id()
			
			# place holder
			d['filled by me']=0
			data.append(d)
		self.response.write(json.dumps(data,cls=ComplexEncoder))	
						
class BrowseBuyOrder(webapp2.RequestHandler):
	def get(self):
		# load buyorder browse page
		template_values = {}
	
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrder.html')
		self.response.write(template.render(template_values))
		
	def post(self):
		# add a new buyorder fill to cart 
		buyorder_id=self.request.POST['id']
		price=float(self.request.POST['price'])
		qty=int(self.request.POST['qty']) # allowing negative!

		# get BuyOrder instance
		buyorder=BuyOrder.get_by_id(int(buyorder_id))
		assert buyorder!=None
		
		# manage contact -- who is posting this WTB? usually a DOC
		creator=users.get_current_user()
		me=Contact.get_or_insert(ndb.Key('Contact',creator.user_id()).string_id())		
		
		# get open cart where terminal_seller == current login user
		# BuyOrder was creatd with a particular termianl_buyer specified
		# we need to locate the cart that has the matching (terminal_buyer,terminal_seller) pair
		# Note: this means that a serller can have multiple OPEN cart as the same time, each identified
		# by the (terminal_buyer,terminal_seller) pair
		cart_query=BuyOrderCart.query(BuyOrderCart.terminal_seller==me.key,BuyOrderCart.status=='Open')	
		my_cart=None
		open_carts=cart_query.filter(BuyOrderCart.terminal_buyer==buyorder.terminal_buyer,BuyOrderCart.terminal_seller==me.key,BuyOrderCart.status=='Open')
		if not open_carts.count():
			# if no such cart, create one
			my_cart=BuyOrderCart(terminal_buyer=buyorder.terminal_buyer,terminal_seller=me.key,status='Open')
			my_cart.owner=me.key
			my_cart.last_modified_by=me.key
			my_cart.put()
		else:
			# each buyer-seller pair for a particular login user can only have 1 OPEN cart at a time!
			# this is the 1-open-cart rule!
			assert open_carts.count()==1
			my_cart=open_carts.get()
			
		# we have established an OPEN cart
		existing=False
		for i in xrange(len(my_cart.fills)):
			f=my_cart.fills[i]
			if f.order==buyorder.key:
				logging.info('Already in my cart!.....')
				
				# it's already in the cart, just update qty
				existing=True
				f.qty+=qty
				f.last_modified_by=me.key
				break
				
		if not existing:
			logging.info('Not in my cart! Create a new fill!')
			
			# if not existing, create a new fill and add to cart
			f=BuyOrderFill(order=buyorder.key,price=price,qty=qty,client_price=0)
			f.owner=me.key
			f.last_modified_by=me.key
			f.put()
			
			# add to my cart
			my_cart.fills.append(f)
			
		# update cart
		my_cart.put()
		
