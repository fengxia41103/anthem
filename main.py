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

	# buyorder controllers
	Route('/blob/serve/<resource:[^/]+>/', handler='anthem.ServeHandler',name='blobstore-serve'),
	Route('/buyorder/edit/<order_id:\d+>/', handler='anthem.EditBuyOrder',name='buyorder-edit'),
	Route('/buyorder/delete/<order_id:\d+>/', handler='anthem.DeleteBuyOrder',name='buyorder-delete'),
	Route('/buyorder/new', handler='anthem.PublishNewBuyOrder', name='buyorder-new'),
	Route('/buyorder/browse/<order_id:\d+>/', handler='anthem.BrowseBuyOrderById',name='buyorder-browse-id'),
	Route('/buyorder/browse', handler='anthem.BrowseBuyOrder',name='buyorder-browse'),
	Route('/buyorder/owner/<owner_id:\d+>/<cat:[^/]+>/', handler='anthem.BrowseBuyOrderByOwnerByCat',name='buyorder-browse-owner-cat'),  
	Route('/buyorder/owner/<owner_id:\d+>/', handler='anthem.BrowseBuyOrderByOwner',name='buyorder-browse-owner'),  
	Route('/buyorder/manage', handler='anthem.ManageBuyOrder',name='buyorder-manage'),  
	
	# cart controllers
	Route('/cart/approve/<owner_id:\d+>/<cart_id:\d+>/', handler='anthem.ApproveCart',name='cart-approve'),  
	Route('/cart/review', handler='anthem.ReviewCart',name='cart-review'),  
	Route('/cart/banking', handler='anthem.BankingCart',name='cart-banking'),  
	Route('/cart/shipping/process/<owner_id:\d+>/<cart_id:[^/]+>/', handler='anthem.ShippingCartProcess',name='cart-shipping-process'),  
	Route('/cart/shipping/<owner_id:\d+>/<cart_id:[^/]+>/', handler='anthem.ShippingCart',name='cart-shipping'),  
	Route('/cart/manage/seller', handler='anthem.ManageCartAsSeller',name='cart-manage-as-seller'),  
	Route('/cart/manage/buyer', handler='anthem.ManageCartAsBuyer',name='cart-manage-as-buyer'),  


	# user controllers
	Route('/user/contact/preference',handler='anthem.ManageUserContactPreference',name='user-contact-preference'),	
	Route('/user/contact',handler='anthem.ManageUserContact',name='user-contact'),	
	Route('/user/membership/new',handler='anthem.ManageUserMembershipNew',name='user-membership-new'),	
	Route('/user/membership',handler='anthem.ManageUserMembership',name='user-membership'),	
	
	# report controllers
	Route('/report/myseller/<in_days:\d+>/',handler='anthem.ReportMySeller',name='report-myseller'),	
	Route('/report/buyorder/<in_days:\d+>/',handler='anthem.ReportBuyOrderPopular',name='report-buyorder-popular'),	
]

app = WSGIApplication(routes, config=app_config, debug=True)
