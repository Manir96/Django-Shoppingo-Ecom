from django.shortcuts import render, redirect
from accounts.models import *
from django.contrib import messages
from .forms import *
from django.contrib.auth import *
from django.contrib.auth.decorators import login_required
from .decorators import role_required
from django.views.decorators.csrf import csrf_exempt
import random
from django.core.mail import send_mail
from django.contrib.auth.models import User
from .models import PasswordResetCode
from django.conf import settings




def account_addresses(request):
    return render(request, 'accounts/account-addresses.html')

def account_dashboard(request):
    return render(request, 'accounts/account-dashboard.html')

def account_downloads(request):
    return render(request, 'accounts/account-downloads.html')

def account_payment_methods(request):
    return render(request, 'accounts/account-payment-methods.html')

def account_user_details(request):
    return render(request, 'accounts/account-user-details.html')

def account_orders(request):
    return render(request, 'accounts/account-orders.html')


@csrf_exempt
def customer_register(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # login(request, user)  # direct login
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, "Registration successful — welcome, {}!".format(user.first_name or user.email))
            return redirect('customer_login')
        else:
            messages.error(request, "There were errors in your registration form. Please fix them and try again.")
    else:
        form = CustomerRegistrationForm()
    countries = CountryName.objects.all()
    context = {
        'form': form,
        'countries': countries,
    }
    return render(request, 'accounts/customer_register.html', context)


def customer_login(request):
    if request.method == 'POST':
        form = CustomerLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')  # email
            password = form.cleaned_data.get('password')
            user = authenticate(request, email=email, password=password)
            if user is not None and user.role.name == 'customer':
                login(request, user)
                messages.success(request, f"Welcome {user.first_name}!")
                return redirect('account-dashboard')  # redirect to products page
            else:
                messages.error(request, "Invalid credentials or not a customer account.")
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = CustomerLoginForm()
    return render(request, 'accounts/customer_login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('home')




# Dashboards
@login_required
@role_required(['customer'])
def customer_dashboard(request):
    return render(request, 'accounts/customer_dashboard.html')


@login_required
@role_required(['seller'])
def seller_dashboard(request):
    return render(request, 'accounts/seller_dashboard.html')


@login_required
@role_required(['admin', 'superadmin'])
def admin_dashboard(request):
    return render(request, 'accounts/admin_dashboard.html')

from django.contrib.auth import get_user_model
User = get_user_model()

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")
        print("Email received:", email)
        if User.objects.filter(email=email).exists():
            code = str(random.randint(100000, 999999))  # 6 digit OTP
            PasswordResetCode.objects.create(email=email, code=code)
            
            send_mail(
                "Password Reset Code",
                f"Your reset code is {code}",
                settings.DEFAULT_FROM_EMAIL,  # এখানে settings থেকে নিতে ভালো
                [email],
            )

            request.session['reset_email'] = email
            return redirect("verify_code")
        else:
            messages.error(request, "Email not registered!")
    return render(request, "accounts/forgot_password.html")

def verify_code(request):
    if request.method == "POST":
        code = request.POST.get("code")
        email = request.session.get('reset_email')
        try:
            obj = PasswordResetCode.objects.filter(email=email, code=code).last()
            if obj and obj.is_valid():
                request.session['verified'] = True
                return redirect("reset-password")
            else:
                messages.error(request, "Invalid or expired code")
        except:
            messages.error(request, "Something went wrong")
    return render(request, "accounts/verify_code.html")


def reset_password(request):
    if not request.session.get('verified'):
        messages.error(request, "You must verify your code first!")
        return redirect('accounts/verify_code')

    if request.method == "POST":
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        email = request.session.get("reset_email")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
        else:
            try:
                user = CustomUser.objects.get(email=email)
                user.set_password(password)
                user.save()

                # Clear session
                request.session.pop('verified', None)
                request.session.pop('reset_email', None)

                messages.success(request, "Password reset successfully!")
                return redirect("customer_login")  
            except CustomUser.DoesNotExist:
                messages.error(request, "User not found")

    
    return render(request, "accounts/reset_password.html")



@login_required
def account_user_details(request):
    if request.method == "POST":
        user = request.user
        user.first_name = request.POST.get("first_name")
        user.last_name = request.POST.get("last_name")
        user.email = request.POST.get("email")

        # Password change
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        if current_password or new_password or confirm_password:
            if not user.check_password(current_password):
                messages.error(request, "Current password is incorrect")
            elif new_password != confirm_password:
                messages.error(request, "New passwords do not match")
            else:
                user.set_password(new_password)
                user.save()
                update_session_auth_hash(request, user)  # stay logged in
                messages.success(request, "Password changed successfully!")
                return redirect("account-user-details")

        user.save()
        messages.success(request, "Account details updated successfully!")
        return redirect("account-user-details")

    return render(request, "accounts/account-user-details.html")


