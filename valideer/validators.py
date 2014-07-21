from .base import Validator, ValidationError, parse, get_type_name
from itertools import izip
import collections
import datetime
import inspect
import numbers
import re

__all__ = [
    "AnyOf", "AllOf", "ChainOf", "Nullable", "NonNullable",
    "Enum", "Condition", "AdaptBy", "AdaptTo",
    "Type", "Boolean", "Integer", "Number", "Range",
    "String", "Pattern", "Date", "Datetime", "Time",
    "HomogeneousSequence", "HeterogeneousSequence", "Mapping", "Object",
]


class AnyOf(Validator):
    """A composite validator that accepts values accepted by any of its component
    validators.

    In case of adaptation, the first validator to successfully adapt the value
    is used.
    """

    def __init__(self, *schemas):
        self._validators = map(parse, schemas)

    def validate(self, value, adapt=True):
        msgs = []
        for validator in self._validators:
            try:
                return validator.validate(value, adapt)
            except ValidationError as ex:
                msgs.append(ex.msg)
        raise ValidationError(" or ".join(msgs), value)

    @property
    def humanized_name(self):
        return " or ".join(v.humanized_name for v in self._validators)


class AllOf(Validator):
    """A composite validator that accepts values accepted by all of its component
    validators.

    In case of adaptation, the adapted value from the last validator is returned.
    """

    def __init__(self, *schemas):
        self._validators = map(parse, schemas)

    def validate(self, value, adapt=True):
        result = value
        for validator in self._validators:
            result = validator.validate(value, adapt)
        return result

    @property
    def humanized_name(self):
        return " and ".join(v.humanized_name for v in self._validators)


class ChainOf(Validator):
    """A composite validator that passes a value through a sequence of validators.

    value -> validator1 -> value2 -> validator2 -> ... -> validatorN -> final_value
    """

    def __init__(self, *schemas):
        self._validators = map(parse, schemas)

    def validate(self, value, adapt=True):
        for validator in self._validators:
            value = validator.validate(value, adapt)
        return value

    @property
    def humanized_name(self):
        return " chained to ".join(v.humanized_name for v in self._validators)


class Nullable(Validator):
    """A validator that also accepts ``None``.

    ``None`` is adapted to ``default``. ``default`` can also be a zero-argument
    callable, in which case ``None`` is adapted to ``default()``.
    """

    def __init__(self, schema, default=None):
        if isinstance(schema, Validator):
            self._validator = schema
        else:
            validator = parse(schema)
            if isinstance(validator, (Nullable, NonNullable)):
                validator = validator._validator
            self._validator = validator
        self._default = default

    def validate(self, value, adapt=True):
        if value is None:
            return self.default
        return self._validator.validate(value, adapt)

    @property
    def default(self):
        if callable(self._default):
            return self._default()
        else:
            return self._default

    @property
    def humanized_name(self):
        return "%s or null" % self._validator.humanized_name


@Nullable.register_factory
def _NullableFactory(obj):
    """Parse a string starting with "?" as a Nullable validator."""
    if isinstance(obj, basestring) and obj.startswith("?"):
        return Nullable(obj[1:])


class NonNullable(Validator):
    """A validator that accepts anything but ``None``."""

    def __init__(self, schema=None):
        if schema is not None and not isinstance(schema, Validator):
            validator = parse(schema)
            if isinstance(validator, (Nullable, NonNullable)):
                validator = validator._validator
            self._validator = validator
        else:
            self._validator = schema

    def validate(self, value, adapt=True):
        if value is None:
            self.error(value)
        if self._validator is not None:
            return self._validator.validate(value, adapt)
        return value

    @property
    def humanized_name(self):
        return self._validator.humanized_name if self._validator else "non null"


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

    values = ()

    def __init__(self, values=None):
        super(Enum, self).__init__()
        if values is None:
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
        self.error(value)

    @property
    def humanized_name(self):
        return "one of {%s}" % ", ".join(map(repr, self.values))


class Condition(Validator):
    """A validator that accepts a value using a callable ``predicate``.

    A value is accepted if ``predicate(value)`` is true.
    """

    def __init__(self, predicate, traps=Exception):
        if not inspect.isroutine(predicate):
            raise TypeError("Routine expected, %s given" % predicate.__class__)
        self._predicate = predicate
        self._traps = traps

    def validate(self, value, adapt=True):
        if self._traps:
            try:
                is_valid = self._predicate(value)
            except self._traps:
                is_valid = False
        else:
            is_valid = self._predicate(value)

        if not is_valid:
            self.error(value)

        return value

    def error(self, value):
        raise ValidationError("must satisfy predicate %s" % self.humanized_name, value)

    @property
    def humanized_name(self):
        return str(getattr(self._predicate, "__name__", self._predicate))


@Condition.register_factory
def _ConditionFactory(obj):
    """Parse a function or method as a Condition validator."""
    if inspect.isroutine(obj):
        return Condition(obj)


