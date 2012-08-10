from .base import Validator, ValidationError
from itertools import izip
import collections
import datetime
import inspect
import numbers
import re


class AnyOf(Validator):
    """A composite validator that accepts values accepted by any of its components."""

    def __init__(self, *schemas):
        self._validators = map(Validator.parse, schemas)

    def validate(self, value, adapt=True):
        for validator in self._validators:
            try:
                return validator.validate(value, adapt)
            except ValidationError:
                pass
        raise ValidationError("Is not validated by %s" %
            _format_types([v.__class__ for v in self._validators]), value)


class Nullable(Validator):
    """A validator that also accepts None."""

    def __init__(self, schema, default=None):
        if isinstance(schema, Validator):
            self._validator = schema
        else:
            validator = Validator.parse(schema)
            if isinstance(validator, (Nullable, NonNullable)):
                validator = validator._validator
            self._validator = validator
        self.default = default

    def validate(self, value, adapt=True):
        if value is None:
            return self.default
        return self._validator.validate(value, adapt)


@Nullable.register_factory
def _NullableFactory(obj):
    """Parse a string starting with "?" as a Nullable validator."""
    if isinstance(obj, basestring) and obj.startswith("?"):
        return Nullable(obj[1:])


class NonNullable(Validator):
    """A validator that does not accept None."""

    def __init__(self, schema=None):
        if schema is not None and not isinstance(schema, Validator):
            validator = Validator.parse(schema)
            if isinstance(validator, (Nullable, NonNullable)):
                validator = validator._validator
            self._validator = validator
        else:
            self._validator = schema

    def validate(self, value, adapt=True):
        if value is None:
            raise ValidationError("Value must not be null")
        if self._validator is not None:
            return self._validator.validate(value, adapt)
        return value

@NonNullable.register_factory
def _NonNullableFactory(obj):
    """Parse a string starting with "+" as an NonNullable validator."""
    if isinstance(obj, basestring) and obj.startswith("+"):
        return NonNullable(obj[1:])


class Enum(Validator):
    """A validator that accepts only a finite set of values.

    Attributes:
        - values: The collection of valid values.
    """

    values = None

    def __init__(self, values=None):
        super(Enum, self).__init__()
        if not values:
            values = self.values
        try:
            self.values = set(values)
        except TypeError: # unhashable
            self.values = list(values)

    def validate(self, value, adapt=True):
        try:
            if value in self.values:
                return value
        except TypeError: # unhashable
            pass
        raise ValidationError("Must be one of %r" % list(self.values), value)


class AdaptBy(Validator):
    """A validator that adapts a value using an ``adaptor`` callable."""

    def __init__(self, adaptor, traps=Exception):
        """Instantiate this validator.

        :param adaptor: The callable ``f(value)`` to adapt values.
        :param traps: An exception or a tuple of exceptions to catch and wrap
            into a ``ValidationError``. Any other raised exception is left to
            propagate.
        """
        self._adaptor = adaptor
        self._traps = traps

    def validate(self, value, adapt=True):
        if not self._traps:
            return self._adaptor(value)
        try:
            return self._adaptor(value)
        except self._traps, ex:
            raise ValidationError(str(ex), value)


class AdaptTo(AdaptBy):
    """A validator that adapts a value to a target class."""

    def __init__(self, target_cls, traps=Exception, exact=False):
        """Instantiate this validator.

        :param target_cls: The target class.
        :param traps: An exception or a tuple of exceptions to catch and wrap
            into a ``ValidationError``. Any other raised exception is left to
            propagate.
        :param exact: If False, instances of ``target_cls`` or a subclass are
            returned as is. If True, only instances of ``target_cls`` are
            returned as is.
        """
        if not inspect.isclass(target_cls):
            raise TypeError("Type expected, %s given" % target_cls)
        self._exact = exact
        super(AdaptTo, self).__init__(target_cls, traps)

    def validate(self, value, adapt=True):
        if isinstance(value, self._adaptor) and (not self._exact or
                                                 value.__class__ == self._adaptor):
            return value
        return super(AdaptTo, self).validate(value, adapt)


class Type(Validator):
    """A validator accepting values that are instances of one or more given types.

    Attributes:
        - accept_types: A type or tuple of types that are valid.
        - reject_types: A type or tuple of types that are invalid.
    """

    accept_types = ()
    reject_types = ()

    def __init__(self, accept_types=None, reject_types=None):
        if accept_types is not None:
            self.accept_types = accept_types
        if reject_types is not None:
            self.reject_types = reject_types

    def validate(self, value, adapt=True):
        if not isinstance(value, self.accept_types):
            raise ValidationError("Must be %s" % _format_types(self.accept_types),
                                  value)
        if isinstance(value, self.reject_types):
            raise ValidationError("Must not be %s" % _format_types(self.reject_types),
                                  value)
        return value

@Type.register_factory
def _TypeFactory(obj):
    """Parse a python type (or "old-style" class) as a ``Type`` instance."""
    if inspect.isclass(obj):
        return Type(obj)


