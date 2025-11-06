from functools import wraps
from django.http import HttpResponseForbidden


def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return HttpResponseForbidden('Authentication required')
            # both user and their role must be active
            if not user.is_active or not getattr(user, 'role', None) or not user.role.is_active:
                return HttpResponseForbidden('Your account or role is inactive')
            if user.role.name not in allowed_roles and 'any' not in allowed_roles:
                return HttpResponseForbidden('You do not have permission to access this resource')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

