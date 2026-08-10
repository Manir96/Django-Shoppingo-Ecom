"""Production My Account views — dashboard, orders, downloads, addresses, payments, profile."""
from __future__ import annotations

import re
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.account_services import (
    can_cancel_order,
    cancel_order,
    create_notification,
    dashboard_stats,
    default_checkout_address,
    get_owned_completed_order,
    profile_completion,
    recommended_products,
    reorder_to_cart,
    set_default_address,
    time_greeting,
    user_orders_qs,
    validate_address_payload,
)
from accounts.models import CustomUser
from shopingo.models import (
    AccountNotification,
    DigitalDownload,
    Order,
    RecentlyViewed,
    SavedPaymentMethod,
    ShippingAddress,
    SupportTicket,
    SupportTicketReply,
)

LOGIN_URL = "customer_login"


def _avatar_url(user):
    if getattr(user, "avatar", None) and user.avatar:
        return user.avatar.url
    return None


def _shell_ctx(request, active_tab, **extra):
    """Shared premium shell context for account pages."""
    return {
        "active_tab": active_tab,
        "avatar_url": _avatar_url(request.user),
        "stats": dashboard_stats(request.user),
        "unread_notifications": AccountNotification.objects.filter(
            user=request.user, is_read=False
        ).count(),
        "use_premium_shell": True,
        **extra,
    }


@login_required(login_url=LOGIN_URL)
def account_dashboard(request):
    user = request.user
    stats = dashboard_stats(user)
    recent_orders = user_orders_qs(user)[:6]
    recent_views = (
        RecentlyViewed.objects.filter(user=user)
        .select_related("product")
        .prefetch_related("product__images")[:8]
    )
    notifications = AccountNotification.objects.filter(user=user)[:6]
    unread = AccountNotification.objects.filter(user=user, is_read=False).count()
    open_tickets = SupportTicket.objects.filter(
        user=user, status__in=[SupportTicket.STATUS_OPEN, SupportTicket.STATUS_PENDING]
    ).count()
    return render(
        request,
        "accounts/account-dashboard.html",
        {
            "active_tab": "dashboard",
            "stats": stats,
            "recent_orders": recent_orders,
            "recent_views": recent_views,
            "notifications": notifications,
            "unread_notifications": unread,
            "avatar_url": _avatar_url(user),
            "greeting": time_greeting(),
            "today": timezone.localtime(),
            "profile_pct": profile_completion(user),
            "member_since": getattr(user, "date_joined", None) or user.last_login,
            "last_login": user.last_login,
            "default_address": default_checkout_address(user),
            "recommended": recommended_products(user, 8),
            "open_tickets": open_tickets,
            "use_premium_shell": True,
        },
    )


@login_required(login_url=LOGIN_URL)
def account_notifications(request):
    qs = AccountNotification.objects.filter(user=request.user)
    if request.method == "POST" and request.POST.get("action") == "read_all":
        qs.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect("account-notifications")
    return render(
        request,
        "accounts/account-notifications.html",
        {
            "active_tab": "notifications",
            "notifications": qs[:50],
            "unread_notifications": qs.filter(is_read=False).count(),
            "avatar_url": _avatar_url(request.user),
            "stats": dashboard_stats(request.user),
            "use_premium_shell": True,
        },
    )


def _user_support_ticket(user, ticket_id: int) -> SupportTicket:
    ticket = get_object_or_404(
        SupportTicket.objects.select_related("order", "order__completion").prefetch_related("replies"),
        id=ticket_id,
        user=user,
    )
    return ticket


