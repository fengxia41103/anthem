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
		client=self.request.POST['client']
		product=self.request.POST['product']
		description=self.request.POST['description']
		qty=self.request.POST['qty']
		price=self.request.POST['price']
		image=self.request.POST['url']
		
		# create a new buy order and add to store
		order=BuyOrder()
		order.owner=users.get_current_user()
		order.last_modified_by=users.get_current_user()
		order.name=product
		order.description=description
		order.price=float(price)
		order.qty=int(qty)
		order.image=image
		order.put()		

class ListBuyOrder(webapp2.RequestHandler):
	def get(self):
		# list of buyorder to browse
		#filter=rquest.post['filter']
		queries=BuyOrder.query().order(-BuyOrder.created_time).fetch(10)
		
		data=[]
		for q in queries:
			d=q.to_dict()
			d['id']=q.key.id()
			
			# place holder
			d['filled by me']=0
			data.append(d)
		logging.info(data)
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
		price=self.request.POST['price']
		qty=self.request.POST['qty']

		# get open cart
		
