from functools import wraps

from django.contrib.auth.views import redirect_to_login


def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            from shopingo.error_views import render_error

            user = request.user
            if not user.is_authenticated:
                # Web UX: send guests to login; still support explicit 401 via render_error
                if request.headers.get("x-requested-with") == "XMLHttpRequest":
                    return render_error(request, 401)
                return redirect_to_login(request.get_full_path(), login_url="customer_login")
            if not user.is_active or not getattr(user, "role", None) or not user.role.is_active:
                return render_error(request, 403)
            if user.role.name not in allowed_roles and "any" not in allowed_roles:
                return render_error(request, 403)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
