# M-Pesa Integration Documentation

This document provides comprehensive information about the M-Pesa integration implemented in the SMS system.

## Overview

The M-Pesa integration supports the following functionalities:
- **STK Push**: Initiate payments from customers to the business
- **Pull Transactions**: Business to Customer (B2C) payments
- **Callback Handling**: Process payment confirmations and results
- **Transaction Tracking**: Monitor payment status and history

## Configuration

### 1. Environment Variables

Add the following variables to your `.env` file:

```bash
# M-Pesa Integration Credentials
MPESA_CONSUMER_KEY=your_consumer_key_here
MPESA_CONSUMER_SECRET=your_consumer_secret_here
MPESA_PASSKEY=your_passkey_here
MPESA_SHORTCODE=your_shortcode_here
MPESA_INITIATOR_NAME=your_initiator_name_here
MPESA_INITIATOR_PASSWORD=your_initiator_password_here
MPESA_SECURITY_CREDENTIAL=your_security_credential_here
MPESA_CALLBACK_URL=http://127.0.0.1:8000/accounts/mpesa/callback/
MPESA_RESULT_URL=http://127.0.0.1:8000/accounts/mpesa/result/
MPESA_QUEUE_TIMEOUT_URL=http://127.0.0.1:8000/accounts/mpesa/timeout/
MPESA_ENVIRONMENT=sandbox  # sandbox or production
```

### 2. Getting M-Pesa Credentials

#### For Sandbox Environment:
1. Visit [Safaricom Developer Portal](https://developer.safaricom.co.ke/)
2. Create an account and log in
3. Create a new app
4. Get the Consumer Key and Consumer Secret
5. Use the sandbox credentials provided by Safaricom

#### For Production Environment:
1. Apply for production access through your Safaricom account manager
2. Provide required business documentation
3. Receive production credentials
4. Configure your short code and security credentials

## API Endpoints

### STK Push
- **URL**: `/accounts/mpesa/stk-push/`
- **Method**: POST
- **Purpose**: Initiate customer payment via STK push

**Request Body**:
```json
{
    "phone_number": "254712345678",
    "amount": "100.00",
    "account_reference": "Student Fee Payment",
    "transaction_desc": "Fee Payment",
    "student_id": 123,
    "payment_id": 456
}
```

**Response**:
```json
{
    "success": true,
    "transaction_id": "uuid-string",
    "merchant_request_id": "merchant-request-id",
    "checkout_request_id": "checkout-request-id",
    "customer_message": "Success. Request accepted for processing"
}
```

### Pull Transaction (B2C)
- **URL**: `/accounts/mpesa/pull/`
- **Method**: POST
- **Purpose**: Send money from business to customer

**Request Body**:
```json
{
    "receiver_party": "254712345678",
    "receiver_id": 123,
    "amount": "100.00",
    "remarks": "Salary Payment",
    "occasion": "Monthly Salary"
}
```

### Transaction Status
- **URL**: `/accounts/mpesa/transaction/<uuid:transaction_id>/`
- **Method**: GET
- **Purpose**: Check transaction status

**Response**:
```json
{
    "success": true,
    "transaction": {
        "id": "uuid-string",
        "transaction_type": "stk_push",
        "phone_number": "254712345678",
        "amount": "100.00",
        "status": "completed",
        "mpesa_receipt_number": "OEI2V5W6X1",
        "created_at": "2024-01-01T10:00:00Z",
        "processed_at": "2024-01-01T10:05:00Z"
    }
}
```

### Transaction History
- **URL**: `/accounts/mpesa/history/`
- **Method**: GET
- **Purpose**: Get user's transaction history

## Callback Handling

The system handles three types of callbacks:

### 1. STK Push Callback
- **URL**: `/accounts/mpesa/callback/`
- **Purpose**: Handle STK push payment confirmations

### 2. B2C Result Callback
- **URL**: `/accounts/mpesa/result/`
- **Purpose**: Handle pull transaction results

### 3. Timeout Callback
- **URL**: `/accounts/mpesa/timeout/`
- **Purpose**: Handle transaction timeouts

## Database Models

### MpesaTransaction
Tracks all M-Pesa transactions with the following fields:
- `id`: UUID primary key
- `transaction_type`: STK push, pull, B2C, B2B
- `phone_number`: Customer phone number
- `amount`: Transaction amount
- `status`: pending, completed, failed, cancelled
- M-Pesa specific fields (merchant_request_id, checkout_request_id, etc.)
- Related objects (student, staff, payment records)

### MpesaCallback
Stores all callback data for audit and debugging purposes.

### MpesaAccessToken
Caches OAuth access tokens to avoid frequent API calls.

## Testing

### Test Interface
Visit `/accounts/mpesa/test/` to access the testing interface.

### Test Features:
- STK Push testing with form interface
- Pull transaction testing
- Transaction status checking
- Real-time response display

### Testing Process:
1. Configure sandbox credentials
2. Visit the test page
3. Fill in test phone number (use sandbox test numbers)
4. Enter test amount (minimum KES 1)
5. Submit and monitor results
6. Check transaction status using returned UUID

## Security Considerations

1. **HTTPS Required**: All M-Pesa callbacks require HTTPS in production
2. **IP Whitelisting**: Configure IP whitelisting for callback URLs
3. **Webhook Security**: Validate callback authenticity
4. **Data Protection**: Encrypt sensitive payment data
5. **Rate Limiting**: Implement rate limiting for API endpoints

## Error Handling

The system handles various error scenarios:
- Network timeouts
- Invalid phone numbers
- Insufficient funds
- M-Pesa service unavailability
- Invalid credentials

## Integration Examples

### Student Fee Payment
```python
# Create STK push for student fee
mpesa_service = MpesaService()
result = mpesa_service.stk_push(
    phone_number="254712345678",
    amount=15000.00,
    account_reference=f"STUDENT-{student.id}-TERM-{term.id}",
    transaction_desc="School Fee Payment"
)
```

### Staff Salary Payment
```python
# Create pull transaction for salary
mpesa_service = MpesaService()
result = mpesa_service.pull_transaction(
    receiver_party="254712345678",
    amount=50000.00,
    remarks="Monthly Salary",
    occasion="Salary Payment"
)
```

## Troubleshooting

### Common Issues:
1. **Invalid Credentials**: Verify consumer key and secret
2. **Callback Failures**: Check URL accessibility and HTTPS
3. **Timeout Issues**: Verify network connectivity
4. **Invalid Phone Format**: Ensure 254 prefix for Kenyan numbers

### Debugging:
1. Check Django logs for detailed error messages
2. Monitor M-Pesa callback responses
3. Verify transaction status in database
4. Test with sandbox environment first

## Production Deployment

1. **Environment Setup**: Use production credentials
2. **HTTPS Configuration**: Install SSL certificate
3. **Firewall Rules**: Allow M-Pesa server access
4. **Monitoring**: Set up transaction monitoring
5. **Backup Strategy**: Regular database backups

## Support

For M-Pesa API issues:
- Safaricom Developer Documentation
- M-Pesa API Support Portal
- Technical support contacts

For application issues:
- Check application logs
- Review database status
- Verify configuration settings
