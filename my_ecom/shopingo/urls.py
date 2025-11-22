from django.urls import path
from shopingo import views

urlpatterns = [
    path('', views.home, name='home'),
    path('shop-grid-top/', views.shop_grid_top, name='shop-grid-top'),
    path('shop-grid-left/', views.shop_grid_left_sidebar, name='shop-grid-left'),
    path('shop-grid-list/', views.shop_list_left_sidebar, name='shop-grid-list'),
    path('shop-categories/', views.shop_categories, name='shop-categories'),
    path('product-detail/<slug:slug>/', views.product_detail, name='product-detail'),
    path('product-comparison/', views.product_comparison, name='product-comparison'),
    path('starter-page/', views.starter_page, name='starter-page'),
    
    path('order-tracking/', views.order_tracking, name='order-tracking'),
    path('checkout-shipping/', views.checkout_shipping, name='checkout-shipping'),
    path('checkout-review/', views.checkout_review, name='checkout-review'),
    path('checkout-details/', views.checkout_details, name='checkout-details'),
    path('checkout-payment/', views.checkout_payment, name='checkout-payment'),
    path('checkout-complete/<int:order_id>/', views.checkout_complete, name='checkout-complete'),

    
    path('about/', views.about_page, name='about'),
    path('contact/', views.contact_page, name='contact'),



    path('tag/<slug:slug>/', views.produc_tag_view, name='produc_tag_view'),
    path('category/<slug:slug>/', views.produc_category_view, name='produc_category_view'),
    path('subCategory/<slug:slug>/', views.produc_subCategory_view, name='produc_subCategory_view'),
    
    #modal quick view product
    path('quick-view/<slug:slug>/', views.quick_view_product, name='quick-view-product'),
    
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('remove-coupon/', views.remove_coupon, name='remove_coupon'),
    
    path('shopping-cart/', views.shopping_cart, name='shopping-cart'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path("handle-product-action/", views.handle_product_action, name="handle_product_action"),
    path('remove-cart-item/<int:item_id>/', views.remove_cart_item, name='remove_cart_item'),
    path('delete-order-item/<int:item_id>/', views.delete_order_item, name='delete_order_item'),
    path('remove-to-wishlist/<int:item_id>/', views.remove_to_wishlist, name='remove_to_wishlist'),
    path('update-cart-quantity/', views.update_cart_quantity, name='update_cart_quantity'),

    path("ajax/get-divisions/", views.get_divisions, name="get_divisions"),
    path("ajax/get-districts/", views.get_districts, name="get_districts"),
    
]