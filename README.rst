========
valideer
========

`valideer`_ is a Python package for simple and extensible data validation and
adaptation that tries to "make easy things easy and hard things possible".
It started out as a simpler version of `JSON Schema`_ for validating JSON
structures but has since been extended to provide adaptation and handling of
arbitrary Python objects.

**Key features**:

- Supports both validation (check if a value is valid) and adaptation (convert
  a valid input to an appropriate output).
- Succinct: validation schemas can be specified in a declarative and extensible
  mini "language"; no need to define verbose schema classes upfront. A regular
  Python API is also available if the compact syntax is not your cup of tea.
- Batteries included: validators for most common types are included out of the box.
- Extensible: New custom validators and adaptors can be easily defined and
  registered.
- Informative error messages: Validation errors include the reason and exact
  location of the error.
- Agnostic: not tied to any particular framework or application domain (e.g.
  Web form validation).
- Well tested: Extensive test suite with 100% coverage.
- Production ready: Used for validating every access to the `Podio API`_.
- Licence: TBD.


Installation
------------

To install valideer, simply run::

    pip install valideer

Or for the latest version::

    git clone git@github.com:podio/valideer.git
    cd valideer
    python setup.py install

To run the tests you need to install nose_ and optionally coverage_ for coverage
report::

    $ pip install nose coverage
    $ nosetests --with-coverage --cover-package=valideer
	..............................................................................
	Name                  Stmts   Miss  Cover   Missing
	---------------------------------------------------
	valideer                  2      0   100%
	valideer.base            85      0   100%
	valideer.validators     299      0   100%
	---------------------------------------------------
	TOTAL                   386      0   100%
	----------------------------------------------------------------------
	Ran 78 tests in 0.064s


Basic Use
---------

Here's a demo of ``valideer`` using the following `JSON schema example`_::

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

This can be specified by passing a similar but more compact (and extensible, see
`Defining Custom Validators`_) structure to the ``Validator.parse`` static method::

	>>> from valideer import Validator, Range
	>>> product_schema = {
	...     "+id": "number",
	...     "+name": "string",
	...     "+price": Range("number", min_value=0),
	...     "tags": ["string"],
	...     "stock": {
	...         "warehouse": "number",
	...         "retail": "number",
	...     }
	... }
	>>> validator = Validator.parse(product_schema)

``Validator.parse`` returns a ``Validator`` instance, which can be then used to
validate or adapt inputs.

Validation
~~~~~~~~~~

To check if an input is valid call the ``Validator.is_valid`` method::

	>>> product1 = {
	...     "id": 1,
	...     "name": "Foo",
	...     "price": 123,
	...     "tags": ["Bar", "Eek"],
	...     "stock": {
	...         "warehouse": 300,
	...         "retail": 20
	...     }
	... }
	>>> validator.is_valid(product1)
	True
	>>> product2 = {
	...     "id": 1,
	...     "price": 123,
	... }
	>>> validator.is_valid(product2)
	False

Another option is to call ``Validator.validate``. If the input is invalid, it
raises ``ValidationError``::

	>>> validator.validate(product2)
	...
	valideer.base.ValidationError: Invalid value {'price': 123, 'id': 1}: Missing required properties: ['name']

For the common use case of validating inputs when entering a function, the ``@accepts``
decorator provides some handy syntax sugar (shamelessly stolen from typecheck_)::

	>>> from valideer import accepts
	>>> @accepts(product=product_schema, quantity="integer")
	... def get_total_price(product, quantity=1):
	...     return product["price"] * quantity
	...
	>>> get_total_price(product1, 2)
	246
	>>> get_total_price(product1, 0.5)
	...
	valideer.base.ValidationError: Invalid value 0.5: Must be int or long (at quantity)
	>>> get_total_price(product2)
	Traceback (most recent call last):
	...
	valideer.base.ValidationError: Invalid value {'price': 123, 'id': 1}: Missing required properties: ['name'] (at product)

Adaptation
~~~~~~~~~~

Often input data have to be converted from their original form before they are
ready to use; for example a number that may arrive as integer or string and
needs to be adapted to a float. Since validation and adaptation usually happen
simultaneously, ``Validator.validate`` returns the adapted version of the (valid)
input by default.

An existing class can be easily used as an adaptor by being wrapped in ``AdaptTo``::

	>>> from valideer import AdaptTo
	>>> adapt_prices = Validator.parse({"prices": [AdaptTo(float)]}).validate
	>>> adapt_prices({"prices": ["2", "3.1", 1]})
	{'prices': [2.0, 3.1, 1.0]}
	>>> adapt_prices({"prices": ["2", "3f"]})
	...
	valideer.base.ValidationError: Invalid value '3f': invalid literal for float(): 3f (at prices[1])
	>>> adapt_prices({"prices": ["2", 1, None]})
	...
	valideer.base.ValidationError: Invalid value None: float() argument must be a string or a number (at prices[2])

