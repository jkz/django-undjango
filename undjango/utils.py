PSEUDO_SELECTORS = (':all', ':pk', ':local', ':related')
DEFAULT_SELECTORS = (':pk', ':local')

def camelcase(s):
    if '_' not in s:
        return s
    toks = s.split('_')
    return toks[0] + ''.join(x.title() for x in toks[1:] if x.upper() != x)


class ModelFieldResolver(object):
    cache = {}

    def _get_pk_field(self, model):
        return {
            ':pk': {field.name:field for field in [model._meta.pk]},
        }

    def _get_local_fields(self, model):
        "Return the names of all locally defined fields on the model class."
        local = model._meta.fields
        m2m = model._meta.many_to_many

        return {
            ':local': {field.name:field for field in local + m2m},
        }

    def _get_related_fields(self, model):
        "Returns the names of all related fields for model class."
        fk = model._meta.get_all_related_objects()
        m2m = model._meta.get_all_related_many_to_many_objects()

        return {
            ':related': {f.get_accessor_name():f for f in fk + m2m},
        }

    def _get_fields(self, model):
        if not model in self.cache:
            fields = {}

            fields.update(self._get_pk_field(model))
            fields.update(self._get_local_fields(model))
            fields.update(self._get_related_fields(model))

            all_ = {}
            for x in fields.values():
                all_.update(x)

            fields[':all'] = all_

            self.cache[model] = fields

        return self.cache[model]

    def get_field(self, model, attr):
        fields = self._get_fields(model)

        # Alias to model fields
        if attr in PSEUDO_SELECTORS:
            return list(fields[attr].keys())

        # Assume a field or property
        return attr

resolver = ModelFieldResolver()

def parse_selectors(model, fields=None, exclude=None, aliases=None, **options):
    """Validates fields are valid and maps pseudo-fields to actual fields
    for a given model class.
    """
    fields = fields or DEFAULT_SELECTORS
    exclude = exclude or ()
    aliases = aliases or {}
    validated = []

    for alias in fields:
        # Map the output key name to the actual field/accessor name for
        # the model
        actual = aliases.get(alias, alias)

        # Validate the field exists
        cleaned = resolver.get_field(model, actual)

        if cleaned is None:
            raise AttributeError('The "{0}" attribute could not be found '
                'on the model "{1}"'.format(actual, model))

        # Mapped value, so use the original name listed in `fields`
        if isinstance(cleaned, list):
            validated.extend(cleaned)
        elif alias != actual:
            validated.append(alias)
        else:
            validated.append(cleaned)

    return [x for x in validated if x not in exclude]


def get_field_value(obj, name, allow_missing=False):
    value = None

    if hasattr(obj, name):
        value = getattr(obj, name)
    elif hasattr(obj, '__getitem__') and name in obj:
        value = obj[name]
    elif not allow_missing:
        raise ValueError('{0} has no attribute {1}'.format(obj, name))

    # Check for callable
    if callable(value):
        value = value()

    # Handle a local many-to-many or a reverse foreign key
    elif value.__class__.__name__ in (
            'RelatedManager',
            'ManyRelatedManager',
            'GenericRelatedObjectManager'):
        value = value.all()

    return value
