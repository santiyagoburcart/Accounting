import re

class MobileRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # پترن‌های تشخیص موبایل (iPhone, Android, Mobile)
        self.mobile_agent_re = re.compile(r".*(iphone|mobile|android|androidtouch).*", re.IGNORECASE)

    def __call__(self, request):
        # تشخیص موبایل از روی User-Agent
        if self.mobile_agent_re.match(request.META.get('HTTP_USER_AGENT', '')):
            request.is_mobile = True
        else:
            request.is_mobile = False

        response = self.get_response(request)
        return response


class MobileDetectionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # تشخیص ساده بر اساس User-Agent
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        mobile_agents = ['mobile', 'android', 'iphone', 'ipad', 'phone']

        # ست کردن متغیر is_mobile روی آبجکت request
        request.is_mobile = any(agent in user_agent for agent in mobile_agents)

        return self.get_response(request)