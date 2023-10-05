
from django import forms

class YourForm(forms.Form):
    your_field = forms.CharField(label='What name of the book do you like?',
                                  widget=forms.TextInput(attrs={'autocomplete': 'off'}))
