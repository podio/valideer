========
Valideer
========

.. image:: https://travis-ci.org/podio/valideer.svg?branch=master
    :target: https://travis-ci.org/podio/valideer

.. image:: https://coveralls.io/repos/podio/valideer/badge.svg?branch=master
    :target: https://coveralls.io/r/podio/valideer?branch=master

.. image:: https://img.shields.io/pypi/status/valideer.svg
    :target: https://pypi.python.org/pypi/valideer/

.. image:: https://img.shields.io/pypi/v/valideer.svg
    :target: https://pypi.python.org/pypi/valideer/

.. image:: https://img.shields.io/pypi/pyversions/valideer.svg
    :target: https://pypi.python.org/pypi/valideer/

.. image:: https://img.shields.io/pypi/l/valideer.svg
    :target: https://pypi.python.org/pypi/valideer/

Lightweight data validation and adaptation library for Python.

**At a Glance**:

- Supports both validation (check if a value is valid) and adaptation (convert
  a valid input to an appropriate output).
- Succinct: validation schemas can be specified in a declarative and extensible
  mini "language"; no need to define verbose schema classes upfront. A regular
  Python API is also available if the compact syntax is not your cup of tea.
- Batteries included: validators for most common types are included out of the box.
- Extensible: New custom validators and adaptors can be easily defined and
  registered.
- Informative, customizable error messages: Validation errors include the reason
  and location of the error.
- Agnostic: not tied to any particular framework or application domain (e.g.
  Web form validation).
- Well tested: Extensive test suite with 100% coverage.
- Production ready: Used for validating every access to the `Podio API`_.
- Licence: MIT.


Installation
------------

To install run::

    pip install valideer

Or for the latest version::

    git clone git@github.com:podio/valideer.git
    cd valideer
    python setup.py install

You may run the unit tests with::

    $ python setup.py test --quiet
    running test
    running egg_info
    writing dependency_links to valideer.egg-info/dependency_links.txt
    writing requirements to valideer.egg-info/requires.txt
    writing valideer.egg-info/PKG-INFO
    writing top-level names to valideer.egg-info/top_level.txt
    reading manifest file 'valideer.egg-info/SOURCES.txt'
    reading manifest template 'MANIFEST.in'
    writing manifest file 'valideer.egg-info/SOURCES.txt'
    running build_ext
    ...........................................................................................................................................................................
    ----------------------------------------------------------------------
    Ran 171 tests in 0.106s

    OK

Basic Usage
-----------

We'll demonstrate ``valideer`` using the following `JSON schema example`_::

	{
	    "name": "Product",
	    "properties": {
	        "id": {
	            "type": "number",
	            "description": "Product identifier",
	            "required": true
	        },
	        "name": {
	            "type": "string",
	            "description": "Name of the product",
	            "required": true
	        },
	        "price": {
	            "type": "number",
	            "minimum": 0,
	            "required": true
	        },
	        "tags": {
	            "type": "array",
	            "items": {
	                "type": "string"
	            }
	        },
	        "stock": {
	            "type": "object",
	            "properties": {
	                "warehouse": {
	                    "type": "number"
	                },
	                "retail": {
	                    "type": "number"
	                }
	            }
	        }
	    }
	}

This can be specified by passing a similar but less verbose structure to the
``valideer.parse`` function::

	>>> import valideer as V
	>>> product_schema = {
	>>>     "+id": "number",
	>>>     "+name": "string",
	>>>     "+price": V.Range("number", min_value=0),
	>>>     "tags": ["string"],
	>>>     "stock": {
	>>>         "warehouse": "number",
	>>>         "retail": "number",
	>>>     }
	>>> }
	>>> validator = V.parse(product_schema)

``parse`` returns a ``Validator`` instance, which can be then used to validate
or adapt values.

Validation
##########

