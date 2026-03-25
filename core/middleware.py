import logging
from django.shortcuts import render

logger = logging.getLogger(__name__)

class GlobalErrorHandlingMiddleware:
    """
    Middleware to catch all unhandled exceptions and render a friendly error page,
    ensuring the user is always informed that the issue is being fixed.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            if response.status_code >= 400:
                context = {
                    'status_code': response.status_code,
                    'is_404': response.status_code == 404,
                }
                return render(request, 'core/error.html', context, status=response.status_code)
            return response
        except Exception as e:
            logger.error(f"Unhandled exception caught by middleware: {e}", exc_info=True)
            return render(request, 'core/error.html', status=500)

    def process_exception(self, request, exception):
        logger.error(f"process_exception caught: {exception}", exc_info=True)
        return render(request, 'core/error.html', status=500)
