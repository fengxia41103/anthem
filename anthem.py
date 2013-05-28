from google.appengine.api import users
from google.appengine.ext import ndb

import os
import urllib
import json
import cgi
import logging
import datetime

import jinja2
import webapp2
from models import *

class DateEncoder(json.JSONEncoder):
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
		else:
			return json.JSONEncoder.default(self, obj)

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])
        
class MainPage(webapp2.RequestHandler):
	def get(self):
		self.response.headers['Content-Type']='text/plain'
		self.response.write('hey feng')

class PublishNewBuyOrder(webapp2.RequestHandler):
	def get(self):
		template_values = {}
	
		template = JINJA_ENVIRONMENT.get_template('/template/PublishNewBuyOrder.html')
		self.response.write(template.render(template_values))

	def post(self):
		client=self.request.POST['client']
		product=self.request.POST['product']
		description=self.request.POST['description']
		qty=self.request.POST['qty']
		price=self.request.POST['price']
		image=self.request.POST['url']
		
		# create a new buy order and add to store
		creator=users.get_current_user()
		order=BuyOrder()
		order.owner_id=creator.user_id()
		order.owner_name=creator.nickname()
		order.last_modified_by=creator.user_id()
		order.name=product
		order.description=description
		order.price=float(price)
		order.qty=int(qty)
		order.image=image
		order.put()		

class ListBuyOrder(webapp2.RequestHandler):
	def get(self):
		#filter=rquest.post['filter']
		queries=BuyOrder.query().order(-BuyOrder.created_time).fetch(10)
		
		data=[]
		for q in queries:
			d=q.to_dict()
			d['id']=q.key.id()
			
			# place holder
			d['filled by me']=0
			data.append(d)
		#self.response.write(json.dumps([p.to_dict() for p in queries],cls=DateEncoder))		
		logging.info(data)
		self.response.write(json.dumps(data,cls=DateEncoder))	
						
class BrowseBuyOrder(webapp2.RequestHandler):
	def get(self):
		# return a buy order list based on filter string
		template_values = {}
	
		template = JINJA_ENVIRONMENT.get_template('/template/BrowseBuyOrder.html')
		self.response.write(template.render(template_values))
