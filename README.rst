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
	>>> @adapts(json={"prices": [AdaptBy(float)]})
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


Explicit schema definition
~~~~~~~~~~~~~~~~~~~~~~~~~~
*TODO*

Built-in Validators
-------------------
*TODO*

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
