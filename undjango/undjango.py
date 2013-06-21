from django.db import models
from django.conf import settings
from django.db.models.query import QuerySet

from .utils import get_field_value, parse_selectors, camelcase

UNDJANGO_OPTIONS = getattr(settings, 'UNDJANGO_OPTIONS', {})

DEFAULT_OPTIONS = {
    'aliases': {},
    'allow_missing': False,
    'camelcase': False,
    'prefix': '',
    'process': None,
    'values_list': False,
    'flat': True,
    'merge': False,
    'prehook': False,
    'posthook': False,
}

def _defaults(options):
    defaults = DEFAULT_OPTIONS.copy()

    # Update with settings-based options
    defaults.update(UNDJANGO_OPTIONS)

    # Update with current options
    defaults.update(options)

    if 'fields' not in defaults:
        defaults['fields'] = []

    if 'related' not in defaults:
        defaults['related'] = {}

    return defaults


def unmodel(instance, **options):
    "Takes a model instance and converts it into a dict."

    options = _defaults(options)
    attrs = {}

    if options['prehook']:
        if callable(options['prehook']):
            instance = options['prehook'](instance)
            if instance is None:
                return attrs

    # Items in the `fields` list are the output aliases, not the raw
    # accessors (field, method, property names)
    for alias in options['fields']:

        # Get the accessor for the object
        accessor = options['aliases'].get(alias, alias)

        # Create the key that will be used in the output dict
        key = options['prefix'] + alias

        # Optionally camelcase the key
        if options['camelcase']:
            key = camelcase(key)

        # Get the field value. Use the mapped value to the actually property or
        # method name. `value` may be a number of things, so the various types
        # are checked below.
        value = get_field_value(instance, accessor,
            allow_missing=options['allow_missing'])

        # Related objects, perform some checks on their options
        if isinstance(value, (models.Model, QuerySet)):
            _options = _defaults(options['related'].get(accessor, {}))

            # If the `prefix` follows the below template, generate the
            # `prefix` for the related object
            if '{accessor}' in _options['prefix']:
                _options['prefix'] = _options['prefix'].format({'accessor': alias})

            if isinstance(value, models.Model):
                if len(_options['fields']) == 1 and _options['flat'] and not _options['merge']:
                    value = undjango(value, **_options)
                else:
                    # Recurse, get the dict representation
                    _attrs = undjango(value, **_options)

                    # Check if this object should be merged into the parent,
                    # otherwise nest it under the accessor name
                    if _options['merge']:
                        attrs.update(_attrs)
                        continue

                    value = _attrs
            else:
                value = undjango(value, **_options)
        attrs[key] = value

    # Apply post-hook to serialized attributes
    if options['posthook']:
        attrs = options['posthook'](instance, attrs)

    return attrs


def unqueryset(queryset, **options):
    options = _defaults(options)

    if options['prehook']:
        if callable(options['prehook']):
            queryset = options['prehook'](queryset)
            if queryset is None:
                return []
        else:
            queryset = queryset.filter(**options['prehook'])

    # If the `select_related` option is defined, update the `QuerySet`
    if 'select_related' in options:
        queryset = queryset.select_related(*options['select_related'])

    if options['values_list']:
        fields = options['fields']

        # Flatten if only one field is being selected
        if len(fields) == 1:
            queryset = queryset.values_list(fields[0], flat=options['flat'])
        else:
            queryset = queryset.values_list(*fields)
        return list(queryset)

    return [unmodel(model, **options) for model in queryset]


def undjango(obj, fields=None, exclude=None, **options):
    """Recursively attempts to find ``Model`` and ``QuerySet`` instances
    to convert them into their representative datastructure per their
    ``Resource`` (if one exists).
    """

    # Handle model instances
    if isinstance(obj, models.Model):
        fields = parse_selectors(obj.__class__, fields, exclude, **options)
        return unmodel(obj, fields=fields, **options)

    # Handle querysets
    if isinstance(obj, QuerySet):
        fields = parse_selectors(obj.model, fields, exclude, **options)
        return unqueryset(obj, fields=fields, **options)

    # Handle dict instances
    if isinstance(obj, dict):
        exclude = exclude or []
        fields = fields or obj.keys()
        fields = [x for x in (fields or obj.keys()) if x not in exclude]
        return unmodel(obj, fields=fields, **options)

    # Handle other iterables
    if hasattr(obj, '__iter__'):
        return [undjango(i, fields, exclude, **options) for i in obj]

    return obj
