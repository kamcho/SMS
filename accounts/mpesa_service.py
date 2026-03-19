import base64
import requests
from requests.auth import HTTPBasicAuth
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
from .models import MpesaTransaction, MpesaCallback


class MpesaService:
    """Service class for M-Pesa API integration"""
    
    def __init__(self):
        self.consumer_key = getattr(settings, 'MPESA_CONSUMER_KEY', '')
        self.consumer_secret = getattr(settings, 'MPESA_CONSUMER_SECRET', '')
        self.passkey = getattr(settings, 'MPESA_PASSKEY', '')
        self.shortcode = getattr(settings, 'MPESA_SHORTCODE', '')
        self.initiator_name = getattr(settings, 'MPESA_INITIATOR_NAME', '')
        self.initiator_password = getattr(settings, 'MPESA_INITIATOR_PASSWORD', '')
        self.security_credential = getattr(settings, 'MPESA_SECURITY_CREDENTIAL', '')
        self.callback_url = getattr(settings, 'MPESA_CALLBACK_URL', '')
        self.result_url = getattr(settings, 'MPESA_RESULT_URL', '')
        self.queue_timeout_url = getattr(settings, 'MPESA_QUEUE_TIMEOUT_URL', '')
        self.environment = getattr(settings, 'MPESA_ENVIRONMENT', 'sandbox')
        
        # Set base URLs based on environment
        if self.environment == 'production':
            self.base_url = 'https://api.safaricom.co.ke'
        else:
            self.base_url = 'https://sandbox.safaricom.co.ke'
    
    def get_access_token(self):
        """Get M-Pesa OAuth access token directly from Safaricom without using database cache"""
        print(f"🔑 DEBUG: Generating new M-Pesa access token for {self.environment}...")
        
        # Verify credentials aren't empty
        if not self.consumer_key or not self.consumer_secret:
            print(f"❌ DEBUG: Missing credentials! Key: '{self.consumer_key}', Secret: '{self.consumer_secret}'")
            raise Exception("M-Pesa Consumer Key or Secret is missing in settings.")

        # Show partial keys for verification by user
        key_show = f"{self.consumer_key[:4]}...{self.consumer_key[-4:]}" if len(self.consumer_key) > 8 else "****"
        secret_show = f"{self.consumer_secret[:4]}...{self.consumer_secret[-4:]}" if len(self.consumer_secret) > 8 else "****"
        print(f"🔐 DEBUG: Using Key: {key_show}, Secret: {secret_show}")
        
        # Get new token from M-Pesa
        api_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        print(f"🌐 DEBUG: Requesting token from: {api_url}")
        
        try:
            # Use HTTPBasicAuth explicitly as requested
            response = requests.get(
                api_url,
                auth=HTTPBasicAuth(self.consumer_key, self.consumer_secret),
                timeout=30
            )
            
            print(f"📡 DEBUG: Token response status: {response.status_code}")
            print(f"📡 DEBUG: Token response body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get('access_token')
                print(f"✅ DEBUG: Successfully generated access token")
                return access_token
            else:
                print(f"❌ DEBUG: Failed to generate access token. Status: {response.status_code}, Body: {response.text}")
                # We raise an exception here; the view should handle it to show a nice error
                raise Exception(f"M-Pesa Token generation failed with status {response.status_code}: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"🚨 DEBUG: Network error while generating access token: {str(e)}")
            raise Exception(f"Network error while generating access token: {str(e)}")

    
    def generate_password(self):
        """Generate password for STK push"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password_str = f"{self.shortcode}{self.passkey}{timestamp}"
        password_bytes = password_str.encode('ascii')
        password = base64.b64encode(password_bytes).decode('ascii')
        return password, timestamp
    
    def stk_push(self, phone_number, amount, account_reference, transaction_desc, callback_url=None):
        """Initiate STK push payment"""
        print(f"🚀 DEBUG: Starting STK push...")
        print(f"📱 DEBUG: Phone: {phone_number}")
        print(f"💰 DEBUG: Amount: {amount}")
        print(f"📝 DEBUG: Account Reference: {account_reference}")
        print(f"📝 DEBUG: Transaction Desc: {transaction_desc}")
        print(f"🔗 DEBUG: Callback URL: {callback_url}")
        
        try:
            access_token = self.get_access_token()
            password, timestamp = self.generate_password()
            
            print(f"🔐 DEBUG: Generated password: {password[:20]}...")
            print(f"⏰ DEBUG: Timestamp: {timestamp}")
            
            api_url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
            print(f"🌐 DEBUG: STK Push URL: {api_url}")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': 'CustomerPayBillOnline',
                'Amount': int(amount),
                'PartyA': phone_number,
                'PartyB': self.shortcode,
                'PhoneNumber': phone_number,
                'CallBackURL': callback_url or self.callback_url,
                'AccountReference': account_reference,
                'TransactionDesc': transaction_desc
            }
            
            print(f"📦 DEBUG: STK Push payload:")
            for key, value in payload.items():
                if 'Password' not in key:
                    print(f"   {key}: {value}")
                else:
                    print(f"   {key}: {value[:20]}...")
            
            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            print(f"📡 DEBUG: STK Push response status: {response.status_code}")
            print(f"📡 DEBUG: STK Push response body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ DEBUG: STK Push successful!")
                return {
                    'success': True,
                    'data': data,
                    'merchant_request_id': data.get('MerchantRequestID'),
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'response_code': data.get('ResponseCode'),
                    'response_description': data.get('ResponseDescription'),
                    'customer_message': data.get('CustomerMessage')
                }
            else:
                print(f"❌ DEBUG: STK Push failed!")
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            print(f"🚨 DEBUG: Network error in STK push: {str(e)}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            print(f"🚨 DEBUG: Unexpected error in STK push: {str(e)}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def pull_transaction(self, receiver_party, receiver_id, amount, remarks, occasion=''):
        """Initiate B2C transaction (Business to Customer)"""
        # Check if initiator credentials are configured
        if not self.initiator_name or not self.security_credential:
            return {
                'success': False,
                'error': 'Initiator credentials not configured. Required for B2C transactions.'
            }
        
        try:
            access_token = self.get_access_token()
            
            api_url = f"{self.base_url}/mpesa/b2c/v1/paymentrequest"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'InitiatorName': self.initiator_name,
                'SecurityCredential': self.security_credential,
                'CommandID': 'BusinessPayment',
                'Amount': int(amount),
                'PartyA': self.shortcode,
                'PartyB': receiver_party,
                'Remarks': remarks,
                'QueueTimeOutURL': self.queue_timeout_url,
                'ResultURL': self.result_url,
                'Occasion': occasion
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'conversation_id': data.get('ConversationID'),
                    'originator_conversation_id': data.get('OriginatorConversationID'),
                    'response_code': data.get('ResponseCode'),
                    'response_description': data.get('ResponseDescription')
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def transaction_status(self, transaction_id, party_a, party_b, remarks=''):
        """Check transaction status"""
        # Check if initiator credentials are configured
        if not self.initiator_name or not self.security_credential:
            return {
                'success': False,
                'error': 'Initiator credentials not configured. Required for transaction status queries.'
            }
        
        try:
            access_token = self.get_access_token()
            
            api_url = f"{self.base_url}/mpesa/transactionstatus/v1/query"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'InitiatorName': self.initiator_name,
                'SecurityCredential': self.security_credential,
                'CommandID': 'TransactionStatusQuery',
                'TransactionID': transaction_id,
                'PartyA': party_a,
                'PartyB': party_b,
                'IdentifierType': '1',  # 1 for MSISDN, 2 for Till Number, 4 for Shortcode
                'ResultURL': self.result_url,
                'QueueTimeOutURL': self.queue_timeout_url,
                'Remarks': remarks
            }
            
            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'response_code': data.get('ResponseCode'),
                    'response_description': data.get('ResponseDescription')
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def process_callback(self, callback_data, callback_type='success'):
        """Process M-Pesa callback data"""
        print(f"📞 DEBUG: Processing M-Pesa callback...")
        print(f"📞 DEBUG: Callback type: {callback_type}")
        print(f"📞 DEBUG: Raw callback data: {json.dumps(callback_data, indent=2)}")
        
        try:
            # Extract relevant data from callback
            body = callback_data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            
            merchant_request_id = stk_callback.get('MerchantRequestID')
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')
            
            print(f"🔍 DEBUG: Merchant Request ID: {merchant_request_id}")
            print(f"🔍 DEBUG: Checkout Request ID: {checkout_request_id}")
            print(f"🔍 DEBUG: Result Code: {result_code}")
            print(f"🔍 DEBUG: Result Description: {result_desc}")
            
            # Find the transaction
            transaction = MpesaTransaction.objects.filter(
                merchant_request_id=merchant_request_id,
                checkout_request_id=checkout_request_id
            ).first()
            
            if not transaction:
                print(f"❌ DEBUG: Transaction not found for IDs: {merchant_request_id}, {checkout_request_id}")
                return {
                    'success': False,
                    'error': 'Transaction not found'
                }
            
            print(f"✅ DEBUG: Found transaction: {transaction.id}")
            
            # Store callback data
            MpesaCallback.objects.create(
                transaction=transaction,
                callback_type=callback_type,
                raw_data=callback_data
            )
            print(f"💾 DEBUG: Callback data stored")
            
            # Update transaction based on result
            if result_code == 0 or result_code == '0':
                print(f"💰 DEBUG: Transaction successful - processing payment details")
                callback_metadata = stk_callback.get('CallbackMetadata', {})
                items = callback_metadata.get('Item', [])
                
                mpesa_receipt = None
                transaction_date = None
                phone_number = None
                amount = None
                
                for item in items:
                    name = item.get('Name')
                    value = item.get('Value')
                    
                    print(f"📋 DEBUG: Callback item - {name}: {value}")
                    
                    if name == 'MpesaReceiptNumber':
                        mpesa_receipt = value
                    elif name == 'TransactionDate':
                        transaction_date = value
                    elif name == 'PhoneNumber':
                        phone_number = value
                    elif name == 'Amount':
                        amount = value
                
                print(f"💰 DEBUG: Extracted - Receipt: {mpesa_receipt}, Date: {transaction_date}, Phone: {phone_number}, Amount: {amount}")
                
                # Update transaction
                transaction.status = 'completed'
                transaction.response_code = result_code
                transaction.response_description = result_desc
                transaction.mpesa_receipt_number = mpesa_receipt
                transaction.processed_at = timezone.now()
                
                if transaction_date:
                    # Parse transaction date (format: YYYYMMDDHHMMSS)
                    try:
                        dt = datetime.strptime(str(transaction_date), '%Y%m%d%H%M%S')
                        transaction.transaction_date = dt
                        print(f"📅 DEBUG: Parsed transaction date: {dt}")
                    except ValueError:
                        print(f"⚠️ DEBUG: Could not parse transaction date: {transaction_date}")
                
                transaction.save()
                print(f"✅ DEBUG: Transaction updated to completed")
                
                # Update or create student payment
                if hasattr(transaction, 'fee_payment') and hasattr(transaction.fee_payment, 'id'):
                    # Legacy support: update existing payment
                    try:
                        payment = transaction.fee_payment
                        payment.method = 'Mpesa'
                        payment.reference = transaction.mpesa_receipt_number
                        payment.save()
                        print(f"💳 DEBUG: Updated existing linked fee payment: {payment.id}")
                    except Exception as e:
                        print(f"⚠️ DEBUG: Error updating existing payment: {str(e)}")
                elif transaction.student:
                    # New flow: create Payment object here to reduce fee balance ONLY on success
                    from .models import Payment
                    try:
                        payment = Payment.objects.create(
                            student=transaction.student,
                            amount=transaction.amount,
                            method='Mpesa',
                            reference=transaction.mpesa_receipt_number,
                            date_paid=timezone.now().date(),
                            recorded_by=transaction.initiated_by,
                            mpesa_transaction=transaction
                        )
                        print(f"💳 DEBUG: Created fee payment on success: {payment.id}")
                    except Exception as e:
                        print(f"⚠️ DEBUG: Error creating fee payment on success: {str(e)}")
                
                # Update staff payment if linked via reverse relation
                if hasattr(transaction, 'salary_payment'):
                    staff_payment = transaction.salary_payment
                    staff_payment.payment_method = 'Mpesa'
                    staff_payment.reference = transaction.mpesa_receipt_number
                    staff_payment.save()
                    print(f"💼 DEBUG: Updated linked staff payment: {staff_payment.id}")
                
                return {
                    'success': True,
                    'message': 'Transaction completed successfully',
                    'transaction_id': str(transaction.id),
                    'mpesa_receipt': mpesa_receipt
                }
            else:
                print(f"❌ DEBUG: Transaction failed - updating status")
                transaction.status = 'failed'
                transaction.response_code = result_code
                transaction.response_description = result_desc
                transaction.processed_at = timezone.now()
                transaction.save()
                print(f"❌ DEBUG: Transaction updated to failed")
                
                return {
                    'success': False,
                    'message': 'Transaction failed',
                    'error': result_desc,
                    'transaction_id': str(transaction.id)
                }
                
        except Exception as e:
            print(f"🚨 DEBUG: Error processing callback: {str(e)}")
            import traceback
            print(f"🚨 DEBUG: Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f"Error processing callback: {str(e)}"
            }

    def query_pull_transactions(self, start_date=None, end_date=None, offset=0):
        """Query Pull Transactions API for reconciliation"""
        print(f"🔍 DEBUG: Querying Pull Transactions...")
        
        try:
            access_token = self.get_access_token()
            
            # Default dates if not provided (Documentation says up to 48 hours)
            if not start_date:
                start_date = (timezone.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            if not end_date:
                end_date = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                
            api_url = f"{self.base_url}/pulltransactions/v1/query"
            print(f"🌐 DEBUG: Pull URL: {api_url}")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "ShortCode": self.shortcode,
                "StartDate": start_date,
                "EndDate": end_date,
                "OffSetValue": str(offset)
            }
            
            print(f"📦 DEBUG: Payload: {payload}")
            
            # The documentation says GET but provides a body. 
            # Note: Safaricom's Production API often requires POST when a JSON body is sent.
            response = requests.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            print(f"📡 DEBUG: Response status: {response.status_code}")
            print(f"📡 DEBUG: Response body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': data,
                    'status_code': 200
                }
            else:
                return {
                    'success': False,
                    'error': response.text,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            print(f"🚨 DEBUG: Error in query_pull_transactions: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

