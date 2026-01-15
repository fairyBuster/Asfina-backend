from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()

class PhoneOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows login with either phone or username.
    - Admin users: login with username
    - Regular users: login with phone
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        admin_base = f"/{getattr(settings, 'ADMIN_URL', 'admin').strip('/')}"
        if request and (request.path == admin_base or request.path.startswith(admin_base + "/")):
            try:
                user = User.objects.get(username=username)
                if user.check_password(password):
                    return user
            except User.DoesNotExist:
                return None
        try:
            user = User.objects.get(phone=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
        return None