To check if an input is valid call the ``is_valid`` method::

	>>> product1 = {
	>>>     "id": 1,
	>>>     "name": "Foo",
	>>>     "price": 123,
	>>>     "tags": ["Bar", "Eek"],
	>>>     "stock": {
	>>>         "warehouse": 300,
	>>>         "retail": 20
	>>>     }
	>>> }
	>>> validator.is_valid(product1)
	True
	>>> product2 = {
	>>>     "id": 1,
	>>>     "price": 123,
	>>> }
	>>> validator.is_valid(product2)
	False

Another option is the ``validate`` method. If the input is invalid, it raises
``ValidationError``::

	>>> validator.validate(product2)
	ValidationError: Invalid value {'price': 123, 'id': 1} (dict): missing required properties: ['name']

For the common use case of validating inputs when entering a function, the
``@accepts`` decorator provides some nice syntax sugar (shamelessly stolen from
typecheck_)::

	>>> from valideer import accepts
	>>> @accepts(product=product_schema, quantity="integer")
	>>> def get_total_price(product, quantity=1):
	>>>     return product["price"] * quantity
	>>>
	>>> get_total_price(product1, 2)
	246
	>>> get_total_price(product1, 0.5)
	ValidationError: Invalid value 0.5 (float): must be integer (at quantity)
	>>> get_total_price(product2)
	ValidationError: Invalid value {'price': 123, 'id': 1} (dict): missing required properties: ['name'] (at product)

Adaptation
##########

Often input data have to be converted from their original form before they are
ready to use; for example a number that may arrive as integer or string and
needs to be adapted to a float. Since validation and adaptation usually happen
simultaneously, ``validate`` returns the adapted version of the (valid) input
by default.

An existing class can be easily used as an adaptor by being wrapped in ``AdaptTo``::

	>>> import valideer as V
	>>> adapt_prices = V.parse({"prices": [V.AdaptTo(float)]}).validate
	>>> adapt_prices({"prices": ["2", "3.1", 1]})
	{'prices': [2.0, 3.1, 1.0]}
	>>> adapt_prices({"prices": ["2", "3f"]})
	ValidationError: Invalid value '3f' (str): invalid literal for float(): 3f (at prices[1])
	>>> adapt_prices({"prices": ["2", 1, None]})
	ValidationError: Invalid value None (NoneType): float() argument must be a string or a number (at prices[2])

Similar to ``@accepts``, the ``@adapts`` decorator provides a convenient syntax
for adapting function inputs::

	>>> from valideer import adapts
	>>> @adapts(json={"prices": [AdaptTo(float)]})
	>>> def get_sum_price(json):
	>>>     return sum(json["prices"])
	>>> get_sum_price({"prices": ["2", "3.1", 1]})
	6.1
	>>> get_sum_price({"prices": ["2", "3f"]})
	ValidationError: Invalid value '3f' (str): invalid literal for float(): 3f (at json['prices'][1])
	>>> get_sum_price({"prices": ["2", 1, None]})
	ValidationError: Invalid value None (NoneType): float() argument must be a string or a number (at json['prices'][2])

Required and optional object properties
#######################################

By default object properties are considered optional unless they start with "+".
This default can be inverted by using the ``parsing`` context manager with
``required_properties=True``. In this case object properties are considered
required by default unless they start with "?". For example::

	validator = V.parse({
	    "+name": "string",
	    "duration": {
	        "+hours": "integer",
	        "+minutes": "integer",
	        "seconds": "integer"
	    }
	})

is equivalent to::

    with V.parsing(required_properties=True):
    	validator = V.parse({
    	    "name": "string",
    	    "?duration": {
    	        "hours": "integer",
    	        "minutes": "integer",
    	        "?seconds": "integer"
    	    }
    	})

Ignoring optional object property errors
########################################

