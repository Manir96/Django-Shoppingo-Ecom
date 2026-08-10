from django.urls import path
from accounts import views

urlpatterns = [
    path('account-dashboard/', views.account_dashboard, name='account-dashboard'),
    path('account-orders/', views.account_orders, name='account-orders'),
    path('account-orders/<int:order_id>/', views.account_order_detail, name='account-order-detail'),
    path('account-orders/<int:order_id>/cancel/', views.account_cancel_order, name='account-cancel-order'),
    path('account-orders/<int:order_id>/reorder/', views.account_reorder, name='account-reorder'),
    path('account-downloads/', views.account_downloads, name='account-downloads'),
    path('account-downloads/<int:download_id>/file/', views.account_download_file, name='account-download-file'),
    path('account-addresses/', views.account_addresses, name='account-addresses'),
    path('account-payment-methods/', views.account_payment_methods, name='account-payment-methods'),
    path('account-user-details/', views.account_user_details, name='account-user-details'),
    path('account-notifications/', views.account_notifications, name='account-notifications'),
    path('account-notifications/read/', views.account_mark_notifications_read, name='account-notifications-read'),
    path('account-support/', views.account_support, name='account-support'),
    path('account-support/<int:ticket_id>/', views.account_support_detail, name='account-support-detail'),
    path('logout/', views.user_logout, name='user_logout'),

    path('register/customer/', views.customer_register, name='customer_register'),
    path('login/customer/', views.customer_login, name='customer_login'),
    path('forgot-password/customer/', views.forgot_password, name='forgot-password'),
    path('verify-code/', views.verify_code, name='verify_code'),
    path('reset-password/', views.reset_password, name='reset-password'),

    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('dashboard/seller/', views.seller_dashboard, name='seller_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
]
