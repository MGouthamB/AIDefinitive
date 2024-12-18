import os

from django.db import models
from cryptography.fernet import Fernet
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError

class Payment(models.Model):
    Name = models.CharField(max_length=100,default="")
    Payment_ID = models.CharField(max_length=255)
    Payment_Details = models.TextField(max_length=500)
    Non_Compete_Document = models.FileField(upload_to=r'Signed_Documents/')
    Promissory_Document = models.FileField(upload_to=r'Signed_Documents/')
    Payment_at = models.DateTimeField(auto_now_add=True, editable=False)

    def __str__(self):
        if self.Name: return f"{self.Name}"
        return super().__str__()

    class Meta:
        verbose_name = "Archive"
        verbose_name_plural = "Archive"


class Allowed_User(models.Model):
    Email_ID = models.CharField(max_length=255,unique=True)
    Expire_Date = models.DateField(blank=False)
    link = models.CharField(max_length=255,default="",blank=True)

    def __str__(self):
        return f"{self.Email_ID}"

    def clean(self):
        if self.Expire_Date <= timezone.localdate():
            raise ValidationError("Expire_Date must be in the future.")

    def save(self, *args, **kwargs):
        try:
            fernet = Fernet(os.getenv('LINK_KEY'))
            self.Email_ID = self.Email_ID.lower()
            self.link = "https://payments.aidefinitive.com/step1/"+fernet.encrypt(self.Email_ID.lower().encode()).decode('utf-8')
            super().save(*args, **kwargs)
        except IntegrityError as e:
            raise ValidationError(f"A user with the email {self.Email_ID} already exists.")

    class Meta:
        verbose_name = "Allowed Users"
        verbose_name_plural = "Allowed Users"