class Boolean(Type):
    """A validator that accepts bool values."""

    name = "boolean"
    accept_types = bool


class Integer(Type):
    """A validator that accepts integers (numbers.Integral instances) but not bool."""

    name = "integer"
    accept_types = numbers.Integral
    reject_types = bool


class Range(Validator):
    """A validator that accepts only numbers in a certain range"""

    def __init__(self, schema, min_value=None, max_value=None):
        """Instantiate an Integer validator.

        :param min_value: If not None, values less than ``min_value`` are
            invalid.
        :param max_value: If not None, values larger than ``max_value`` are
            invalid.
        """
        super(Range, self).__init__()
        self._validator = Validator.parse(schema)
        self._min_value = min_value
        self._max_value = max_value

    def validate(self, value, adapt=True):
        value = self._validator.validate(value, adapt=adapt)

        if self._min_value is not None and value < self._min_value:
            raise ValidationError("Must not be less than %d" %
                                  self._min_value, value)
        if self._max_value is not None and value > self._max_value:
            raise ValidationError("Must not be larger than %d" %
                                  self._max_value, value)

        return value


class Number(Type):
    """A validator that accepts any numbers (but not bool)."""

    name = "number"
    accept_types = numbers.Number
    reject_types = bool


class Date(Type):
    """A validator that accepts datetime.date values."""

    name = "date"
    accept_types = datetime.date


class Datetime(Type):
    """A validator that accepts datetime.datetime values."""

    name = "datetime"
    accept_types = datetime.datetime


class Time(Type):
    """A validator that accepts datetime.time values."""

    name = "time"
    accept_types = datetime.time


class String(Type):
    """A validator that accepts string values."""

    name = "string"
    accept_types = basestring

    def __init__(self, min_length=None, max_length=None):
        """Instantiate a String validator.

        :param min_length: If not None, strings shorter than ``min_length`` are
            invalid.
        :param max_length: If not None, strings longer than ``max_length`` are
            invalid.
        """
        super(String, self).__init__()
        self._min_length = min_length
        self._max_length = max_length

    def validate(self, value, adapt=True):
        super(String, self).validate(value)
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError("Must be at least %d characters long" %
                                  self._min_length, value)
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError("Must be at most %d characters long" %
                                  self._max_length, value)
        return value


_SRE_Pattern = type(re.compile(""))

class Pattern(String):
    """A validator that accepts strings that match a given regular expression.

    Attributes:
        - regexp: The regular expression (string or compiled) to be matched.
    """

    regexp = None

    def __init__(self, regexp=None):
        super(Pattern, self).__init__()
        self.regexp = re.compile(regexp or self.regexp)

    def validate(self, value, adapt=True):
        super(Pattern, self).validate(value)
        if not self.regexp.match(value):
            raise ValidationError("Does not match pattern %s" % self.regexp.pattern,
                                  value)
        return value

@Pattern.register_factory
def _PatternFactory(obj):
    """Parse a compiled regexp as a ``Pattern`` instance."""
    if isinstance(obj, _SRE_Pattern):
        return Pattern(obj)


class HomogeneousSequence(Type):
    """A validator that accepts homogeneous, non-fixed size sequences."""

    accept_types = collections.Sequence
    reject_types = basestring

    def __init__(self, item_schema=None, min_length=None, max_length=None):
        """Instantiate a ``HomogeneousSequence`` validator.

        :param item_schema: If not None, the schema of the items of the list.
        """
        super(HomogeneousSequence, self).__init__()
        if item_schema is not None:
            self._item_validator = Validator.parse(item_schema)
        else:
            self._item_validator = None
        self._min_length = min_length
        self._max_length = max_length

    def validate(self, value, adapt=True):
        super(HomogeneousSequence, self).validate(value)
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError("Must contain at least %d elements" %
                                  self._min_length, value)
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError("Must contain at most %d elements" %
                                  self._max_length, value)
        if self._item_validator is None:
            return value
        if adapt:
            return value.__class__(self._iter_validated_items(value, adapt))
        for _ in self._iter_validated_items(value, adapt):
            pass

    def _iter_validated_items(self, value, adapt):
        validate_item = self._item_validator.validate
        for i, item in enumerate(value):
            try:
                yield validate_item(item, adapt)
            except ValidationError as ex:
                raise ex.add_context(i)

@HomogeneousSequence.register_factory
def _HomogeneousSequenceFactory(obj):
    """Parse an empty or 1-element ``[schema]`` list as a ``HomogeneousSequence`` 
    validator.
    """
    if isinstance(obj, list) and len(obj) <= 1:
        return HomogeneousSequence(*obj)


