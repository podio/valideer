__all__ = [
    "SchemaError",
    "BaseValidationError", "ValidationError",
    "set_name_for_types", "reset_type_names",
]

_TYPE_NAMES = {}


def set_name_for_types(name, *types):
    """Associate one or more types with an alternative human-friendly name."""
    for t in types:
        _TYPE_NAMES[t] = name


def reset_type_names():
    _TYPE_NAMES.clear()


def get_type_name(type):
    return _TYPE_NAMES.get(type) or type.__name__


class SchemaError(Exception):
    """An object cannot be parsed as a validator."""


class BaseValidationError(ValueError):
    """Abstract base class of all validation errors."""

    def __str__(self):
        return self.to_string()

    @property
    def message(self):
        return self.to_string()

    @property
    def args(self):
        return (self.to_string(),)

    def to_string(self, repr_value=repr):
        raise NotImplementedError('Abstract method')


class ValidationError(BaseValidationError):
    """A value is invalid for a given validator."""

    _UNDEFINED = object()

    def __init__(self, msg, value=_UNDEFINED):
        self.msg = msg
        self.value = value
        self.context = []
        super(ValidationError, self).__init__()

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
