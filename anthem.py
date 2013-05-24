import os
import urllib
import json
import cgi
import logging

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2


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
		qty=self.request.POST['qty']
		price=self.request.POST['price']
		image=self.request.POST['url']
		self.response.write(json.dumps({'me':'this'}))
		
		
class Test(webapp2.RequestHandler):
	def post(self):
		name=self.request.POST['name']
		comment=self.request.POST['comment']
		self.response.write(str(json.dumps({'me':'this'})))		