By default an invalid object property value raises ``ValidationError``,
regardless of whether it's required or optional. It is possible to ignore invalid
values for optional properties by using the ``parsing`` context manager with
``ignore_optional_property_errors=True``::

    >>> schema = {
    ...     "+name": "string",
    ...     "price": "number",
    ... }
    >>> data = {"name": "wine", "price": "12.50"}
    >>> V.parse(schema).validate(data)
    valideer.base.ValidationError: Invalid value '12.50' (str): must be number (at price)
    >>> with V.parsing(ignore_optional_property_errors=True):
    ...     print V.parse(schema).validate(data)
    {'name': 'wine'}

Additional object properties
############################

Any properties that are not specified as either required or optional are allowed
by default. This default can be overriden by calling ``parsing`` with
``additional_properties=``

- ``False`` to disallow all additional properties
- ``Object.REMOVE`` to remove all additional properties from the adapted value
- any validator or parseable schema to validate all additional property
  values using this schema::

	>>> schema = {
	>>>     "name": "string",
	>>>     "duration": {
	>>>         "hours": "integer",
	>>>         "minutes": "integer",
	>>>     }
	>>> }
	>>> data = {"name": "lap", "duration": {"hours":3, "minutes":33, "seconds": 12}}
	>>> V.parse(schema).validate(data)
	{'duration': {'hours': 3, 'minutes': 33, 'seconds': 12}, 'name': 'lap'}
	>>> with V.parsing(additional_properties=False):
	...    V.parse(schema).validate(data)
	ValidationError: Invalid value {'hours': 3, 'seconds': 12, 'minutes': 33} (dict): additional properties: ['seconds'] (at duration)
	>>> with V.parsing(additional_properties=V.Object.REMOVE):
	...    print V.parse(schema).validate(data)
	{'duration': {'hours': 3, 'minutes': 33}, 'name': 'lap'}
	>>> with V.parsing(additional_properties="string"):
	...    V.parse(schema).validate(data)
	ValidationError: Invalid value 12 (int): must be string (at duration['seconds'])


Explicit Instantiation
######################

The usual way to create a validator is by passing an appropriate nested structure
to ``parse``, as outlined above.  This enables concise schema definitions with
minimal boilerplate. In case this seems too cryptic or "unpythonic" for your
taste, a validator can be also created explicitly from regular Python classes::

	>>> from valideer import Object, HomogeneousSequence, Number, String, Range
	>>> validator = Object(
	>>>     required={
	>>>         "id": Number(),
	>>>         "name": String(),
	>>>         "price": Range(Number(), min_value=0),
	>>>     },
	>>>     optional={
	>>>         "tags": HomogeneousSequence(String()),
	>>>         "stock": Object(
	>>>             optional={
	>>>                 "warehouse": Number(),
	>>>                 "retail": Number(),
	>>>             }
	>>>         )
	>>>     }
	>>> )


Built-in Validators
-------------------
``valideer`` comes with several predefined validators, each implemented as a
``Validator`` subclass. As shown above, some validator classes also support a
shortcut form that can be used to specify implicitly a validator instance.

Basic
#####

* ``valideer.Boolean()``: Accepts ``bool`` instances.

  :Shortcut: ``"boolean"``

* ``valideer.Integer()``: Accepts integers (``numbers.Integral`` instances),
  excluding ``bool``.

  :Shortcut: ``"integer"``

* ``valideer.Number()``: Accepts numbers (``numbers.Number`` instances),
  excluding ``bool``.

  :Shortcut: ``"number"``

* ``valideer.Date()``: Accepts ``datetime.date`` instances.

  :Shortcut: ``"date"``

* ``valideer.Time()``: Accepts ``datetime.time`` instances.

  :Shortcut: ``"time"``

* ``valideer.Datetime()``: Accepts ``datetime.datetime`` instances.

  :Shortcut: ``"datetime"``

* ``valideer.String(min_length=None, max_length=None)``: Accepts strings
  (``basestring`` instances).

  :Shortcut: ``"string"``

* ``valideer.Pattern(regexp)``: Accepts strings that match the given regular
  expression.

  :Shortcut: *Compiled regular expression*

