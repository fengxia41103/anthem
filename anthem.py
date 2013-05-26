from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import users

import os
import urllib
import json
import cgi
import logging

import jinja2
import webapp2
from models import *

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
		order.owner=creator.user_id()
		order.last_modified_by=creator.user_id()
		order.name=product
		order.description=description
		order.price=float(price)
		order.qty=int(qty)
		order.image=image
		order.put()		
		
class BrowseBuyOrder(webapp2.RequestHandler):
	def get(self):
		pass