Similar to ``@accepts``, the ``@adapts`` decorator provides a handy syntax for
adapting function inputs::

	>>> from valideer import adapts
	>>> @adapts(json={"prices": [AdaptTo(float)]})
	... def get_sum_price(json):
	...     return sum(json["prices"])
	...
	>>> get_sum_price({"prices": ["2", "3.1", 1]})
	6.1
	>>> get_sum_price({"prices": ["2", "3f"]})
	...
	valideer.base.ValidationError: Invalid value '3f': invalid literal for float(): 3f (at json['prices'][1])
	>>> get_sum_price({"prices": ["2", 1, None]})
	...
	valideer.base.ValidationError: Invalid value None: float() argument must be a string or a number (at json['prices'][2])

The ``validate`` method also accepts an optional boolean ``adapt=True`` parameter;
if ``False``, the validator may choose to perform only validation. This can be
useful if adaptation happens to be significantly more expensive than validation.

Explicit validator creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The usual way to create a validator is by passing an appropriate nested structure
to ``Validator.parse``, as outlined above.  This allows for some concise schema
definitions with minimal boilerplate. In case this seems too "magic" or
"unpythonic" for your taste however, a validator can also be created explicitly
from regular Python classes. Here's how to instantiate explicitly an equivalent
``product`` validator::

	>>> from valideer import Object, HomogeneousSequence, Number, String, Range
	>>> validator = Object(
	...     required={
	...         "id": Number(),
	...         "name": String(),
	...         "price": Range(Number(), min_value=0),
	...     },
	...     optional={
	...         "tags": HomogeneousSequence(String()),
	...         "stock": Object(
	...             optional={
	...                 "warehouse": Number(),
	...                 "retail": Number(),
	...             }
	...         )
	...     }
	... )


Built-in Validators
-------------------
``valideer`` comes with several predefined validators, each implemented as a
``Validator`` subclass. A validator can optionally specify a "name" or a factory
function that can be used by ``Validator.parse`` as a shortcut for creating
instances of this validator. Here are the currently available validators:

Basic
~~~~~

* ``valideer.Boolean()``: Accepts ``bool`` instances.

  :Shortcut: ``"boolean"``

* ``valideer.Integer()``: Accepts integers (``int`` and ``long`` instances
  excluding ``bool``).

  :Shortcut: ``"integer"``

* ``valideer.Number()``: Accepts numbers (``int``, ``long``, ``float`` and ``Decimal``
  instances excluding ``bool``).

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

* ``valideer.Type(accept_types=None, reject_types=None)``: Accepts instances of
  the given ``accept_types`` but excluding instances of ``reject_types``.

  :Shortcut: *Python type*

* ``valideer.Enum(values)``: Accepts a fixed set of values.

  :Shortcut: *N/A*

Containers
~~~~~~~~~~

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

* ``valideer.Object(optional={}, required={})``: Accepts JSON-like objects
  (``collections.Mapping`` instances with string keys). Properties that are
  specified as ``optional`` or ``required`` are validated against the respective
  value schema. Any additional unspecified properties are implicitly valid.

  :Shortcut: {"*property*": *value_schema*, "*property*": *value_schema*, ...,
  			  "*property*": *value_schema*}. Properties that start with ``+``
  			  are required, the rest are optional.

Adaptors
~~~~~~~~

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
~~~~~~~~~

* ``valideer.Nullable(schema, default=None)``: Accepts values that are valid for
  ``schema`` or ``None``. ``default`` is returned as the adapted value of ``None``.

  :Shortcut: "?{*validator_name*}". For example "?integer" accepts integers and
  			 ``None``.

* ``valideer.NonNullable(schema=None)``: Accepts values that are valid for
  ``schema`` (if specified) except for ``None``.

  :Shortcut: "+{*validator_name*}"

* ``valideer.Range(schema, min_value=None, max_value=None)``: Accepts values that
  are valid for ``schema`` and within the given ``[min_value, max_value]`` range.

  :Shortcut: *N/A*

* ``valideer.AnyOf(*schemas)``: Accepts values that are valid for at least one
  of the component ``schemas``.

  :Shortcut: *N/A*


Defining Custom Validators
--------------------------
*TODO*

.. _valideer: https://github.com/podio/valideer
.. _JSON Schema: https://tools.ietf.org/html/draft-zyp-json-schema-03
.. _Podio API: https://developers.podio.com
.. _nose: http://pypi.python.org/pypi/nose
.. _coverage: http://pypi.python.org/pypi/coverage
.. _JSON schema example: http://en.wikipedia.org/wiki/JSON#Schema
.. _typecheck: http://pypi.python.org/pypi/typecheck