class AdaptBy(Validator):
    """A validator that adapts a value using an ``adaptor`` callable."""

    def __init__(self, adaptor, traps=Exception):
        """Instantiate this validator.

        :param adaptor: The callable ``f(value)`` to adapt values.
        :param traps: An exception or a tuple of exceptions to catch and wrap
            into a :py:exc:`ValidationError`. Any other raised exception is
            left to propagate.
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
            into a :py:exc:`ValidationError`. Any other raised exception is left
            to propagate.
        :param exact: If False, instances of ``target_cls`` or a subclass are
            returned as is. If True, only instances of ``target_cls`` are
            returned as is.
        """
        if not inspect.isclass(target_cls):
            raise TypeError("Type expected, %s given" % target_cls.__class__)
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
        if not isinstance(value, self.accept_types) or isinstance(value, self.reject_types):
            self.error(value)
        return value

    @property
    def humanized_name(self):
        return self.name or _format_types(self.accept_types)


@Type.register_factory
def _TypeFactory(obj):
    """Parse a python type (or "old-style" class) as a :py:class:`Type` instance."""
    if inspect.isclass(obj):
        return Type(obj)


class Boolean(Type):
    """A validator that accepts bool values."""

    name = "boolean"
    accept_types = bool


class Integer(Type):
    """
    A validator that accepts integers (:py:class:`numbers.Integral` instances)
    but not bool.
    """

    name = "integer"
    accept_types = numbers.Integral
    reject_types = bool


class Range(Validator):
    """A validator that accepts values within in a certain range."""

    def __init__(self, schema=None, min_value=None, max_value=None):
        """Instantiate a :py:class:`Range` validator.

        :param schema: Optional schema or validator for the value.
        :param min_value: If not None, values less than ``min_value`` are
            invalid.
        :param max_value: If not None, values larger than ``max_value`` are
            invalid.
        """
        super(Range, self).__init__()
        self._validator = parse(schema) if schema is not None else None
        self._min_value = min_value
        self._max_value = max_value

    def validate(self, value, adapt=True):
        if self._validator is not None:
            value = self._validator.validate(value, adapt=adapt)

        if self._min_value is not None and value < self._min_value:
            raise ValidationError("must not be less than %d" %
                                  self._min_value, value)
        if self._max_value is not None and value > self._max_value:
            raise ValidationError("must not be larger than %d" %
                                  self._max_value, value)

        return value


class Number(Type):
    """A validator that accepts any numbers (but not bool)."""

    name = "number"
    accept_types = numbers.Number
    reject_types = bool


class Date(Type):
    """A validator that accepts :py:class:`datetime.date` values."""

    name = "date"
    accept_types = datetime.date


class Datetime(Type):
    """A validator that accepts :py:class:`datetime.datetime` values."""

    name = "datetime"
    accept_types = datetime.datetime


