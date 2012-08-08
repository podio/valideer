import inspect
from decorator import decorator

_NAMED_VALIDATORS = {}
_VALIDATOR_FACTORIES = []

class SchemaError(Exception):
    """An object cannot be parsed as a validator."""


class ValidationError(ValueError):
    """A value is invalid for a given validator."""

    _UNDEFINED = object()

    def __init__(self, msg, value=_UNDEFINED):
        if value is not self._UNDEFINED:
            msg = "Invalid value %r: %s" % (value, msg)
        super(ValidationError, self).__init__(msg)
        self.context = []

    def __str__(self):
        s = super(ValidationError, self).__str__()
        if self.context:
            s += " (at %s)" % "".join("[%r]" % context if i > 0 else str(context)
                                      for i, context in enumerate(reversed(self.context)))
        return s

    def add_context(self, context):
        self.context.append(context)
        return self


class Validator(object):
    """Abstract base class of all validators.

    Concrete subclasses must implement ``validate()``. A subclass may optionally
    define a ``name`` attribute (typically a string) that can be used to specify
    a validator in ``parse()`` instead of instantiating it explicitly.
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

        :param adapt: If False, it indicates that the caller is interested only
            on whether ``value`` is valid, not on adapting it. This is essentially
            an optimization hint for cases that validation can be done more
            efficiently than adaptation.

        :raises ValidationError: If ``value`` is invalid.
        :returns: The adapted value if ``adapt`` is True, otherwise anything.
        """
        raise NotImplementedError

    def is_valid(self, value):
        """Check if the value is valid.

        :returns: True if the value is valid, False if invalid.
        """
        try:
            self.validate(value, adapt=False)
            return True
        except ValidationError:
            return False

    @staticmethod
    def register(name, validator):
        """Register a validator instance under the given ``name``."""
        if not isinstance(validator, Validator):
            raise TypeError("Validator instance expected, %s given" % validator.__class__)
        _NAMED_VALIDATORS[name] = validator

    @staticmethod
    def register_factory(func):
        """Decorator for registering a validator factory.

        The decorated factory must be a callable that takes a single parameter
        that can be any arbitrary object and returns a Validator instance if it
        can parse the input object successfully, or None otherwise.
        """
        _VALIDATOR_FACTORIES.insert(0, func)
        return func

    @staticmethod
    def parse(obj):
        """Try to parse the given ``obj`` as a validator instance.

        :param obj: If it is a ...
            - ``Validator`` instance, return it.
            - ``Validator`` subclass, instantiate it without arguments and return it.
            - name of a known ``Validator`` subclass, instantiate the subclass
              without arguments and return it.
            - otherwise find the first registered ``Validator`` factory that can
              create it. The search order is the reverse of the factory registration
              order. The caller is responsible for ensuring there are no ambiguous
              values that can be parsed by more than one factory.
        :raises SchemaError: If no appropriate validator could be found.
        """
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


def accepts(**schemas):
    """Create a decorator for validating function parameters.

    Example::

        @accepts(a="number", body={"+field_ids": [int], "is_ok": bool})
        def f(a, body):
            print (a, body["field_ids"], body.get("is_ok"))

    :param schemas: The schema for validating a given parameter.
    """
    validate = Validator.parse(schemas).validate
    @decorator
    def validating(func, *args, **kwargs):
        validate(inspect.getcallargs(func, *args, **kwargs), adapt=False)
        return func(*args, **kwargs)
    return validating


def adapts(**schemas):
    """Create a decorator for validating and adapting function parameters.

    Example::

        @adapts(a="number", body={"+field_ids": [int], "is_ok": bool})
        def f(a, body):
            print (a, body.field_ids, body.is_ok)

    :param schemas: The schema for adapting a given parameter.
    """
    validate = Validator.parse(schemas).validate

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