* ``valideer.Condition(predicate, traps=Exception)``: Accepts values for which
  ``predicate(value)`` is true. Any raised exception that is instance of ``traps``
  is re-raised as a ``ValidationError``.

  :Shortcut: *Python function or method*.

* ``valideer.Type(accept_types=None, reject_types=None)``: Accepts instances of
  the given ``accept_types`` but excluding instances of ``reject_types``.

  :Shortcut: *Python type*. For example ``int`` is equivalent to ``valideer.Type(int)``.

* ``valideer.Enum(values)``: Accepts a fixed set of values.

  :Shortcut: *N/A*

Containers
##########

* ``valideer.HomogeneousSequence(item_schema=None, min_length=None, max_length=None)``:
  Accepts sequences (``collections.Sequence`` instances excluding strings) with
  elements that are valid for ``item_schema`` (if specified) and length between
  ``min_length`` and ``max_length`` (if specified).

  :Shortcut: [*item_schema*]

* ``valideer.HeterogeneousSequence(*item_schemas)``: Accepts fixed length
  sequences (``collections.Sequence`` instances excluding strings) where the
  ``i``-th element is valid for the ``i``-th ``item_schema``.

  :Shortcut: (*item_schema*, *item_schema*, ..., *item_schema*)

* ``valideer.Mapping(key_schema=None, value_schema=None)``: Accepts mappings
  (``collections.Mapping`` instances) with keys that are valid for ``key_schema``
  (if specified) and values that are valid for ``value_schema`` (if specified).

  :Shortcut: *N/A*

* ``valideer.Object(optional={}, required={}, additional=True)``: Accepts JSON-like
  objects (``collections.Mapping`` instances with string keys). Properties that
  are specified as ``optional`` or ``required`` are validated against the respective
  value schema. Any additional properties are either allowed (if ``additional``
  is True), disallowed (if ``additional`` is False) or validated against the
  ``additional`` schema.

  :Shortcut: {"*property*": *value_schema*, "*property*": *value_schema*, ...,
  			  "*property*": *value_schema*}. Properties that start with ``'+'``
  			  are required, the rest are optional and additional properties are
  			  allowed.

Adaptors
########

* ``valideer.AdaptBy(adaptor, traps=Exception)``: Adapts a value by calling
  ``adaptor(value)``. Any raised exception that is instance of ``traps`` is
  wrapped into a ``ValidationError``.

  :Shortcut: *N/A*

* ``valideer.AdaptTo(adaptor, traps=Exception, exact=False)``: Similar to
  ``AdaptBy`` but for types. Any value that is already instance of ``adaptor``
  is returned as is, otherwise it is adapted by calling ``adaptor(value)``. If
  ``exact`` is ``True``, instances of ``adaptor`` subclasses are also adapted.

  :Shortcut: *N/A*

Composite
#########

* ``valideer.Nullable(schema, default=None)``: Accepts values that are valid for
  ``schema`` or ``None``. ``default`` is returned as the adapted value of ``None``.
  ``default`` can also be a zero-argument callable, in which case the adapted
  value of ``None`` is ``default()``.

  :Shortcut: "?{*validator_name*}". For example ``"?integer"`` accepts any integer
  			 or ``None`` value.

* ``valideer.NonNullable(schema=None)``: Accepts values that are valid for
  ``schema`` (if specified) except for ``None``.

  :Shortcut: "+{*validator_name*}"

* ``valideer.Range(schema, min_value=None, max_value=None)``: Accepts values that
  are valid for ``schema`` and within the given ``[min_value, max_value]`` range.

  :Shortcut: *N/A*

* ``valideer.AnyOf(*schemas)``: Accepts values that are valid for at least one
  of the given ``schemas``.

  :Shortcut: *N/A*

* ``valideer.AllOf(*schemas)``: Accepts values that are valid for all the given
  ``schemas``.

  :Shortcut: *N/A*

* ``valideer.ChainOf(*schemas)``: Passes values through a chain of validator and
  adaptor ``schemas``.

  :Shortcut: *N/A*


