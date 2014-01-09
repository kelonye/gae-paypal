import urllib
import urllib2
import urlparse
from google.appengine.ext import ndb
from google.appengine.api import urlfetch
from google.appengine.ext import deferred
from google.appengine._internal.django.utils import simplejson as json

# configurables
user = None
password = None
signature = None
version = 109
sandbox = True
app_id = 'APP-80W284485P519543T'


# paypal call error e.g. timeout, ssl
class RequestError(Exception):
    pass


# acknowledgment error
class AckError(Exception):
    pass


class Model(ndb.Model):

    defer_status_check_by_minutes = 30

    status = ndb.StringProperty(
    )
    currency = ndb.StringProperty(
        default='USD'
    )

    def get_url(self, url):
        if sandbox:
            url = url % 'sandbox.'
        else:
            url = url % ''
        return url


class Accept(Model):

    token = ndb.StringProperty(
    )
    payer_id = ndb.StringProperty(
    )
    transaction_id = ndb.StringProperty(
    )
    amount = ndb.FloatProperty(
    )

    def build_request_url(self, opts, url='https://api.%spaypal.com/nvp'):
        
        url = self.get_url(url)

        opts.update({
            'USER': user,
            'PWD': password,
            'SIGNATURE': signature,
            'VERSION': version
        })

        return url + '?' + urllib.urlencode(opts)

    def call(self, opts, url='https://api.%spaypal.com/nvp'):

        url = self.build_request_url(opts, url)

        ctx = ndb.get_context()
        res = ctx.urlfetch(url).get_result()

        if res.status_code != 200:
            raise RequestError(res.content)

        return urlparse.parse_qs(res.content)

    # request payment token
    # @return {str} confirm url
    def create(self):

        qs = self.call({
            'METHOD': 'SetExpressCheckout',
            'PAYMENTREQUEST_0_PAYMENTACTION': 'SALE',
            'PAYMENTREQUEST_0_AMT': str(self.amount),
            'PAYMENTREQUEST_0_CURRENCYCODE': str(self.currency),
            'returnUrl': Accept.returnurl,
            'cancelUrl': Accept.cancelurl
        })
        if qs['ACK'] != ['Success']:
            raise AckError(qs)
        [self.token] = qs['TOKEN']
        self.put()

        url = 'https://www.%spaypal.com/cgi-bin/webscr'
        url = self.build_request_url({
            'cmd': '_express-checkout',
            'token': self.token
        }, url)
        return url

    # complete and check payment status
    def execute(self):

        if not self.get_is_pending():
            return

        qs = self.call({
            'METHOD': 'DoExpressCheckoutPayment',
            'TOKEN': self.token,
            'PAYERID': self.payer_id,
            'PAYMENTREQUEST_0_PAYMENTACTION': 'SALE',
            'PAYMENTREQUEST_0_AMT': self.amount,
            'PAYMENTREQUEST_0_CURRENCYCODE': self.currency
        })
        [self.transaction_id] = qs['PAYMENTINFO_0_TRANSACTIONID']
        self.put()

        self.check_status()

    # check payment status if pending
    def check_status(self):

        if not self.get_is_pending():
            return

        qs = self.call({
            'METHOD': 'GetTransactionDetails',
            'TRANSACTIONID': self.transaction_id
        })
        self.status = qs['PAYMENTSTATUS'][0].upper()
        self.put()

        if not self.get_is_pending():
            return

        deferred.defer(
            self.check_status,
            _countdown=Accept.defer_status_check_by_minutes
        )

    # return true if pending
    def get_is_pending(self):
        return self.status in [
            None,
            'NONE',
            'PENDING',
            'IN-PROGRESS'
        ]

    # find payment with `token`
    @classmethod
    def find_by_token(cls, token):
        return Accept.gql('WHERE token=:1', token).get()


class Transfer(Model):

    pay_key = ndb.StringProperty(
    )

    def call(self, payload, url='https://svcs.%spaypal.com/AdaptivePayments/Pay'):

        url = self.get_url(url)
        
        headers = {
            'X-PAYPAL-SECURITY-USERID' : user,
            'X-PAYPAL-SECURITY-PASSWORD' : password,
            'X-PAYPAL-SECURITY-SIGNATURE' : signature,
            'X-PAYPAL-APPLICATION-ID': app_id,
            'X-PAYPAL-REQUEST-DATA-FORMAT' : 'JSON',
            'X-PAYPAL-RESPONSE-DATA-FORMAT' : 'JSON',
            'Content-Type': 'application/json'
        }

        ctx = ndb.get_context()
        res = ctx.urlfetch(
            url,
            headers=headers,
            payload=json.dumps(payload),
            method=urlfetch.POST
        ).get_result()

        if res.status_code != 200:
            raise RequestError(res.content)

        data = json.loads(res.content)
        envelope = data['responseEnvelope']
        ack = envelope.get('ack') or envelope.get('ACK')

        if ack != 'Success':
            raise AckError(res.content)

        return data

    def create(self):

        def receivers():
            for receiver in self.receivers():
                yield {
                    'amount': receiver.amount,
                    'email': receiver.email
                }

        payload = {
            "actionType": "PAY",
            "currencyCode": self.currency,
            "receiverList": {
                "receiver": list(receivers())
            },
            "returnUrl": Transfer.returnurl,
            "cancelUrl": Transfer.cancelurl,
            "requestEnvelope": {
                "errorLanguage": "en_US",
                "detailLevel": "ReturnAll"
            }
        }

        data = self.call(payload)

        self.pay_key = str(data['payKey'])
        self.put()

        url = 'https://www.%spaypal.com/cgi-bin/webscr'

        url = self.get_url(url)
        
        return url + '?' + urllib.urlencode({
            'cmd': '_ap-payment',
            'paykey': self.pay_key
        })

    def execute(self):
        self.check_status()

    # check payment status if pending
    def check_status(self):

        if not self.get_is_pending():
            return

        payload = {
            "payKey": self.pay_key,
            "requestEnvelope": {
                "errorLanguage": "en_US",
                "detailLevel": "ReturnAll"
            }
        }

        url = 'https://svcs.%spaypal.com/AdaptivePayments/PaymentDetails'
        data = self.call(payload, url)

        self.status = data['status'].upper()
        self.put()

        if not self.get_is_pending():
            return

        deferred.defer(
            self.check_status,
            _countdown=Accept.defer_status_check_by_minutes
        )

    def receivers(self):
        return Receiver.gql(
            'WHERE transfer=:1', self.key
        )

    # return true if pending
    def get_is_pending(self):
        return self.status in [
            None,
            'NONE',
            'PENDING',
            'PROCESSING'
        ]


class Receiver(ndb.Model):
    email = ndb.StringProperty(
    )
    amount = ndb.FloatProperty(
    )
    transfer = ndb.KeyProperty(
        kind=Transfer
    )
