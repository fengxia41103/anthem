# -*- coding: utf-8 -*-
import sys
from secrets import SESSION_KEY

from webapp2 import WSGIApplication, Route

# inject './lib' dir in the path so that we can simply do "import ndb" 
# or whatever there's in the app lib dir.
if 'lib' not in sys.path:
    sys.path[0:0] = ['lib']

# webapp2 config
app_config = {
  'webapp2_extras.sessions': {
    'cookie_name': '_simpleauth_sess',
    'secret_key': SESSION_KEY
  },
  'webapp2_extras.auth': {
    'user_attributes': []
  }
}
    
# Map URLs to handlers
routes = [
	Route('/', handler='anthem.MainPage'),  
	Route('/profile', handler='handlers.ProfileHandler', name='profile'),
	Route('/logout', handler='handlers.AuthHandler:logout', name='logout'),
	Route('/auth/<provider>',handler='handlers.AuthHandler:_simple_auth', name='auth_login'),
	Route('/auth/<provider>/callback', handler='handlers.AuthHandler:_auth_callback', name='auth_callback'),

	# Anthem
	Route('/buyorder/new', handler='anthem.PublishNewBuyOrder'),  	
	Route('/buyorder/browse', handler='anthem.BrowseBuyOrder',name='buyorder-browse'),  
	Route('/buyorder/owner/<owner_id:\d+>/<cat:[^/]+>/', handler='anthem.BrowseBuyOrderByOwnerByCat',name='buyorder-browse-owner-cat'),  
	Route('/buyorder/owner/<owner_id:\d+>/', handler='anthem.BrowseBuyOrderByOwner',name='buyorder-browse-owner'),  
	Route('/buyorder/manage', handler='anthem.ManageBuyOrder',name='buyorder-manage'),  
	Route('/cart/review', handler='anthem.ReviewCart',name='cart-review'),  
	Route('/cart/manage', handler='anthem.ManageBuyOrderCart',name='cart-manage'),  
	Route('/cart/banking', handler='anthem.BankingCart',name='cart-banking'),  
	Route('/cart/shipping/<cart_id:[^/]+>/', handler='anthem.ShippingCart',name='cart-shipping'),  
	Route('/user/profile',handler='anthem.ManageUserProfile',name='user-profie'),	
]

app = WSGIApplication(routes, config=app_config, debug=True)