User Defined Validators
-----------------------

The set of predefined validators listed above can be easily extended with user
defined validators. All you need to do is extend ``Validator`` (or a more
convenient subclass) and implement the ``validate`` method. Here is an example
of a custom validator that could be used to enforce minimal password strength::

	from valideer import String, ValidationError

	class Password(String):

	    name = "password"

	    def __init__(self, min_length=6, min_lower=1, min_upper=1, min_digits=0):
	        super(Password, self).__init__(min_length=min_length)
	        self.min_lower = min_lower
	        self.min_upper = min_upper
	        self.min_digits = min_digits

	    def validate(self, value, adapt=True):
	        super(Password, self).validate(value)

	        if len(filter(str.islower, value)) < self.min_lower:
	            raise ValidationError("At least %d lowercase characters required" % self.min_lower)

	        if len(filter(str.isupper, value)) < self.min_upper:
	            raise ValidationError("At least %d uppercase characters required" % self.min_upper)

	        if len(filter(str.isdigit, value)) < self.min_digits:
	            raise ValidationError("At least %d digits required" % self.min_digits)

	        return value

A few notes:

* The optional ``name`` class attribute creates a shortcut for referring to a
  default instance of the validator. In this example the string ``"password"``
  becomes an alias to a ``Password()`` instance.

* ``validate`` takes an optional boolean ``adapt`` parameter that defaults to
  ``True``. If it is ``False``, the validator is allowed to skip adaptation and
  perform validation only. This is basically an optimization hint that can be
  useful if adaptation happens to be significantly more expensive than validation.
  This isn't common though and so ``adapt`` is usually ignored.

Shortcut Registration
#####################

Setting a ``name`` class attribute is the simplest way to create a validator
shortcut. A shortcut can also be created explicitly with the ``valideer.register``
function::

	>>> import valideer as V
	>>> V.register("strong_password", Password(min_length=8, min_digits=1))
	>>> is_fair_password = V.parse("password").is_valid
	>>> is_strong_password = V.parse("strong_password").is_valid
	>>> for pwd in "passwd", "Passwd", "PASSWd", "Pas5word":
	>>>     print (pwd, is_fair_password(pwd), is_strong_password(pwd))
	('passwd', False, False)
	('Passwd', True, False)
	('PASSWd', True, False)
	('Pas5word', True, True)

Finally it is possible to parse arbitrary Python objects as validator shortcuts.
For example let's define a ``Not`` composite validator, a validator that accepts
a value if and only if it is rejected by another validator::

	class Not(Validator):

	    def __init__(self, schema):
	        self._validator = Validator.parse(schema)

	    def validate(self, value, adapt=True):
	        if self._validator.is_valid(value):
	            raise ValidationError("Should not be a %s" % self._validator.__class__.__name__, value)
	        return value

If we'd like to parse ``'!foo'`` strings as a shortcut for ``Not('foo')``, we
can do so with the ``valideer.register_factory`` decorator::

	>>> @V.register_factory
	>>> def NotFactory(obj):
	>>>     if isinstance(obj, basestring) and obj.startswith("!"):
	>>>         return Not(obj[1:])
	>>>
	>>> validate = V.parse({"i": "integer", "s": "!number"}).validate
	>>> validate({"i": 4, "s": ""})
	{'i': 4, 's': ''}
	>>> validate({"i": 4, "s": 1.2})
	ValidationError: Invalid value 1.2 (float): Should not be a Number (at s)


.. _valideer: https://github.com/podio/valideer
.. _JSON Schema: https://tools.ietf.org/html/draft-zyp-json-schema-03
.. _Podio API: https://developers.podio.com
.. _nose: http://pypi.python.org/pypi/nose
.. _coverage: http://pypi.python.org/pypi/coverage
.. _JSON schema example: http://en.wikipedia.org/wiki/JSON#Schema
.. _typecheck: http://pypi.python.org/pypi/typecheck
