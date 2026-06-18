from django.conf import settings
from django.http import JsonResponse


def status(request):
    return JsonResponse({"ok": True, "version": settings.APP_VERSION})
