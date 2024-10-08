import os

from django.db import models
from cryptography.fernet import Fernet
from django.utils import timezone
from django.core.exceptions import ValidationError

class Payment(models.Model):
    Payment_ID = models.CharField(max_length=255)
    Payment_Details = models.TextField(max_length=255)
    Non_Compete_Document = models.FileField(upload_to=r'Signed_Documents/')
    Promissory_Document = models.FileField(upload_to=r'Signed_Documents/')
    Payment_at = models.DateTimeField(auto_now_add=True, editable=False)

class Allowed_User(models.Model):
    Email_ID = models.CharField(max_length=255,unique=True)
    Expire_Date = models.DateField(blank=False)
    link = models.CharField(max_length=255,default="",blank=True)

    def __str__(self):
        return f"{self.Email_ID}"

    def clean(self):

        if self.Expire_Date <= timezone.now().date():
            raise ValidationError("Expire_Date must be in the future.")

    def save(self, *args, **kwargs):
        fernet = Fernet(os.getenv('LINK_KEY'))
        self.Email_ID = self.Email_ID.lower()
        self.link = os.getenv('HOST_NAME')+""+fernet.encrypt(self.Email_ID.lower().encode()).decode('utf-8')
        super().save(*args, **kwargs)