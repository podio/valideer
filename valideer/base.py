import inspect
import itertools
from contextlib import contextmanager
from threading import RLock
from decorator import decorator

from six import with_metaclass
from .errors import SchemaError, ValidationError, MultipleValidationError


__all__ = [
    "parse", "parsing", "register", "register_factory",
    "Validator", "accepts", "returns", "adapts",
]

_NAMED_VALIDATORS = {}
_VALIDATOR_FACTORIES = []
_VALIDATOR_FACTORIES_LOCK = RLock()


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

    from .validators import Object
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


class _MetaValidator(type):
    def __new__(mcs, name, bases, attrs):  # @NoSelf
        validator_type = type.__new__(mcs, name, bases, attrs)
        validator_name = attrs.get("name")
        if validator_name is not None:
            _NAMED_VALIDATORS[validator_name] = validator_type
        return validator_type


class Validator(with_metaclass(_MetaValidator)):
    """Abstract base class of all validators.

    Concrete subclasses must implement :py:meth:`validate`. A subclass may optionally
    define a :py:attr:`name` attribute (typically a string) that can be used to specify
    a validator in :py:meth:`parse` instead of instantiating it explicitly.
    """

    name = None

    def validate(self, value, adapt=True):
        """
        Check if ``value`` is valid and if so adapt it, otherwise raise a
        ``ValidationError`` for the first encountered error.

        :param adapt: If ``False``, it indicates that the caller is interested
            only on whether ``value`` is valid, not on adapting it. This is
            essentially an optimization hint for cases that validation can be
            done more efficiently than adaptation.

        :raises ValidationError: If ``value`` is invalid.
        :returns: The adapted value if ``adapt`` is ``True``, otherwise anything.
        """
        raise NotImplementedError

    def full_validate(self, value, adapt=True):
        """
        Same as :py:meth:`validate` but raise :py:class:`MultipleValidationError`
        that holds all validation errors if ``value`` is invalid.

        The default implementation simply calls :py:meth:`validate` and wraps a
        :py:class:`ValidationError` into a :py:class:`MultipleValidationError`.

        :param adapt: If ``False``, it indicates that the caller is interested
            only on whether ``value`` is valid, not on adapting it. This is
            essentially an optimization hint for cases that validation can be
            done more efficiently than adaptation.

        :raises MultipleValidationError: If ``value`` is invalid.
        :returns: The adapted value if ``adapt`` is ``True``, otherwise anything.
        """
        try:
            return self.validate(value, adapt)
        except ValidationError as ex:
            raise MultipleValidationError([ex])

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


class ContainerValidator(Validator):
    """
    Convenient abstract base class for validators of container-like values that
    need to report multiple errors for their items without duplicating the logic
    between :py:meth:`validate` and :py:meth:`full_validate` or making the
    former less efficient than necessary by delegating to the latter.

    Concrete subclasses have to implement :py:meth:`_iter_errors_and_items` as a
    generator that yields all validation errors and items of the container value.
    If there are no validation errors and `adapt=True`, the final adapted value
    is produced by passing the yielded items to :py:meth:`_reduce_items`. The
    default :py:meth:`_reduce_items` instantiates `value.__class__` with the
    iterator of items but subclasses can override it if necessary.
    """

    def validate(self, value, adapt=True):
        return self._validate(value, adapt, full=False)

    def full_validate(self, value, adapt=True):
        return self._validate(value, adapt, full=True)

    def _validate(self, value, adapt, full):
        iterable = self._iter_errors_and_items(value, adapt, full)
        t1, t2 = itertools.tee(iterable)
        iter_errors = (x for x in t1 if isinstance(x, ValidationError))
        if full:
            multi_error = MultipleValidationError(iter_errors)
            if multi_error.errors:
                raise multi_error
        else:
            error = next(iter_errors, None)
            if error:
                raise error

        if adapt:
            iter_items = (x for x in t2 if not isinstance(x, ValidationError))
            return self._reduce_items(iter_items, value)

        return value

    def _reduce_items(self, iterable, value):
        return value.__class__(iterable)

    def _iter_errors_and_items(self, value, adapt, full):
        raise NotImplementedError


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


def returns(schema):
    """Create a decorator for validating function return value.

    Example::
        @accepts(a=int, b=int)
        @returns(int)
        def f(a, b):
            return a + b

    :param schema: The schema for adapting a given parameter.
    """
    validate = parse(schema).validate

    @decorator
    def validating(func, *args, **kwargs):
        ret = func(*args, **kwargs)
        validate(ret, adapt=False)
        return ret
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
        if not adapted_varargs:  # keywords only
            if adapted_keywords:
                adapted.update(adapted_keywords)
            return func(**adapted)

        adapted_posargs = [adapted[arg] for arg in argspec.args]
        adapted_posargs.extend(adapted_varargs)
        return func(*adapted_posargs, **adapted_keywords)

    return adapting
