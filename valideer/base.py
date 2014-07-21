import inspect
from contextlib import contextmanager
from threading import RLock
from decorator import decorator

__all__ = [
    "ValidationError", "SchemaError", "Validator", "accepts", "adapts",
    "parse", "parsing", "register", "register_factory",
    "set_name_for_types", "reset_type_names",
]

_NAMED_VALIDATORS = {}
_VALIDATOR_FACTORIES = []
_VALIDATOR_FACTORIES_LOCK = RLock()

class SchemaError(Exception):
    """An object cannot be parsed as a validator."""


class ValidationError(ValueError):
    """A value is invalid for a given validator."""

    _UNDEFINED = object()

    def __init__(self, msg, value=_UNDEFINED):
        self.msg = msg
        self.value = value
        self.context = []
        super(ValidationError, self).__init__(str(self))

    def __str__(self):
        return self.to_string()

    def to_string(self, repr_value=repr):
        msg = self.msg
        if self.value is not self._UNDEFINED:
            msg = "Invalid value %s (%s): %s" % (repr_value(self.value),
                                                 get_type_name(self.value.__class__),
                                                 msg)
        if self.context:
            msg += " (at %s)" % "".join("[%r]" % context if i > 0 else str(context)
                                        for i, context in enumerate(reversed(self.context)))
        return msg

    def add_context(self, context):
        self.context.append(context)
        return self


def parse(obj, required_properties=None, additional_properties=None):
    """Try to parse the given ``obj`` as a validator instance.

    :param obj: The object to be parsed. If it is a...:

        - :py:class:`Validator` instance, return it.
        - :py:class:`Validator` subclass, instantiate it without arguments and
          return it.
        - :py:attr:`~Validator.name` of a known :py:class:`Validator` subclass,
          instantiate the subclass without arguments and return it.
        - otherwise find the first registered :py:class:`Validator` factory that
          can create it. The search order is the reverse of the factory registration
          order. The caller is responsible for ensuring there are no ambiguous
          values that can be parsed by more than one factory.

    :param required_properties: See the respective :py:func:`parsing` parameter.
    :param additional_properties: See the respective :py:func:`parsing` parameter.

    :raises SchemaError: If no appropriate validator could be found.

    .. warning:: Passing ``required_properties`` and/or ``additional_properties``
        with value other than ``None`` may be non intuitive for schemas that
        involve nested validators. Take for example the following schema::

            v = V.parse({
                "x": "integer",
                "child": V.Nullable({
                    "y": "integer"
                })
            }, required_properties=True)

        Here the top-level properties 'x' and 'child' are required but the nested
        'y' property is not. This is because by the time :py:meth:`parse` is called,
        :py:class:`~valideer.validators.Nullable` has already parsed its argument
        with the default value of ``required_properties``. Several other builtin
        validators work similarly to :py:class:`~valideer.validators.Nullable`,
        accepting one or more schemas to parse. In order to parse an arbitrarily
        complex nested validator with the same value for ``required_properties``
        and/or ``additional_properties``, use the :py:func:`parsing` context
        manager instead::

            with V.parsing(required_properties=True):
                v = V.parse({
                    "x": "integer",
                    "child": V.Nullable({
                        "y": "integer"
                    })
                })
    """
    if not (required_properties is additional_properties is None):
        with parsing(required_properties=required_properties,
                     additional_properties=additional_properties):
            return parse(obj)

    validator = None

    if isinstance(obj, Validator):
        validator = obj
    elif inspect.isclass(obj) and issubclass(obj, Validator):
        validator = obj()
    else:
        try:
            validator = _NAMED_VALIDATORS[obj]
        except (KeyError, TypeError):
            for factory in _VALIDATOR_FACTORIES:
                validator = factory(obj)
                if validator is not None:
                    break
        else:
            if inspect.isclass(validator) and issubclass(validator, Validator):
                _NAMED_VALIDATORS[obj] = validator = validator()

    if not isinstance(validator, Validator):
        raise SchemaError("%r cannot be parsed as a Validator" % obj)

    return validator


@contextmanager
def parsing(required_properties=None, additional_properties=None):
    """
    Context manager for overriding the default validator parsing rules for the
    following code block.

    :param required_properties: Specifies for this parse call whether parsed
        :py:class:`~valideer.validators.Object` properties are required or
        optional by default. It can be:

        - ``True`` for required.
        - ``False`` for optional.
        - ``None`` to use the value of the
          :py:attr:`~valideer.validators.Object.REQUIRED_PROPERTIES` attribute.

    :param additional_properties: Specifies for this parse call the schema of
        all :py:class:`~valideer.validators.Object` properties that are not
        explicitly defined as optional or required. It can also be:

        - ``True`` to allow any value for additional properties.
        - ``False`` to disallow any additional properties.
        - :py:attr:`~valideer.validators.Object.REMOVE` to remove any additional
          properties from the adapted object.
        - ``None`` to use the value of the
          :py:attr:`~valideer.validators.Object.ADDITIONAL_PROPERTIES` attribute.
    """
    from .validators import Object, _ObjectFactory
    with _VALIDATOR_FACTORIES_LOCK:
        if required_properties is not None:
            old_required_properties = Object.REQUIRED_PROPERTIES
            Object.REQUIRED_PROPERTIES = required_properties
        if additional_properties is not None:
            old_additional_properties = Object.ADDITIONAL_PROPERTIES
            Object.ADDITIONAL_PROPERTIES = additional_properties
        try:
            yield
        finally:
            if required_properties is not None:
                Object.REQUIRED_PROPERTIES = old_required_properties
            if additional_properties is not None:
                Object.ADDITIONAL_PROPERTIES = old_additional_properties


