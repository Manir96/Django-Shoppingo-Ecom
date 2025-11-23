from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import *
from .forms import CustomUserCreationForm, CustomUserChangeForm


@admin.register(CountryName)
class CountryNameAdmin(admin.ModelAdmin):
    list_display = ("nameName",)
    search_fields = ("nameName",)
    ordering = ("nameName",)



@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('id', 'division_name', 'country')
    list_filter = ('country',)
    search_fields = ('division_name', 'country__name')
    ordering = ('country', 'division_name')



@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("district_name", "country", "division")
    list_filter = ("country", "division")


class CustomUserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = ('email', 'first_name', 'last_name', 'username', 'role', 'is_staff', 'is_active', 'country_name')
    list_filter = ('is_staff', 'is_active', 'role')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'username', 'role', 'country_name')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'username', 'role', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'country_name'),
        }),
    )

    search_fields = ('email', 'first_name', 'last_name', 'username', 'role__name', 'country_name__nameName')
    filter_horizontal = ('groups', 'user_permissions')


admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Role)