@login_required(login_url=LOGIN_URL)
def account_support(request):
    tickets = SupportTicket.objects.filter(user=request.user).select_related("order")
    recent_orders = list(user_orders_qs(request.user)[:20])

    if request.method == "POST":
        action = (request.POST.get("action") or "create").strip()
        if action == "create":
            subject = (request.POST.get("subject") or "").strip()[:200]
            message = (request.POST.get("message") or "").strip()
            category = (request.POST.get("category") or SupportTicket.CAT_OTHER).strip()
            valid_cats = {c[0] for c in SupportTicket.CATEGORY_CHOICES}
            if category not in valid_cats:
                category = SupportTicket.CAT_OTHER
            order_id = request.POST.get("order_id") or ""
            order = None
            if order_id:
                try:
                    order = Order.objects.get(id=int(order_id), user=request.user)
                except (Order.DoesNotExist, ValueError, TypeError):
                    messages.error(request, "Invalid order selected.")
                    return redirect("account-support")

            open_count = SupportTicket.objects.filter(
                user=request.user,
                status__in=[SupportTicket.STATUS_OPEN, SupportTicket.STATUS_PENDING],
            ).count()
            if open_count >= 10:
                messages.error(request, "You already have 10 open tickets. Please wait for a reply or close one.")
                return redirect("account-support")

            recent = (
                SupportTicket.objects.filter(user=request.user)
                .order_by("-created_at")
                .first()
            )
            if recent and (timezone.now() - recent.created_at).total_seconds() < 30:
                messages.error(request, "Please wait a moment before submitting another ticket.")
                return redirect("account-support")

            if len(subject) < 4 or len(message) < 10:
                messages.error(request, "Please enter a clearer subject and message (at least a few words).")
            else:
                ticket = SupportTicket.objects.create(
                    user=request.user,
                    subject=subject,
                    message=message,
                    category=category,
                    order=order,
                )
                SupportTicketReply.objects.create(
                    ticket=ticket,
                    author=request.user,
                    is_staff=False,
                    body=message,
                )
                create_notification(
                    request.user,
                    "Support ticket created",
                    f"We received your ticket #{ticket.id}: {subject}",
                    reverse("account-support-detail", args=[ticket.id]),
                    ntype="system",
                )
                messages.success(request, f"Ticket #{ticket.id} submitted. We’ll get back to you soon.")
                return redirect("account-support-detail", ticket_id=ticket.id)

    status_filter = (request.GET.get("status") or "").strip()
    if status_filter in dict(SupportTicket.STATUS_CHOICES):
        tickets = tickets.filter(status=status_filter)

    return render(
        request,
        "accounts/account-support.html",
        _shell_ctx(
            request,
            "support",
            tickets=list(tickets[:40]),
            recent_orders=recent_orders,
            ticket_categories=SupportTicket.CATEGORY_CHOICES,
            status_filter=status_filter,
            open_count=SupportTicket.objects.filter(
                user=request.user,
                status__in=[SupportTicket.STATUS_OPEN, SupportTicket.STATUS_PENDING],
            ).count(),
        ),
    )


@login_required(login_url=LOGIN_URL)
def account_support_detail(request, ticket_id: int):
    ticket = _user_support_ticket(request.user, ticket_id)
    replies = ticket.replies.select_related("author").all()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "reply":
            if ticket.status == SupportTicket.STATUS_CLOSED:
                messages.error(request, "This ticket is closed. Open a new ticket if you need more help.")
                return redirect("account-support-detail", ticket_id=ticket.id)
            body = (request.POST.get("body") or "").strip()
            if len(body) < 2:
                messages.error(request, "Please enter a reply message.")
            else:
                SupportTicketReply.objects.create(
                    ticket=ticket,
                    author=request.user,
                    is_staff=False,
                    body=body[:5000],
                )
                if ticket.status == SupportTicket.STATUS_RESOLVED:
                    ticket.status = SupportTicket.STATUS_PENDING
                    ticket.save(update_fields=["status", "updated_at"])
                elif ticket.status == SupportTicket.STATUS_OPEN:
                    ticket.status = SupportTicket.STATUS_PENDING
                    ticket.save(update_fields=["status", "updated_at"])
                messages.success(request, "Your reply was sent.")
                return redirect("account-support-detail", ticket_id=ticket.id)

        if action == "close":
            if ticket.user_id != request.user.id:
                raise Http404("Ticket not found.")
            ticket.status = SupportTicket.STATUS_CLOSED
            ticket.save(update_fields=["status", "updated_at"])
            messages.success(request, f"Ticket #{ticket.id} closed.")
            return redirect("account-support")

    return render(
        request,
        "accounts/account-support-detail.html",
        _shell_ctx(
            request,
            "support",
            ticket=ticket,
            replies=replies,
        ),
    )


@login_required(login_url=LOGIN_URL)
def account_orders(request):
    qs = user_orders_qs(request.user)
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(order__order_status__status=status)
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "accounts/account-orders.html",
        _shell_ctx(
            request,
            "orders",
            orders=page,
            page_obj=page,
            status_filter=status,
        ),
    )


@login_required(login_url=LOGIN_URL)
def account_order_detail(request, order_id):
    completed = get_owned_completed_order(request.user, order_id)
    if not completed:
        raise Http404("Order not found.")
    order = completed.order
    items = completed.order_items.select_related("product").prefetch_related("product__images")
    return render(
        request,
        "accounts/account-order-detail.html",
        _shell_ctx(
            request,
            "orders",
            completed=completed,
            order=order,
            items=items,
            payment=getattr(order, "payment", None),
            invoice=getattr(order, "invoice", None),
            can_cancel=can_cancel_order(order),
        ),
    )


@login_required(login_url=LOGIN_URL)
@require_POST
def account_cancel_order(request, order_id):
    completed = get_owned_completed_order(request.user, order_id)
    if not completed:
        raise Http404("Order not found.")
    if cancel_order(completed.order):
        messages.success(request, f"Order #{completed.order_id} has been cancelled.")
    else:
        messages.error(request, "This order can no longer be cancelled.")
    return redirect("account-order-detail", order_id=order_id)


