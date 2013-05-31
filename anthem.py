import webapp2
from google.appengine.api import users
from webapp2 import uri_for,redirect
import os
import urllib
import json
import cgi
import logging
import datetime

import jinja2
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
			m=Membership(role='Super')
			m.member_pay(1)
			me.memberships.append(m)
			me.put()
		return me

	def get_open_cart(self,me):
		# get open cart where terminal_seller == current login user
		# if BuyOrder was creatd with a particular termianl_buyer specified
		# we need to locate the cart that has the matching (terminal_buyer,terminal_seller) pair
		# 
		# RULE -- single OPEN cart per terminal_seller rule
		# open_cart=BuyOrderCart.query(BuyOrderCart.terminal_seller==me.key,BuyOrderCart.status=='Open')
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
		template_values['user']=me
		template_values['url_login']=users.create_login_url(self.request.url)
		template_values['url_logout']=users.create_logout_url('/')

		# filters
		# filter by owner id
		try:
			owner_id=self.request.GET['owner']
		except:
			owner_id=None
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
			queries=BuyOrder.query(BuyOrder.tags.IN(nd.lower().replace(',',' ').split(' ')))
		else:
			queries=BuyOrder.query()
		
		# my open cart
		open_cart=template_values['cart']=self.get_open_cart(me)
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
		my_cart=self.get_open_cart(me)
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
			f=BuyOrderFill(order=buyorder.key,price=price,qty=qty,client_price=0)
			f.owner=me.key
			f.last_modified_by=me.key
			my_cart.fills.append(f)
			my_cart.broker=buyorder.owner
			
		# update cart
		my_cart.compute_gross_margin()
		my_cart.put()
		
		self.response.write(json.dumps(my_cart.to_dict(),cls=ComplexEncoder))

class ReviewCart(MyBaseHandler):
	def get(self):
		template_values = {}
		cart_id=int(self.request.GET['cart'])
		
		me=self.get_contact()
		cart=BuyOrderCart.get_by_id(cart_id,parent=me.key)
		assert cart!=None		
		
		template_values['cart']=cart
		template_values['url']=uri_for('cart-review')
		template = JINJA_ENVIRONMENT.get_template('/template/ReviewCart.html')
		self.response.write(template.render(template_values))
	
	def post(self):
		template_values = {}
		cart_id=int(self.request.POST['cart'])
		me=self.get_contact()
		cart=BuyOrderCart.get_by_id(cart_id,parent=me.key)
		assert cart!=None		
	
		if self.request.POST.has_key('action'):
			action=self.request.POST['action']
			id=int(self.request.POST['id'])
			obj=self.request.POST['kind']
			
			if obj=='BuyOrderFill':
				# we allow remove fill from cart
				assert action=='remove'
				
				matching_key=ndb.Key('BuyOrder',id)
				new_fills=[f for f in cart.fills if f.order!=matching_key]
				cart.fills=new_fills
				
			# update cart
			cart.put()
			self.response.write('0')
