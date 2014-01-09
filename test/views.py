import os

from google.appengine.dist import use_library
use_library('django', '1.2')
os.environ['DJANGO_SETTINGS_MODULE'] = '__init__'

import webapp2 as webapp
from webapp2_extras import sessions
from google.appengine.ext.webapp import template

from models import *


sessions.default_config['secret_key'] = '-- secret key --'


class View(webapp.RequestHandler):

    def dispatch(self):

        src = 'http://' + self.request.headers['host']

        paypal.Accept.returnurl = src + '/accept/return/'
        paypal.Accept.cancelurl = src + '/accept/cancel/'

        paypal.Transfer.returnurl = src + '/transfer/return/'
        paypal.Transfer.cancelurl = src + '/transfer/cancel/'

        self.session_store = sessions.get_store(
            request=self.request
        )
        try:
            webapp.RequestHandler.dispatch(self)
        finally:
            self.session_store.save_sessions(self.response)

    @webapp.cached_property
    def session(self):
        return self.session_store.get_session()

    def render(self, path, template_values={}):
        path = os.path.join(
            os.path.dirname(__file__), 'templates/%s.html' % path
        )
        self.response.out.write(template.render(path, template_values))


class IndexView(View):

    def get(self):
        self.response.out.write(
        '''
        <a href="/accept/">accept</a>
        <a href="/transfer/">transfer</a>
        '''
        )


class AcceptView(View):

    def get(self):

        payment = paypal.Accept.gql(
            'LIMIT 1'
        ).get()
        if not payment:
            payment = paypal.Accept(
                amount=10.00
            )
            payment.put()

        self.redirect(payment.create())


class AcceptReturnView(View):

    def get(self):

        token = str(self.request.get('token'))
        payer_id = str(self.request.get('PayerID'))

        if not (token and payer_id):
            self.response.out.write('400 both token and pay id required')
            return

        payment = paypal.Accept.find_by_token(token)
        payment.payer_id = payer_id
        payment.put()
        
        payment.execute()
        
        self.response.out.write(payment)


class AcceptCancelView(View):

    def get(self):
        pass


class TransferView(View):

    def get(self):
        transfer = paypal.Transfer.gql(
            'LIMIT 1'
        ).get()
        if not transfer:
            transfer = paypal.Transfer(
            )
            transfer.put()
        receiver = paypal.Receiver.gql(
            'LIMIT 1'
        ).get()
        if not receiver:
            receiver = paypal.Receiver(
                email=conf['receiver'],
                amount=10.00,
                transfer=transfer.key
            )
            receiver.put()
        url = transfer.create()
        self.redirect(url)


class TransferReturnView(View):

    def get(self):
        transfer = paypal.Transfer.gql(
            'LIMIT 1'
        ).get()
        transfer.execute()


class TransferCancelView(View):

    def get(self):
        pass


urls = [
    ('/', IndexView),
    ('/accept/', AcceptView),
    ('/accept/return/', AcceptReturnView),
    ('/accept/cancel/', AcceptCancelView),
    ('/transfer/', TransferView),
    ('/transfer/return/', TransferReturnView),
    ('/transfer/cancel/', TransferCancelView),
]

app = webapp.WSGIApplication(urls, debug=True)
