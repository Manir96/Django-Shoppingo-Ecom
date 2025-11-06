from django.db import models
from django.contrib.auth.models import *
import uuid
from django.utils import timezone
from datetime import timedelta
from smart_selects.db_fields import ChainedForeignKey

class CountryName(models.Model):
    nameName = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["nameName"]

    def __str__(self):
        return self.nameName



class Division(models.Model):
    country = models.ForeignKey(CountryName, on_delete=models.CASCADE, related_name="states")
    division_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('country', 'division_name')
        ordering = ["division_name"]

    def __str__(self):
        return f"{self.division_name} ({self.country.nameName})"

class District(models.Model):
    
    country = models.ForeignKey(CountryName, on_delete=models.CASCADE)
    division = ChainedForeignKey(
        Division,
        chained_field="country",           # field on this model
        chained_model_field="country",     # field on Division model
        show_all=False,
        auto_choose=True,
        sort=True,
        on_delete=models.CASCADE
    )
    district_name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('division', 'district_name')
        ordering = ["district_name"]

    def __str__(self):
        return f"{self.district_name} ({self.division.division_name})"

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.display_name or self.name


class CustomUserManager(BaseUserManager):
    def _create_user(self, email, password, role=None, username=None, **extra_fields):
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        if isinstance(role, str):
            role_obj, _ = Role.objects.get_or_create(name=role)
        else:
            role_obj = role
        user = self.model(email=email, role=role_obj, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


    def create_user(self, email, password=None, role=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, role=role, **extra_fields)


    def create_superuser(self, email, password=None, role=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if role is None:
            role, _ = Role.objects.get_or_create(name='superadmin', defaults={'display_name': 'Super Admin', 'is_active': True})
        if not extra_fields.get('username'):
            extra_fields['username'] = email.split('@')[0]  
        return self._create_user(email, password, role=role,**extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    username = models.CharField(max_length=150, blank=True)
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True)
    country_name = models.ForeignKey(CountryName, on_delete=models.SET_NULL, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = [] 

    def __str__(self):
        return self.email


@property
def has_active_role(self):
    return bool(self.role and self.role.is_active)


def has_permission(self):
    """Helper that checks both user active and role active."""
    return self.is_active and self.has_active_role




class PasswordResetCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + timedelta(minutes=10)