import requests
import json
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db import models
from .mpesa_service import MpesaService
from .models import MpesaTransaction, MpesaCallback, Payment
import logging

logger = logging.getLogger(__name__)


class MpesaTransactionService:
    """Service for fetching and managing M-Pesa transactions"""
    
    def __init__(self):
        self.mpesa_service = MpesaService()
    
    def fetch_paybill_transactions(self, start_date=None, end_date=None):
        """
        Fetch actual transactions from M-Pesa paybill using Daraja Pull Transactions API
        This gets real transactions from M-Pesa servers
        """
        print(f"🔍 DEBUG: Fetching REAL paybill transactions from Daraja Pull Transactions API")
        print(f"📅 DEBUG: Date range: {start_date} to {end_date}")
        
        # Check if initiator credentials are configured
        if not self.mpesa_service.initiator_name or not self.mpesa_service.security_credential:
            print("❌ DEBUG: Initiator credentials not configured for transaction query")
            return {
                'success': False,
                'error': 'Initiator credentials required for fetching transactions from M-Pesa'
            }
        
        try:
            access_token = self.mpesa_service.get_access_token()
            
            # Default to last 3 hours if no dates provided
            if not start_date:
                start_date = timezone.now() - timedelta(hours=3)
            if not end_date:
                end_date = timezone.now()
            
            # Use Pull Transactions API 
            api_url = f"{self.mpesa_service.base_url}/pulltransactions/v1/query"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "ShortCode": self.mpesa_service.shortcode,  # Your Paybill/Till number
                "StartDate": start_date.strftime('%Y-%m-%d %H:%M:%S'),
                "EndDate": end_date.strftime('%Y-%m-%d %H:%M:%S'),
                "OffSetValue": "0"
            }
            
            print(f"🌐 DEBUG: Calling Pull Transactions API at {api_url}")
            print(f"🔐 DEBUG: Using shortcode: {self.mpesa_service.shortcode}")
            print(f"📦 DEBUG: Payload: {payload}")
            
            # Make the actual API call
            response = requests.get(api_url, json=payload, headers=headers, timeout=30)
            
            print(f"📡 DEBUG: API response status: {response.status_code}")
            print(f"📡 DEBUG: API response body: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ DEBUG: Successfully received transaction data")
                
                # Process the response data
                transactions = []
                
                # Handle different response formats from M-Pesa
                if 'Result' in data:
                    result_data = data['Result']
                    
                    if isinstance(result_data, list):
                        # Direct list of transactions
                        for item in result_data:
                            transactions.append(self._format_transaction(item))
                    elif isinstance(result_data, dict) and 'Items' in result_data:
                        # Nested structure with Items array
                        for item in result_data['Items']:
                            transactions.append(self._format_transaction(item))
                
                print(f"📊 DEBUG: Processed {len(transactions)} transactions")
                
                return {
                    'success': True,
                    'transactions': transactions,
                    'total_count': len(transactions),
                    'start_date': start_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'end_date': end_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'source': 'Daraja Pull Transactions API',
                    'raw_response': data
                }
            else:
                print(f"❌ DEBUG: API call failed with status {response.status_code}")
                return {
                    'success': False,
                    'error': f"API call failed: {response.text}",
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            print(f"🚨 DEBUG: Network error calling Pull Transactions API: {str(e)}")
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            print(f"🚨 DEBUG: Unexpected error: {str(e)}")
            import traceback
            print(f"🚨 DEBUG: Traceback: {traceback.format_exc()}")
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def _format_transaction(self, item):
        """Format transaction item from API response and save to database if new"""
        # Handle different field names from M-Pesa API
        receipt = item.get('TransID', item.get('MpesaReceiptNumber', item.get('transactionId')))
        phone = item.get('MSISDN', item.get('PhoneNumber', item.get('Source', item.get('msisdn', ''))))
        amount = item.get('TransAmount', item.get('Amount', item.get('amount', 0)))
        date_str = item.get('TransTime', item.get('TransactionDate', item.get('trxDate', '')))
        
        # Save to database if not exists
        txn = None
        if receipt:
            txn, created = MpesaTransaction.objects.get_or_create(
                mpesa_receipt_number=receipt,
                defaults={
                    'transaction_type': 'stk_push',  # Likely from pull API
                    'phone_number': phone,
                    'amount': float(amount) if amount else 0,
                    'status': 'completed',
                    'response_code': '0',
                    'response_description': item.get('TransDesc', item.get('Description', 'Pulled from Daraja API')),
                    'processed_at': timezone.now()
                }
            )
            if created and date_str:
                # Try parsing different date formats
                for fmt in ('%Y%m%d%H%M%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
                    try:
                        txn.transaction_date = datetime.strptime(str(date_str), fmt)
                        txn.save()
                        break
                    except:
                        continue

        return {
            'id': str(txn.id) if txn else str(uuid.uuid4()),
            'phone_number': phone,
            'amount': float(amount) if amount else 0,
            'reference_number': receipt or 'N/A',
            'transaction_date': date_str,
            'status': 'completed',
            'transaction_type': 'stk_push',
            'response_description': item.get('TransDesc', item.get('Description', 'Transaction completed')),
            'student': {
                'id': txn.fee_payment.student.id,
                'name': f"{txn.fee_payment.student.first_name} {txn.fee_payment.student.last_name}" if txn.fee_payment.student else None,
                'admission_number': txn.fee_payment.student.adm_no if txn.fee_payment.student else None
            } if txn and hasattr(txn, 'fee_payment') and txn.fee_payment.student else None,
            'created_at': txn.created_at.isoformat() if txn else timezone.now().isoformat(),
            'processed_at': txn.processed_at.isoformat() if txn else timezone.now().isoformat(),
            'raw_data': item,
            'saved': True if txn else False
        }
    
    def get_local_transactions(self, start_date=None, end_date=None):
        """Get transactions from local database"""
        queryset = MpesaTransaction.objects.filter(
            status='completed'
        ).order_by('-created_at')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        transactions = []
        for transaction in queryset:
            transactions.append({
                'id': str(transaction.id),
                'phone_number': transaction.phone_number,
                'amount': float(transaction.amount),
                'reference_number': transaction.mpesa_receipt_number or 'N/A',
                'transaction_date': transaction.transaction_date.isoformat() if transaction.transaction_date else transaction.created_at.isoformat(),
                'status': transaction.status,
                'transaction_type': transaction.transaction_type,
                'merchant_request_id': transaction.merchant_request_id,
                'checkout_request_id': transaction.checkout_request_id,
                'response_description': transaction.response_description,
                'student': {
                    'id': transaction.fee_payment.student.id,
                    'name': f"{transaction.fee_payment.student.first_name} {transaction.fee_payment.student.last_name}" if transaction.fee_payment.student else None,
                    'admission_number': transaction.fee_payment.student.admission_number if transaction.fee_payment.student else None
                } if transaction.fee_payment.student else None,
                'created_at': transaction.created_at.isoformat(),
                'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None
            })
        
        return transactions
    
    def search_transactions(self, query=None, phone_number=None, reference=None, 
                          start_date=None, end_date=None, status=None):
        """Search transactions with various filters"""
        queryset = MpesaTransaction.objects.all().order_by('-created_at')
        
        if query:
            queryset = queryset.filter(
                models.Q(phone_number__icontains=query) |
                models.Q(mpesa_receipt_number__icontains=query) |
                models.Q(response_description__icontains=query)
            )
        
        if phone_number:
            queryset = queryset.filter(phone_number__icontains=phone_number)
        
        if reference:
            queryset = queryset.filter(mpesa_receipt_number__icontains=reference)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        if status:
            queryset = queryset.filter(status=status)
        
        transactions = []
        for transaction in queryset:
            transactions.append({
                'id': str(transaction.id),
                'phone_number': transaction.phone_number,
                'amount': float(transaction.amount),
                'reference_number': transaction.mpesa_receipt_number or 'N/A',
                'transaction_date': transaction.transaction_date.isoformat() if transaction.transaction_date else transaction.created_at.isoformat(),
                'status': transaction.status,
                'transaction_type': transaction.transaction_type,
                'student': {
                    'id': transaction.fee_payment.student.id,
                    'name': f"{transaction.fee_payment.student.first_name} {transaction.fee_payment.student.last_name}" if transaction.fee_payment.student else None,
                    'admission_number': transaction.fee_payment.student.admission_number if transaction.fee_payment.student else None
                } if transaction.fee_payment.student else None,
                'created_at': transaction.created_at.isoformat(),
                'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None
            })
        
        return transactions
    
    def get_transaction_statistics(self, start_date=None, end_date=None):
        """Get transaction statistics for a given period"""
        queryset = MpesaTransaction.objects.filter(status='completed')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        total_amount = queryset.aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        total_count = queryset.count()
        
        # Group by status
        status_counts = queryset.values('status').annotate(
            count=models.Count('id')
        ).order_by('status')
        
        # Group by transaction type
        type_counts = queryset.values('transaction_type').annotate(
            count=models.Count('id'),
            total_amount=models.Sum('amount')
        ).order_by('transaction_type')
        
        return {
            'total_amount': float(total_amount),
            'total_count': total_count,
            'status_breakdown': list(status_counts),
            'type_breakdown': list(type_counts)
        }
