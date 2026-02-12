from django import template

register = template.Library()

@register.filter
def get_schedule_for(data_table, school_class):
    """
    بر اساس کلاس، برنامه مربوطه رو از data_table می‌گیره.
    """
    return data_table.get(school_class, {})

@register.filter
def get_item(dictionary, key):
    """
    گرفتن آیتم از دیکشنری یا لیست به کمک key.
    """
    if dictionary is None:
        return None
    return dictionary.get(key) if isinstance(dictionary, dict) else None