class HeterogeneousSequence(Type):
    """A validator that accepts heterogeneous, fixed size sequences."""

    accept_types = collections.Sequence
    reject_types = basestring

    def __init__(self, *item_schemas):
        """Instantiate a ``HeterogeneousSequence`` validator.

        :param item_schemas: The schema of each element of the the tuple.
        """
        super(HeterogeneousSequence, self).__init__()
        self._item_validators = map(Validator.parse, item_schemas)

    def validate(self, value, adapt=True):
        super(HeterogeneousSequence, self).validate(value)
        if len(value) != len(self._item_validators):
            raise ValidationError("%d items expected, %d found" %
                                  (len(self._item_validators), len(value)), value)
        if adapt:
            return value.__class__(self._iter_validated_items(value, adapt))
        for _ in self._iter_validated_items(value, adapt):
            pass

    def _iter_validated_items(self, value, adapt):
        for i, (validator, item) in enumerate(izip(self._item_validators, value)):
            try:
                yield validator.validate(item, adapt)
            except ValidationError as ex:
                raise ex.add_context(i)

@HeterogeneousSequence.register_factory
def _HeterogeneousSequenceFactory(obj):
    """Parse a  ``(schema1, ..., schemaN)`` tuple as a ``HeterogeneousSequence`` 
    validator.
    """
    if isinstance(obj, tuple):
        return HeterogeneousSequence(*obj)


class Mapping(Type):
    """A validator that accepts dicts."""

    accept_types = collections.Mapping

    def __init__(self, key_schema=None, value_schema=None):
        """Instantiate a dict validator.

        :param key_schema: If not None, the schema of the dict keys.
        :param value_schema: If not None, the schema of the dict values.
        """
        super(Mapping, self).__init__()
        if key_schema is not None:
            self._key_validator = Validator.parse(key_schema)
        else:
            self._key_validator = None
        if value_schema is not None:
            self._value_validator = Validator.parse(value_schema)
        else:
            self._value_validator = None

    def validate(self, value, adapt=True):
        super(Mapping, self).validate(value)
        if adapt:
            return dict(self._iter_validated_items(value, adapt))
        for _ in self._iter_validated_items(value, adapt):
            pass

    def _iter_validated_items(self, value, adapt):
        validate_key = validate_value = None
        if self._key_validator is not None:
            validate_key = self._key_validator.validate
        if self._value_validator is not None:
            validate_value = self._value_validator.validate
        for k, v in value.iteritems():
            if validate_value is not None:
                try:
                    v = validate_value(v, adapt)
                except ValidationError as ex:
                    raise ex.add_context(k)
            if validate_key is not None:
                k = validate_key(k, adapt)
            yield (k, v)


class Object(Type):
    """A validator that accepts json-like objects.

    A ``json-like object`` here is meant as a dict with specific properties 
    (i.e. string keys).
    """

    accept_types = collections.Mapping

    REQUIRED_PROPERTIES = False

    def __init__(self, optional={}, required={}):
        """Instantiate an Object validator.

        :param optional: The schema of optional properties, specified as a
            ``{name: schema}`` dict.
        :param required: The schema of required properties, specified as a
            ``{name: schema}`` dict.

        Extra properties not specified as either ``optional`` or ``required``
        are implicitly allowed.
        """
        super(Object, self).__init__()
        self._required_keys = set(required)
        self._named_validators = [
            (name, Validator.parse(schema))
            for name, schema in dict(optional, **required).iteritems()
        ]

    def validate(self, value, adapt=True):
        super(Object, self).validate(value)
        missing_required = self._required_keys.difference(value)
        if missing_required:
            raise ValidationError("Missing required properties: %s" %
                                  list(missing_required), value)
        if adapt:
            adapted = dict(value)
            adapted.update(self._iter_validated_items(value, adapt))
            return adapted
        for _ in self._iter_validated_items(value, adapt):
            pass

    def _iter_validated_items(self, value, adapt):
        for name, validator in self._named_validators:
            if name in value:
                try:
                    yield (name, validator.validate(value[name], adapt))
                except ValidationError as ex:
                    raise ex.add_context(name)
            elif isinstance(validator, Nullable) and validator.default is not None:
                yield (name, validator.default)

@Object.register_factory
def _ObjectFactory(obj):
    """Parse a python ``{name: schema}`` dict as an ``Object`` instance.

    A property name can be prepended by "+" or "?" to mark it explicitly as
    required or optional, respectively. Otherwise ``Object.REQUIRED_PROPERTIES``
    is used to determine if properties are required by default.
    """
    if isinstance(obj, dict):
        optional, required = {}, {}
        for key, value in obj.iteritems():
            if key.startswith("+"):
                required[key[1:]] = value
            elif key.startswith("?"):
                optional[key[1:]] = value
            elif Object.REQUIRED_PROPERTIES:
                required[key] = value
            else:
                optional[key] = value
        return Object(optional, required)


def _format_types(types):
    if inspect.isclass(types):
        types = (types,)
    names = [t.__name__ for t in types]
    s = names[-1]
    if len(names) > 1:
        s = ", ".join(names[:-1]) + " or " + s
    return s
