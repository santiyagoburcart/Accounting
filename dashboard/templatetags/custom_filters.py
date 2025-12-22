from django import template
from django.utils.translation import gettext as _

register = template.Library()

@register.filter(name='month_name')
def month_name(month_number):
    # نام ماه‌ها را انگلیسی/فینگیلیش می‌نویسیم و مارک می‌کنیم برای ترجمه
    months = {
        1: _('Farvardin'), 2: _('Ordibehesht'), 3: _('Khordad'), 4: _('Tir'),
        5: _('Mordad'), 6: _('Shahrivar'), 7: _('Mehr'), 8: _('Aban'),
        9: _('Azar'), 10: _('Dey'), 11: _('Bahman'), 12: _('Esfand')
    }
    try:
        return months.get(int(month_number), month_number)
    except:
        return month_number

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)