def register(name, validator):
    """Register a validator instance under the given ``name``."""
    if not isinstance(validator, Validator):
        raise TypeError("Validator instance expected, %s given" % validator.__class__)
    _NAMED_VALIDATORS[name] = validator


def register_factory(func):
    """Decorator for registering a validator factory.

    The decorated factory must be a callable that takes a single parameter
    that can be any arbitrary object and returns a :py:class:`Validator` instance
    if it can parse the input object successfully, or ``None`` otherwise.
    """
    _VALIDATOR_FACTORIES.insert(0, func)
    return func


class Validator(object):
    """Abstract base class of all validators.

    Concrete subclasses must implement :py:meth:`validate`. A subclass may optionally
    define a :py:attr:`name` attribute (typically a string) that can be used to specify
    a validator in :py:meth:`parse` instead of instantiating it explicitly.
    """

    class __metaclass__(type):
        def __new__(mcs, name, bases, attrs): #@NoSelf
            validator_type = type.__new__(mcs, name, bases, attrs)
            validator_name = attrs.get("name")
            if validator_name is not None:
                _NAMED_VALIDATORS[validator_name] = validator_type
            return validator_type

    name = None

    def validate(self, value, adapt=True):
        """Check if ``value`` is valid and if so adapt it.

        :param adapt: If ``False``, it indicates that the caller is interested
            only on whether ``value`` is valid, not on adapting it. This is
            essentially an optimization hint for cases that validation can be
            done more efficiently than adaptation.

        :raises ValidationError: If ``value`` is invalid.
        :returns: The adapted value if ``adapt`` is ``True``, otherwise anything.
        """
        raise NotImplementedError

    def is_valid(self, value):
        """Check if the value is valid.

        :returns: ``True`` if the value is valid, ``False`` if invalid.
        """
        try:
            self.validate(value, adapt=False)
            return True
        except ValidationError:
            return False

    def error(self, value):
        """Helper method that can be called when ``value`` is deemed invalid.

        Can be overriden to provide customized :py:exc:`ValidationError` subclasses.
        """
        raise ValidationError("must be %s" % self.humanized_name, value)

    @property
    def humanized_name(self):
        """Return a human-friendly string name for this validator."""
        return self.name or self.__class__.__name__

    # for backwards compatibility

    parse = staticmethod(parse)
    register = staticmethod(register)
    register_factory = staticmethod(register_factory)


def accepts(**schemas):
    """Create a decorator for validating function parameters.

    Example::

        @accepts(a="number", body={"+field_ids": [int], "is_ok": bool})
        def f(a, body):
            print (a, body["field_ids"], body.get("is_ok"))

    :param schemas: The schema for validating a given parameter.
    """
    validate = parse(schemas).validate
    @decorator
    def validating(func, *args, **kwargs):
        validate(inspect.getcallargs(func, *args, **kwargs), adapt=False)
        return func(*args, **kwargs)
    return validating


def adapts(**schemas):
    """Create a decorator for validating and adapting function parameters.

    Example::

        @adapts(a="number", body={"+field_ids": [V.AdaptTo(int)], "is_ok": bool})
        def f(a, body):
            print (a, body.field_ids, body.is_ok)

    :param schemas: The schema for adapting a given parameter.
    """
    validate = parse(schemas).validate

    @decorator
    def adapting(func, *args, **kwargs):
        adapted = validate(inspect.getcallargs(func, *args, **kwargs), adapt=True)
        argspec = inspect.getargspec(func)

        if argspec.varargs is argspec.keywords is None:
            # optimization for the common no varargs, no keywords case
            return func(**adapted)

        adapted_varargs = adapted.pop(argspec.varargs, ())
        adapted_keywords = adapted.pop(argspec.keywords, {})
        if not adapted_varargs: # keywords only
            if adapted_keywords:
                adapted.update(adapted_keywords)
            return func(**adapted)

        adapted_posargs = [adapted[arg] for arg in argspec.args]
        adapted_posargs.extend(adapted_varargs)
        return func(*adapted_posargs, **adapted_keywords)

    return adapting


_TYPE_NAMES = {}

def set_name_for_types(name, *types):
    """Associate one or more types with an alternative human-friendly name."""
    for t in types:
        _TYPE_NAMES[t] = name

def reset_type_names():
    _TYPE_NAMES.clear()

def get_type_name(type):
    return _TYPE_NAMES.get(type) or type.__name__
