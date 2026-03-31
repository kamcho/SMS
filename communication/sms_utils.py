import requests
import logging
from django.conf import settings
from .models import SMSLog

logger = logging.getLogger(__name__)

class TextSMSAPI:
    def __init__(self):
        self.api_key = settings.TEXT_SMS_API_KEY
        self.partner_id = settings.TEXT_SMS_PARTNER_ID
        self.shortcode = settings.TEXT_SMS_SHORTCODE
        self.single_url = "https://sms.textsms.co.ke/api/services/sendsms/"
        self.bulk_url = "https://sms.textsms.co.ke/api/services/sendbulk/"

    def format_mobile(self, mobile):
        """Format number to 254..."""
        if not mobile:
            return ""
        mobile = str(mobile).strip().replace(" ", "").replace("+", "").replace("-", "")
        if mobile.startswith("07"):
            return "254" + mobile[1:]
        if mobile.startswith("01"):
             return "254" + mobile[1:]
        if mobile.startswith("7") or mobile.startswith("1"):
             if len(mobile) == 9:
                return "254" + mobile
        return mobile

    def send_sms(self, mobile, message, notification=None):
        formatted_mobile = self.format_mobile(mobile)
        if not formatted_mobile:
            return False, "Invalid mobile number"

        payload = {
            "apikey": self.api_key,
            "partnerID": self.partner_id,
            "message": message,
            "shortcode": self.shortcode,
            "mobile": formatted_mobile
        }
        
        sms_log = SMSLog.objects.create(
            recipient=formatted_mobile,
            message=message,
            notification=notification,
            status='Pending'
        )
        
        try:
            response = requests.post(self.single_url, json=payload, timeout=15)
            result = response.json()
            
            # The API returns responses as a list
            if 'responses' in result and len(result['responses']) > 0:
                api_res = result['responses'][0]
                code = api_res.get('response-code', api_res.get('respose-code'))
                desc = api_res.get('response-description', '')
                
                sms_log.response_code = str(code)
                sms_log.response_description = desc
                sms_log.message_id = api_res.get('messageid')
                
                # Treat '200' as success, or fallback to the text snippet
                if str(code) == "200" or "success" in str(desc).lower():
                    sms_log.status = 'Success'
                else:
                    sms_log.status = 'Failed'
            else:
                sms_log.status = 'Failed'
                sms_log.response_description = f"Unexpected response format: {response.text}"
                
        except Exception as e:
            logger.error(f"TextSMS send_sms error: {e}")
            sms_log.status = 'Failed'
            sms_log.response_description = str(e)
            
        sms_log.save()
        return sms_log.status == 'Success', sms_log.response_description

    def get_balance(self):
        payload = {
            "apikey": self.api_key,
            "partnerID": self.partner_id
        }
        try:
            response = requests.post("https://sms.textsms.co.ke/api/services/getbalance/", json=payload, timeout=10)
            # The API might be using a different key or format, but based on common SMS APIs in Kenya
            result = response.json()
            # If it's a list, handle it
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('credit', '0')
            return result.get('credit', '0')
        except Exception as e:
            logger.error(f"TextSMS get_balance error: {e}")
            return "N/A"
