from zoneinfo import ZoneInfo
from django.utils import timezone
class Headers:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        from django.http import HttpResponse
        try:length=int(request.META.get('CONTENT_LENGTH') or 0)
        except (ValueError,TypeError):return HttpResponse('Invalid request size.',status=400)
        if length<0:return HttpResponse('Invalid request size.',status=400)
        limit=2300000 if request.path in ['/resume/','/resume/check/'] else 256*1024
        if length>limit:
            from django.http import HttpResponse
            return HttpResponse('Request exceeds the upload limit.',status=413)
        response=self.get_response(request)
        response['Content-Security-Policy']="default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response['Referrer-Policy']='same-origin'
        response['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response['Cache-Control']='no-store'
        return response
class UserTimezone:
    def __init__(self,get_response): self.get_response=get_response
    def __call__(self,request):
        try:
            if request.user.is_authenticated: timezone.activate(ZoneInfo(request.user.profile.timezone))
            return self.get_response(request)
        finally: timezone.deactivate()