class Time(Type):
    """A validator that accepts :py:class:`datetime.time` values."""

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
            raise ValidationError("must be at least %d characters long" %
                                  self._min_length, value)
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError("must be at most %d characters long" %
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
            self.error(value)
        return value

    def error(self, value):
        raise ValidationError("must match %s" % self.humanized_name, value)

    @property
    def humanized_name(self):
        return "pattern %s" % self.regexp.pattern


@Pattern.register_factory
def _PatternFactory(obj):
    """Parse a compiled regexp as a :py:class:`Pattern` instance."""
    if isinstance(obj, _SRE_Pattern):
        return Pattern(obj)


class HomogeneousSequence(Type):
    """A validator that accepts homogeneous, non-fixed size sequences."""

    accept_types = collections.Sequence
    reject_types = basestring

    def __init__(self, item_schema=None, min_length=None, max_length=None):
        """Instantiate a :py:class:`HomogeneousSequence` validator.

        :param item_schema: If not None, the schema of the items of the list.
        """
        super(HomogeneousSequence, self).__init__()
        if item_schema is not None:
            self._item_validator = parse(item_schema)
        else:
            self._item_validator = None
        self._min_length = min_length
        self._max_length = max_length

    def validate(self, value, adapt=True):
        super(HomogeneousSequence, self).validate(value)
        if self._min_length is not None and len(value) < self._min_length:
            raise ValidationError("must contain at least %d elements" %
                                  self._min_length, value)
        if self._max_length is not None and len(value) > self._max_length:
            raise ValidationError("must contain at most %d elements" %
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
    """
    Parse an empty or 1-element ``[schema]`` list as a :py:class:`HomogeneousSequence`
    validator.
    """
    if isinstance(obj, list) and len(obj) <= 1:
        return HomogeneousSequence(*obj)


class HeterogeneousSequence(Type):
    """A validator that accepts heterogeneous, fixed size sequences."""

    accept_types = collections.Sequence
    reject_types = basestring

    def __init__(self, *item_schemas):
        """Instantiate a :py:class:`HeterogeneousSequence` validator.

        :param item_schemas: The schema of each element of the the tuple.
        """
        super(HeterogeneousSequence, self).__init__()
        self._item_validators = map(parse, item_schemas)

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
    """
    Parse a  ``(schema1, ..., schemaN)`` tuple as a :py:class:`HeterogeneousSequence`
    validator.
    """
    if isinstance(obj, tuple):
        return HeterogeneousSequence(*obj)


class Mapping(Type):
    """A validator that accepts mappings (:py:class:`collections.Mapping` instances)."""

    accept_types = collections.Mapping

    def __init__(self, key_schema=None, value_schema=None):
        """Instantiate a :py:class:`Mapping` validator.

        :param key_schema: If not None, the schema of the dict keys.
        :param value_schema: If not None, the schema of the dict values.
        """
        super(Mapping, self).__init__()
        if key_schema is not None:
            self._key_validator = parse(key_schema)
        else:
            self._key_validator = None
        if value_schema is not None:
            self._value_validator = parse(value_schema)
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

    A ``json-like object`` here is meant as a dict with a predefined set of
    "properties", i.e. string keys.
    """

    accept_types = collections.Mapping

    REQUIRED_PROPERTIES = False
    ADDITIONAL_PROPERTIES = True
    REMOVE = object()

    def __init__(self, optional={}, required={}, additional=None):
        """Instantiate an Object validator.

        :param optional: The schema of optional properties, specified as a
            ``{name: schema}`` dict.
        :param required: The schema of required properties, specified as a
            ``{name: schema}`` dict.
        :param additional: The schema of all properties that are not explicitly
            defined as ``optional`` or ``required``. It can also be:

            - ``True`` to allow any value for additional properties.
            - ``False`` to disallow any additional properties.
            - :py:attr:`REMOVE` to remove any additional properties from the
              adapted object.
            - ``None`` to use the value of the ``ADDITIONAL_PROPERTIES`` class
              attribute.
        """
        super(Object, self).__init__()
        if additional is None:
            additional = self.ADDITIONAL_PROPERTIES
        if not isinstance(additional, bool) and additional is not self.REMOVE:
            additional = parse(additional)
        self._named_validators = [
            (name, parse(schema))
            for name, schema in dict(optional, **required).iteritems()
        ]
        self._required_keys = set(required)
        self._all_keys = set(name for name, _ in self._named_validators)
        self._additional = additional

    def validate(self, value, adapt=True):
        super(Object, self).validate(value)
        missing_required = self._required_keys.difference(value)
        if missing_required:
            raise ValidationError("missing required properties: %s" %
                                  list(missing_required), value)

        result = dict(value) if adapt else None
        for name, validator in self._named_validators:
            if name in value:
                try:
                    adapted = validator.validate(value[name], adapt)
                    if result is not None:
                        result[name] = adapted
                except ValidationError as ex:
                    raise ex.add_context(name)
            elif isinstance(validator, Nullable):
                adapted = validator.default
                if adapted is not None and result is not None:
                    result[name] = adapted

        if self._additional != True:
            all_keys = self._all_keys
            additional_properties = [k for k in value if k not in all_keys]
            if additional_properties:
                if self._additional == False:
                    raise ValidationError("additional properties: %s" %
                                          additional_properties, value)
                elif self._additional is self.REMOVE:
                    if result is not None:
                        for name in additional_properties:
                            del result[name]
                else:
                    additional_validate = self._additional.validate
                    for name in additional_properties:
                        try:
                            adapted = additional_validate(value[name], adapt)
                            if result is not None:
                                result[name] = adapted
                        except ValidationError as ex:
                            raise ex.add_context(name)

        return result


@Object.register_factory
def _ObjectFactory(obj, required_properties=None, additional_properties=None):
    """Parse a python ``{name: schema}`` dict as an :py:class:`Object` instance.

    - A property name prepended by "+" is required
    - A property name prepended by "?" is optional
    - Any other property is:
      - required if ``required_properties`` is True
        or
        ``required_properties`` is None and :py:attr:`Object.REQUIRED_PROPERTIES`
      - optional if ``required_properties`` is False
        or
        ``required_properties`` is None and ``not`` :py:attr:`Object.REQUIRED_PROPERTIES`

    :param additional_properties: The ``additional`` parameter to :py:class:`Object`.
    """
    if isinstance(obj, dict):
        if required_properties is None:
            required_properties = Object.REQUIRED_PROPERTIES
        optional, required = {}, {}
        for key, value in obj.iteritems():
            if key.startswith("+"):
                required[key[1:]] = value
            elif key.startswith("?"):
                optional[key[1:]] = value
            elif required_properties:
                required[key] = value
            else:
                optional[key] = value
        return Object(optional, required, additional_properties)


def _format_types(types):
    if inspect.isclass(types):
        types = (types,)
    names = map(get_type_name, types)
    s = names[-1]
    if len(names) > 1:
        s = ", ".join(names[:-1]) + " or " + s
    return s
