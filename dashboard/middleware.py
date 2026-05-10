from django.shortcuts import redirect
from django.conf import settings


class LoginRequiredMiddleware:
    """Redirect all unauthenticated requests to the login page.
    
    This is simpler and safer than decorating every single view function.
    It ensures that NO page can ever be accessed without logging in.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Allow the login page itself and admin to be accessed without auth
        allowed_paths = [settings.LOGIN_URL, '/admin/']
        if not request.user.is_authenticated and not any(request.path.startswith(p) for p in allowed_paths):
            return redirect(settings.LOGIN_URL)
        return self.get_response(request)
