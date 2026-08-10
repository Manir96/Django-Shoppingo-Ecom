from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import *
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .decorators import role_required
import random
from django.core.mail import send_mail
from django.conf import settings
from .models import PasswordResetCode, CustomUser, CountryName
from django.contrib.auth import get_user_model

# Re-export My Account views
from .account_views import (  # noqa: F401
    account_addresses,
    account_cancel_order,
    account_dashboard,
    account_download_file,
    account_downloads,
    account_mark_notifications_read,
    account_notifications,
    account_order_detail,
    account_orders,
    account_payment_methods,
    account_reorder,
    account_support,
    account_support_detail,
    account_user_details,
    user_logout,
)

User = get_user_model()


def customer_register(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(
                request,
                "Registration successful — welcome, {}!".format(user.first_name or user.email),
            )
            return redirect('customer_login')
        messages.error(request, "There were errors in your registration form. Please fix them and try again.")
    else:
        form = CustomerRegistrationForm()
    countries = CountryName.objects.all()
    return render(
        request,
        'accounts/customer_register.html',
        {'form': form, 'countries': countries},
    )


def customer_login(request):
    if request.method == 'POST':
        form = CustomerLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, email=email, password=password)
            if user is not None and user.role and user.role.name == 'customer':
                login(request, user)
                messages.success(request, f"Welcome {user.get_full_name()}!")
                next_url = request.GET.get('next') or 'account-dashboard'
                return redirect(next_url)
            messages.error(request, "Invalid credentials or not a customer account.")
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = CustomerLoginForm()
    return render(request, 'accounts/customer_login.html', {'form': form})


@login_required
@role_required(['customer'])
def customer_dashboard(request):
    return redirect('account-dashboard')


@login_required
@role_required(['seller'])
def seller_dashboard(request):
    return render(request, 'accounts/seller_dashboard.html')


@login_required
@role_required(['admin', 'superadmin'])
def admin_dashboard(request):
    return render(request, 'accounts/admin_dashboard.html')


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        if User.objects.filter(email=email).exists():
            code = str(random.randint(100000, 999999))
            PasswordResetCode.objects.create(email=email, code=code)
            send_mail(
                "Password Reset Code",
                f"Your reset code is {code}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=True,
            )
            request.session['reset_email'] = email
            return redirect("verify_code")
        messages.error(request, "Email not registered!")
    return render(request, "accounts/forgot_password.html")


def verify_code(request):
    if request.method == "POST":
        code = request.POST.get("code")
        email = request.session.get('reset_email')
        obj = PasswordResetCode.objects.filter(email=email, code=code).last()
        if obj and obj.is_valid():
            request.session['verified'] = True
            return redirect("reset-password")
        messages.error(request, "Invalid or expired code")
    return render(request, "accounts/verify_code.html")


def reset_password(request):
    if not request.session.get('verified'):
        messages.error(request, "You must verify your code first!")
        return redirect('verify_code')

    if request.method == "POST":
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        email = request.session.get("reset_email")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
        elif not password or len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
        else:
            try:
                user = CustomUser.objects.get(email=email)
                user.set_password(password)
                user.save()
                request.session.pop('verified', None)
                request.session.pop('reset_email', None)
                messages.success(request, "Password reset successfully!")
                return redirect("customer_login")
            except CustomUser.DoesNotExist:
                messages.error(request, "User not found")

    return render(request, "accounts/reset_password.html")
