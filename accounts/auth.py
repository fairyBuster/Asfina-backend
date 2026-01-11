from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class PhoneOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows login with either phone or username.
    - Admin users: login with username
    - Regular users: login with phone
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        # For admin interface, always try username first
        if request and request.path.startswith('/admin/'):
            try:
                user = User.objects.get(username=username)
                if user.check_password(password):
                    return user
            except User.DoesNotExist:
                return None
        
        # For API/regular users, try phone number
        try:
            user = User.objects.get(phone=username)
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            return None
            
        return None
