from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

class MobileAuthenticationForm(AuthenticationForm):
    """
    فرم لاگین مخصوص موبایل با اینپوت‌های بزرگ و تیره
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full bg-[#1e293b] border border-white/10 rounded-xl px-4 py-3.5 text-white placeholder-slate-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all text-center font-bold text-lg',
            'placeholder': 'Username',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full bg-[#1e293b] border border-white/10 rounded-xl px-4 py-3.5 text-white placeholder-slate-500 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all text-center font-bold text-lg',
            'placeholder': '••••••••',
        })
    )