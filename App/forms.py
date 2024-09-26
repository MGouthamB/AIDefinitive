from django import forms

class PDFUploadForm(forms.Form):
    pdf = forms.FileField()