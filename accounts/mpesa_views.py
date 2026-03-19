from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import View
from django.utils import timezone
from django.db import transaction as django_transaction
from django.contrib import messages
from django.db import models
from decimal import Decimal
import json
import logging

from .models import MpesaTransaction, MpesaCallback, Payment, StaffPayment
from .mpesa_service import MpesaService
from core.models import Student

logger = logging.getLogger(__name__)


@login_required
def mpesa_test_view(request):
    """Test view for M-Pesa functionality"""
    return render(request, 'accounts/mpesa_test.html')


class MpesaSTKPushView(LoginRequiredMixin, View):
    """View for initiating STK push payments"""
    
    def post(self, request):
        print("🚀 DEBUG: STK Push view called!")
        print(f"🚀 DEBUG: Request method: {request.method}")
        print(f"🚀 DEBUG: Request body: {request.body}")
        
        try:
            data = json.loads(request.body)
            print(f"📦 DEBUG: Parsed JSON data: {data}")
            
            phone_number = data.get('phone_number')
            amount = data.get('amount')
            account_reference = data.get('account_reference', '')
            transaction_desc = data.get('transaction_desc', 'Payment')
            staff_id = data.get('staff_id')
            payment_id = data.get('payment_id')
            
            print(f"📱 DEBUG: Extracted phone: {phone_number}")
            print(f"💰 DEBUG: Extracted amount: {amount}")
            print(f"📝 DEBUG: Extracted account_ref: {account_reference}")
            print(f"📝 DEBUG: Extracted transaction_desc: {transaction_desc}")
            print(f"👤 DEBUG: Extracted staff_id: {staff_id}")
            print(f"💳 DEBUG: Extracted payment_id: {payment_id}")
            
            # Validate required fields
            if not phone_number or not amount:
                print("❌ DEBUG: Missing required fields")
                return JsonResponse({
                    'success': False,
                    'error': 'Phone number and amount are required'
                }, status=400)
            
            # Clean phone number (remove spaces, +, etc.)
            phone_number = phone_number.replace(' ', '').replace('+', '')
            if not phone_number.startswith('254'):
                phone_number = '254' + phone_number[-9:] if len(phone_number) >= 9 else phone_number
            
            print(f"📱 DEBUG: Cleaned phone number: {phone_number}")
            
            # Create transaction record
            mpesa_transaction = MpesaTransaction.objects.create(
                transaction_type='stk_push',
                phone_number=phone_number,
                amount=Decimal(str(amount)),
                status='pending'
            )
            
            print(f"💾 DEBUG: Created transaction: {mpesa_transaction.id}")
            
            # Link from relevant models if provided
            if staff_id:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    staff = User.objects.get(id=staff_id)
                    # For B2C we usually link staff to txn, but for STK push 
                    # we might not have a model yet unless it's a specific business flow.
                    # If there's no model to link FROM, we might need a generic link or just rely on logs.
                    # However, if this is a salary payment:
                    staff_payment = StaffPayment.objects.filter(staff=staff, mpesa_transaction__isnull=True).first()
                    if staff_payment:
                        staff_payment.mpesa_transaction = mpesa_transaction
                        staff_payment.save()
                        print(f"👤 DEBUG: Linked to staff payment: {staff_payment.id}")
                except Exception as e:
                    print(f"⚠️ DEBUG: Error linking staff: {str(e)}")
            
            if payment_id:
                try:
                    payment = Payment.objects.get(id=payment_id)
                    payment.mpesa_transaction = mpesa_transaction
                    payment.save()
                    print(f"💳 DEBUG: Linked from payment: {payment.id}")
                except Payment.DoesNotExist:
                    print(f"⚠️ DEBUG: Payment not found: {payment_id}")
            
            print(f"💾 DEBUG: Transaction saved")
            
            # Initiate STK push
            mpesa_service = MpesaService()
            callback_url = request.build_absolute_uri('/accounts/mpesa/callback/')
            print(f"🔗 DEBUG: Generated callback URL: {callback_url}")
            
            result = mpesa_service.stk_push(
                phone_number=phone_number,
                amount=amount,
                account_reference=account_reference or f"TXN-{mpesa_transaction.id}",
                transaction_desc=transaction_desc,
                callback_url=callback_url
            )
            
            print(f"📡 DEBUG: STK Push service result: {result}")
            
            if result['success']:
                # Update transaction with M-Pesa response
                mpesa_transaction.merchant_request_id = result.get('merchant_request_id')
                mpesa_transaction.checkout_request_id = result.get('checkout_request_id')
                mpesa_transaction.response_code = result.get('response_code')
                mpesa_transaction.response_description = result.get('response_description')
                mpesa_transaction.save()
                
                print(f"✅ DEBUG: Transaction updated with M-Pesa response")
                
                return JsonResponse({
                    'success': True,
                    'transaction_id': str(mpesa_transaction.id),
                    'merchant_request_id': result.get('merchant_request_id'),
                    'checkout_request_id': result.get('checkout_request_id'),
                    'customer_message': result.get('customer_message')
                })
            else:
                mpesa_transaction.status = 'failed'
                mpesa_transaction.response_description = result.get('error')
                mpesa_transaction.save()
                
                print(f"❌ DEBUG: Transaction marked as failed")
                
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Unknown error occurred')
                }, status=400)
                
        except json.JSONDecodeError as e:
            print(f"❌ DEBUG: JSON decode error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
        except Exception as e:
            print(f"🚨 DEBUG: Unexpected error: {str(e)}")
            import traceback
            print(f"🚨 DEBUG: Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=500)


class MpesaB2CView(LoginRequiredMixin, View):
    """View for initiating B2C transactions (Business to Customer)"""
    
    def post(self, request):
        print("💼 DEBUG: B2C Pull view called!")
        print(f"💼 DEBUG: Request method: {request.method}")
        print(f"💼 DEBUG: Request body: {request.body}")
        
        try:
            data = json.loads(request.body)
            print(f"📦 DEBUG: Parsed JSON data: {data}")
            
            receiver_party = data.get('receiver_party')
            receiver_id = data.get('receiver_id')  # Staff ID
            amount = data.get('amount')
            remarks = data.get('remarks', 'Payment')
            occasion = data.get('occasion', '')
            
            print(f"👤 DEBUG: Receiver party: {receiver_party}")
            print(f"🆔 DEBUG: Receiver ID: {receiver_id}")
            print(f"💰 DEBUG: Amount: {amount}")
            print(f"📝 DEBUG: Remarks: {remarks}")
            print(f"🎉 DEBUG: Occasion: {occasion}")
            
            # Validate required fields
            if not receiver_party or not receiver_id or not amount:
                print("❌ DEBUG: Missing required fields")
                return JsonResponse({
                    'success': False,
                    'error': 'Receiver party, receiver ID, and amount are required'
                }, status=400)
            
            # Create transaction record
            mpesa_transaction = MpesaTransaction.objects.create(
                transaction_type='b2c',
                phone_number=receiver_party,
                amount=Decimal(str(amount)),
                status='pending'
            )
            
            print(f"💾 DEBUG: Created B2C transaction: {mpesa_transaction.id}")
            
            # Link from staff payment if provided
            if receiver_id:
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    staff = User.objects.get(id=receiver_id)
                    staff_payment = StaffPayment.objects.filter(staff=staff, mpesa_transaction__isnull=True).first()
                    if staff_payment:
                        staff_payment.mpesa_transaction = mpesa_transaction
                        staff_payment.save()
                        print(f"👤 DEBUG: Linked from staff payment: {staff_payment.id}")
                except Exception as e:
                    print(f"🚨 DEBUG: Error linking staff: {str(e)}")
            
            mpesa_transaction.save()
            print(f"💾 DEBUG: B2C transaction saved")
            
            # Initiate B2C transaction
            mpesa_service = MpesaService()
            result = mpesa_service.pull_transaction(
                receiver_party=receiver_party,
                receiver_id=receiver_id,
                amount=amount,
                remarks=remarks,
                occasion=occasion
            )
            
            print(f"📡 DEBUG: B2C service result: {result}")
            
            if result['success']:
                # Update transaction with M-Pesa response
                mpesa_transaction.response_code = result.get('response_code')
                mpesa_transaction.response_description = result.get('response_description')
                mpesa_transaction.save()
                
                print(f"✅ DEBUG: B2C transaction updated with M-Pesa response")
                
                return JsonResponse({
                    'success': True,
                    'transaction_id': str(mpesa_transaction.id),
                    'conversation_id': result.get('conversation_id'),
                    'originator_conversation_id': result.get('originator_conversation_id'),
                    'response_description': result.get('response_description')
                })
            else:
                mpesa_transaction.status = 'failed'
                mpesa_transaction.response_description = result.get('error')
                mpesa_transaction.save()
                
                print(f"❌ DEBUG: B2C transaction marked as failed")
                
                return JsonResponse({
                    'success': False,
                    'error': result.get('error', 'Unknown error occurred'),
                    'error_code': result.get('response_code', 'UNKNOWN')
                }, status=400)
                
        except json.JSONDecodeError as e:
            print(f"❌ DEBUG: JSON decode error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data',
                'error_code': 'JSON_DECODE_ERROR'
            }, status=400)
        except Exception as e:
            print(f"🚨 DEBUG: Unexpected error: {str(e)}")
            import traceback
            print(f"🚨 DEBUG: Traceback: {traceback.format_exc()}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred',
                'error_code': 'UNEXPECTED_ERROR'
            }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_callback(request):
    """Handle M-Pesa callback for STK push"""
    print("🔔 DEBUG: M-Pesa callback received!")
    print(f"🔔 DEBUG: Request method: {request.method}")
    print(f"🔔 DEBUG: Request headers: {dict(request.headers)}")
    print(f"🔔 DEBUG: Request body: {request.body}")
    
    try:
        callback_data = json.loads(request.body)
        print(f"📦 DEBUG: Parsed callback JSON successfully")
        
        # Process the callback
        mpesa_service = MpesaService()
        result = mpesa_service.process_callback(callback_data, 'success')
        
        print(f"✅ DEBUG: Callback processed result: {result}")
        
        if result['success']:
            # If transaction was successful, update related payment records
            transaction_id = result.get('transaction_id')
            if transaction_id:
                try:
                    transaction = MpesaTransaction.objects.get(id=transaction_id)
                    
                    if transaction.status == 'completed':
                        # Update student payment if linked via reverse relation
                        if hasattr(transaction, 'fee_payment'):
                            payment = transaction.fee_payment
                            payment.payment_method = 'Mpesa'
                            payment.reference = transaction.mpesa_receipt_number
                            payment.save()
                            print(f"💳 DEBUG: Updated student payment {payment.id}")
                        
                        # Update staff payment if linked via reverse relation
                        if hasattr(transaction, 'salary_payment'):
                            staff_payment = transaction.salary_payment
                            staff_payment.payment_method = 'Mpesa'
                            staff_payment.reference = transaction.mpesa_receipt_number
                            staff_payment.save()
                            print(f"💼 DEBUG: Updated staff payment {staff_payment.id}")
                        
                        logger.info(f"Successfully processed M-Pesa callback for transaction {transaction_id}")
                except MpesaTransaction.DoesNotExist:
                    logger.error(f"Transaction not found: {transaction_id}")
        
        return JsonResponse({'result': result}, status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in M-Pesa callback")
        print("❌ DEBUG: Invalid JSON in callback")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing M-Pesa callback: {str(e)}")
        print(f"🚨 DEBUG: Error processing callback: {str(e)}")
        import traceback
        print(f"🚨 DEBUG: Traceback: {traceback.format_exc()}")
        return JsonResponse({'error': 'Processing error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_result(request):
    """Handle M-Pesa result for pull transactions"""
    try:
        result_data = json.loads(request.body)
        
        # Store the result
        body = result_data.get('Body', {})
        result = body.get('Result', {})
        
        conversation_id = result.get('ConversationID')
        originator_conversation_id = result.get('OriginatorConversationID')
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        
        # Find the transaction
        transaction = MpesaTransaction.objects.filter(
            response_description__contains=conversation_id
        ).first()
        
        if transaction:
            # Store callback data
            MpesaCallback.objects.create(
                transaction=transaction,
                callback_type='result',
                raw_data=result_data
            )
            
            # Update transaction status
            if result_code == '0':
                transaction.status = 'completed'
                transaction.response_code = result_code
                transaction.response_description = result_desc
                transaction.processed_at = timezone.now()
                
                # Update staff payment if linked via reverse relation
                if hasattr(transaction, 'salary_payment'):
                    staff_payment = transaction.salary_payment
                    staff_payment.payment_method = 'Mpesa'
                    staff_payment.reference = conversation_id
                    staff_payment.save()
            else:
                transaction.status = 'failed'
                transaction.response_code = result_code
                transaction.response_description = result_desc
                transaction.processed_at = timezone.now()
            
            transaction.save()
        
        return JsonResponse({'ResultCode': 0}, status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in M-Pesa result")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing M-Pesa result: {str(e)}")
        return JsonResponse({'error': 'Processing error'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mpesa_timeout(request):
    """Handle M-Pesa timeout"""
    try:
        timeout_data = json.loads(request.body)
        
        # Store the timeout
        body = timeout_data.get('Body', {})
        result = body.get('Result', {})
        
        conversation_id = result.get('ConversationID')
        
        # Find and update the transaction
        transaction = MpesaTransaction.objects.filter(
            response_description__contains=conversation_id
        ).first()
        
        if transaction:
            MpesaCallback.objects.create(
                transaction=transaction,
                callback_type='timeout',
                raw_data=timeout_data
            )
            
            transaction.status = 'cancelled'
            transaction.response_description = 'Transaction timed out'
            transaction.processed_at = timezone.now()
            transaction.save()
        
        return JsonResponse({'ResultCode': 0}, status=200)
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in M-Pesa timeout")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error processing M-Pesa timeout: {str(e)}")
        return JsonResponse({'error': 'Processing error'}, status=500)


@login_required
@require_http_methods(["GET"])
def transaction_status(request, transaction_id):
    """Check the status of an M-Pesa transaction"""
    try:
        transaction = get_object_or_404(MpesaTransaction, id=transaction_id)
        
        return JsonResponse({
            'success': True,
            'transaction': {
                'id': str(transaction.id),
                'transaction_type': transaction.transaction_type,
                'phone_number': transaction.phone_number,
                'amount': str(transaction.amount),
                'status': transaction.status,
                'merchant_request_id': transaction.merchant_request_id,
                'checkout_request_id': transaction.checkout_request_id,
                'mpesa_receipt_number': transaction.mpesa_receipt_number,
                'response_description': transaction.response_description,
                'created_at': transaction.created_at.isoformat(),
                'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error checking transaction status: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error checking transaction status'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def transaction_history(request):
    """Get transaction history for the current user"""
    try:
        # Get transactions related to the current user via reverse links
        transactions = MpesaTransaction.objects.filter(
            models.Q(salary_payment__staff=request.user) | 
            models.Q(fee_payment__student__studentprofile__user=request.user)
        ).distinct().order_by('-created_at')
        
        transaction_data = []
        for transaction in transactions:
            transaction_data.append({
                'id': str(transaction.id),
                'transaction_type': transaction.transaction_type,
                'phone_number': transaction.phone_number,
                'amount': str(transaction.amount),
                'status': transaction.status,
                'mpesa_receipt_number': transaction.mpesa_receipt_number,
                'response_description': transaction.response_description,
                'created_at': transaction.created_at.isoformat(),
                'processed_at': transaction.processed_at.isoformat() if transaction.processed_at else None
            })
        
        return JsonResponse({
            'success': True,
            'transactions': transaction_data
        })
        
    except Exception as e:
        logger.error(f"Error getting transaction history: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error getting transaction history'
        }, status=500)