@login_required(login_url=LOGIN_URL)
@require_POST
def account_reorder(request, order_id):
    completed = get_owned_completed_order(request.user, order_id)
    if not completed:
        raise Http404("Order not found.")
    n = reorder_to_cart(request.user, completed)
    messages.success(request, f"{n} item(s) added to your cart.")
    return redirect("shopping-cart")


@login_required(login_url=LOGIN_URL)
def account_downloads(request):
    downloads = (
        DigitalDownload.objects.filter(user=request.user)
        .select_related("product", "order")
        .prefetch_related("product__images")
        .order_by("-created_at")
    )
    return render(
        request,
        "accounts/account-downloads.html",
        _shell_ctx(request, "downloads", downloads=downloads),
    )


@login_required(login_url=LOGIN_URL)
def account_download_file(request, download_id):
    entitlement = get_object_or_404(DigitalDownload, id=download_id, user=request.user)
    if not entitlement.can_download:
        messages.error(request, "This download is expired or the limit has been reached.")
        return redirect("account-downloads")
    entitlement.download_count += 1
    entitlement.last_downloaded_at = timezone.now()
    entitlement.save(update_fields=["download_count", "last_downloaded_at"])
    return FileResponse(
        entitlement.product.digital_file.open("rb"),
        as_attachment=True,
        filename=entitlement.product.digital_file.name.split("/")[-1],
    )


