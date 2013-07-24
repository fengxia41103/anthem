import webapp2
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.api import images
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.blobstore import delete, delete_async
from google.appengine.api import channel
from webapp2 import uri_for,redirect
import os
import urllib
import json
import cgi
import logging
import datetime
import time
import jwt # google wallet token
import jinja2
from models import *
from myUtil import *
from secrets import *

JINJA_ENVIRONMENT = jinja2.Environment(
	loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
	extensions=['jinja2.ext.autoescape'])
                
                
class MyBaseHandler(webapp2.RequestHandler):
	def __init__(self, request=None, response=None):
		webapp2.RequestHandler.__init__(self,request,response) # extend the base class
		self.template_values={}         
		self.template_values['user']=self.user = users.get_current_user()
		self.template_values['url_login']=users.create_login_url(self.request.url)
		self.template_values['url_logout']=users.create_logout_url('/')

class AdminContactHandler(MyBaseHandler):
	def get(self):
		# get all contacts
		self.template_values['contacts']=contacts=Contact.query()
		template = JINJA_ENVIRONMENT.get_template('/template/AdminContact.html')
		self.response.write(template.render(self.template_values))
				
	def post(self):
		contact_id=self.request.get('contact id')
		role=self.request.get('role')
		contact=Contact.get_by_id(contact_id)
		assert contact
		contact.cancel_membership(role)
		
		self.response.write('0')

class AdminContactReputationLinkHandler(MyBaseHandler):
	def post(self):
		contact_id=self.request.get('contact id')
		link=self.request.get('link')
		contact=Contact.get_by_id(contact_id)
		assert contact
		contact.reputation_link=link
		contact.put()
		
		self.response.write('0')

class AdminContactReputationScoreHandler(MyBaseHandler):
	def post(self):
		contact_id=self.request.get('contact id')
		score=self.request.get('score')
		contact=Contact.get_by_id(contact_id)
		assert contact
		contact.reputation_score=int(score)
		contact.put()
		
		self.response.write('0')

class AdminCartHandler(MyBaseHandler):
	def get(self):
		# get all carts
		self.template_values['carts']=carts=BuyOrderCart.query()
		
		template = JINJA_ENVIRONMENT.get_template('/template/AdminCart.html')
		self.response.write(template.render(self.template_values))
				
	def post(self):
		pass
