# coding: utf-8

# NOTE: Copied from grapelli to use the tags without the need to install grapelli admin interface
# https://github.com/sehmaschine/django-grappelli/blob/master/grappelli/templatetags/grp_tags.py

# pylint: skip-file

# python imports
from functools import wraps
import json

try:
    from django.contrib.auth import get_user_model
    User = get_user_model()
except ImportError:
    from django.contrib.auth.models import User

# django imports
from django import template
from django.contrib.contenttypes.models import ContentType
from django.utils.formats import get_format
from django.utils.safestring import mark_safe
from django.utils.translation import get_language
from django.template.loader import get_template

register = template.Library()


# GENERIC OBJECTS
class do_get_generic_objects(template.Node):
    def __init__(self):
        pass

    def render(self, context):
        objects = {}
        for c in ContentType.objects.all().order_by('id'):
            objects[c.id] = {'pk': c.id, 'app': c.app_label, 'model': c.model}
        return json.dumps(objects)


@register.tag
def get_content_types(parser, token):
    """
    Returns a list of installed applications and models.
    Needed for lookup of generic relationships.
    """
    return do_get_generic_objects()


# RETURNS CURRENT LANGUAGE
@register.simple_tag
def get_lang():
    return get_language()


@register.simple_tag
def get_date_format():
    return get_format('DATE_INPUT_FORMATS')[0]


@register.simple_tag
def get_time_format():
    return get_format('TIME_INPUT_FORMATS')[0]


@register.simple_tag
def get_datetime_format():
    return get_format('DATETIME_INPUT_FORMATS')[0]


@register.filter
def classname(obj, arg=None):
    classname = obj.__class__.__name__.lower()
    if arg:
        if arg.lower() == classname:
            return True
        return False
    return classname


@register.filter
def classpath(obj):
    module = obj.__module__
    classname = obj.__class__.__name__
    return "%s,%s" % (module, classname)


# FORMSETSORT FOR SORTABLE INLINES

@register.filter
def formsetsort(formset, arg):
    """
    Takes a list of formset dicts, returns that list sorted by the sortable field.
    """
    if arg:
        sorted_list = []
        for item in formset:
            position = item.form[arg].data
            if position and position != "-1":
                sorted_list.append((int(position), item))
        sorted_list.sort()
        sorted_list = [item[1] for item in sorted_list]
        for item in formset:
            position = item.form[arg].data
            if not position or position == "-1":
                sorted_list.append(item)
    else:
        sorted_list = formset
    return sorted_list


# RELATED LOOKUPS

def safe_json_else_list_tag(f):
    """
    Decorator. Registers function as a simple_tag.
    Try: Return value of the decorated function marked safe and json encoded.
    Except: Return []
    """
    @wraps(f)
    def inner(model_admin):
        try:
            return mark_safe(json.dumps(f(model_admin)))
        except:
            return []
    return register.simple_tag(inner)


@safe_json_else_list_tag
def get_related_lookup_fields_fk(model_admin):
    return model_admin.related_lookup_fields.get("fk", [])


@safe_json_else_list_tag
def get_related_lookup_fields_m2m(model_admin):
    return model_admin.related_lookup_fields.get("m2m", [])


@safe_json_else_list_tag
def get_related_lookup_fields_generic(model_admin):
    return model_admin.related_lookup_fields.get("generic", [])


# AUTOCOMPLETES

@safe_json_else_list_tag
def get_autocomplete_lookup_fields_fk(model_admin):
    return model_admin.autocomplete_lookup_fields.get("fk", [])


@safe_json_else_list_tag
def get_autocomplete_lookup_fields_m2m(model_admin):
    return model_admin.autocomplete_lookup_fields.get("m2m", [])


@safe_json_else_list_tag
def get_autocomplete_lookup_fields_generic(model_admin):
    return model_admin.autocomplete_lookup_fields.get("generic", [])


# SORTABLE EXCLUDES
@safe_json_else_list_tag
def get_sortable_excludes(model_admin):
    return model_admin.sortable_excludes


@register.filter
def prettylabel(value):
    return mark_safe(value.replace(":</label>", "</label>"))


# CUSTOM ADMIN LIST FILTER
# WITH TEMPLATE DEFINITION
@register.simple_tag
def admin_list_filter(cl, spec):
    try:
        tpl = get_template(cl.model_admin.change_list_filter_template)
    except:
        tpl = get_template(spec.template)
    return tpl.render({
        'title': spec.title,
        'choices': list(spec.choices(cl)),
        'spec': spec,
    })
