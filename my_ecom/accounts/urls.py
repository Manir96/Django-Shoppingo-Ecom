from django.urls import path
from accounts import views


urlpatterns = [

    path('account-addresses/', views.account_addresses, name='account-addresses'),
    path('account-dashboard/', views.account_dashboard, name='account-dashboard'),
    path('account-downloads/', views.account_downloads, name='account-downloads'),
    path('account-payment-methods/', views.account_payment_methods, name='account-payment-methods'),
    path('account-user-details/', views.account_user_details, name='account-user-details'),
    path('account-orders/', views.account_orders, name='account-orders'),



    path('register/customer/', views.customer_register, name='customer_register'),
    path('login/customer/', views.customer_login, name='customer_login'),
    path('logout/', views.user_logout, name='user_logout'),

    path('forgot-password/customer/', views.forgot_password, name='forgot-password'),
    path("verify-code/", views.verify_code, name="verify_code"),
    path("reset-password/", views.reset_password, name="reset-password"),

    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('dashboard/seller/', views.seller_dashboard, name='seller_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),

    
]