@login_required(login_url=LOGIN_URL)
def account_addresses(request):
    addresses = ShippingAddress.objects.filter(user=request.user)
    shipping = addresses.filter(address_type=ShippingAddress.TYPE_SHIPPING)
    billing = addresses.filter(address_type=ShippingAddress.TYPE_BILLING)
    edit_id = request.GET.get("edit")
    edit_address = None
    if edit_id:
        edit_address = addresses.filter(id=edit_id).first()

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "delete":
            addr = get_object_or_404(ShippingAddress, id=request.POST.get("address_id"), user=request.user)
            addr.delete()
            messages.success(request, "Address deleted.")
            return redirect("account-addresses")
        if action == "set_default":
            addr = get_object_or_404(ShippingAddress, id=request.POST.get("address_id"), user=request.user)
            set_default_address(request.user, addr)
            messages.success(request, "Default address updated.")
            return redirect("account-addresses")

        payload = {
            "first_name": request.POST.get("first_name", "").strip(),
            "last_name": request.POST.get("last_name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
            "country": request.POST.get("country", "").strip(),
            "division": request.POST.get("division", "").strip(),
            "district": request.POST.get("district", "").strip(),
            "zip_code": request.POST.get("zip_code", "").strip(),
            "address1": request.POST.get("address1", "").strip(),
            "address2": request.POST.get("address2", "").strip(),
            "label": request.POST.get("label", "Home").strip() or "Home",
            "address_type": request.POST.get("address_type", ShippingAddress.TYPE_SHIPPING),
        }
        errors = validate_address_payload(payload)
        if payload["address_type"] not in dict(ShippingAddress.TYPE_CHOICES):
            errors.append("Invalid address type.")
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            addr_id = request.POST.get("address_id")
            make_default = request.POST.get("is_default") == "on"
            if addr_id:
                addr = get_object_or_404(ShippingAddress, id=addr_id, user=request.user)
                for k, v in payload.items():
                    setattr(addr, k, v)
                addr.save()
                messages.success(request, "Address updated.")
            else:
                addr = ShippingAddress.objects.create(user=request.user, **payload)
                messages.success(request, "Address added.")
            if make_default or not ShippingAddress.objects.filter(
                user=request.user, address_type=addr.address_type, is_default=True
            ).exclude(pk=addr.pk).exists():
                set_default_address(request.user, addr)
            return redirect("account-addresses")

    return render(
        request,
        "accounts/account-addresses.html",
        _shell_ctx(
            request,
            "addresses",
            shipping_addresses=shipping,
            billing_addresses=billing,
            edit_address=edit_address,
        ),
    )


@login_required(login_url=LOGIN_URL)
def account_payment_methods(request):
    methods = SavedPaymentMethod.objects.filter(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "delete":
            pm = get_object_or_404(
                SavedPaymentMethod, id=request.POST.get("method_id"), user=request.user
            )
            pm.delete()
            messages.success(request, "Payment method removed.")
            return redirect("account-payment-methods")
        if action == "set_default":
            pm = get_object_or_404(
                SavedPaymentMethod, id=request.POST.get("method_id"), user=request.user
            )
            SavedPaymentMethod.objects.filter(user=request.user, is_default=True).update(
                is_default=False
            )
            pm.is_default = True
            pm.save(update_fields=["is_default"])
            messages.success(request, "Default payment method updated.")
            return redirect("account-payment-methods")

        method_type = request.POST.get("method_type", "").strip()
        errors = []
        data = {
            "method_type": method_type,
            "label": request.POST.get("label", "").strip(),
            "is_default": request.POST.get("is_default") == "on",
        }
        if method_type == SavedPaymentMethod.TYPE_CARD:
            number = re.sub(r"\D", "", request.POST.get("card_number", ""))
            if len(number) < 13 or len(number) > 19:
                errors.append("Enter a valid card number.")
            mm = request.POST.get("exp_month", "").strip()
            yy = request.POST.get("exp_year", "").strip()
            if not (mm.isdigit() and 1 <= int(mm) <= 12):
                errors.append("Invalid expiry month.")
            if not (yy.isdigit() and len(yy) in (2, 4)):
                errors.append("Invalid expiry year.")
            data.update(
                {
                    "card_brand": (request.POST.get("card_brand") or "Card").strip()[:40],
                    "last4": number[-4:] if number else "",
                    "exp_month": int(mm) if mm.isdigit() else None,
                    "exp_year": int(yy) if yy.isdigit() else None,
                }
            )
        elif method_type == SavedPaymentMethod.TYPE_PAYPAL:
            email = request.POST.get("paypal_email", "").strip()
            if not email or "@" not in email:
                errors.append("Enter a valid PayPal email.")
            data["paypal_email"] = email
        elif method_type == SavedPaymentMethod.TYPE_BANK:
            bank = request.POST.get("bank_name", "").strip()
            acct = re.sub(r"\D", "", request.POST.get("account_number", ""))
            if not bank:
                errors.append("Bank name is required.")
            if len(acct) < 4:
                errors.append("Enter a valid account number.")
            data.update({"bank_name": bank, "account_last4": acct[-4:] if acct else ""})
        else:
            errors.append("Select a payment method type.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            if data.pop("is_default", False):
                SavedPaymentMethod.objects.filter(user=request.user).update(is_default=False)
                data["is_default"] = True
            elif not methods.exists():
                data["is_default"] = True
            SavedPaymentMethod.objects.create(user=request.user, **data)
            messages.success(request, "Payment method saved (card details are masked).")
            return redirect("account-payment-methods")

    return render(
        request,
        "accounts/account-payment-methods.html",
        _shell_ctx(request, "payments", payment_methods=methods),
    )


@login_required(login_url=LOGIN_URL)
def account_user_details(request):
    user = request.user
    if request.method == "POST":
        errors = []
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        phone = request.POST.get("phone", "").strip()
        gender = request.POST.get("gender", "").strip()
        dob_raw = request.POST.get("date_of_birth", "").strip()

        if not email:
            errors.append("Email is required.")
        elif CustomUser.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            errors.append("This email is already in use.")
        if username and CustomUser.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
            errors.append("This username is already taken.")
        if phone and not re.match(r"^[+]?[\d\s\-()]{8,20}$", phone):
            errors.append("Enter a valid phone number.")

        dob = None
        if dob_raw:
            try:
                dob = datetime.strptime(dob_raw, "%Y-%m-%d").date()
            except ValueError:
                errors.append("Invalid date of birth.")

        avatar = request.FILES.get("avatar")
        if avatar:
            if avatar.size > 2 * 1024 * 1024:
                errors.append("Profile picture must be under 2MB.")
            content = getattr(avatar, "content_type", "") or ""
            if content and not content.startswith("image/"):
                errors.append("Profile picture must be an image file.")

        current_password = request.POST.get("current_password", "")
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")
        changing_pw = bool(current_password or new_password or confirm_password)
        if changing_pw:
            if not (current_password and new_password and confirm_password):
                errors.append("Fill all password fields to change password.")
            elif not user.check_password(current_password):
                errors.append("Current password is incorrect.")
            elif new_password != confirm_password:
                errors.append("New password and confirmation do not match.")
            elif len(new_password) < 8:
                errors.append("New password must be at least 8 characters.")
            elif new_password.isalpha() or new_password.isdigit():
                errors.append("Password should include letters and numbers.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user.first_name = first_name
            user.last_name = last_name
            user.username = username
            user.email = email
            user.phone = phone
            user.gender = gender if gender in dict(CustomUser.GENDER_CHOICES) else ""
            user.date_of_birth = dob
            if avatar:
                user.avatar = avatar
            if changing_pw:
                user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Account details updated successfully.")
            return redirect("account-user-details")

    return render(
        request,
        "accounts/account-user-details.html",
        _shell_ctx(
            request,
            "details",
            gender_choices=CustomUser.GENDER_CHOICES,
        ),
    )


@login_required(login_url=LOGIN_URL)
@require_POST
def account_mark_notifications_read(request):
    AccountNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("account-dashboard")


def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("home")
