from django.contrib import admin
from . models import Payment,Allowed_User
from django.utils.translation import gettext_lazy

admin.site.site_header = "AIDefinitive Admin"
admin.site.site_title = "AIDefinitive Admin Portal"
admin.site.index_title = "Welcome to AIDefinitive Admin Portal"

# Register your models here.
admin.site.register(Payment)
admin.site.register(Allowed_User)