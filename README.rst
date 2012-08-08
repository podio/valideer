========
valideer
========

`valideer`_ is a Python package for simple and extensible data validation and
adaptation (conversion). It tries to *make easy things trivial and hard
things possible*. It started out as a simpler version of `JSON Schema`_ for
validating JSON structures but has since been extended to handle arbitrary
Python objects.

**Key features**:

- Supports both validation (check if a value is valid) and adaptation (convert
  a valid input to a desired output).
- Succinct: validation schemas can be specified in a declarative and extensible
  mini "language"; no need to define verbose schema classes upfront. A more
  familiar regular Python API is also available if the compact syntax is not
  your cup of tea.
- Batteries included: validators for most common types are included out of the box.
- Extensible: New custom validators and adaptors can be easily defined and
  registered.
- Helpful: Validation errors include the reason and exact location of the error.
- Agnostic: not tied to any particular framework or application domain (e.g.
  Web form validation). Any Python values and function inputs can be validated
  and adapted.
- Tested: Extensive test suite with 100% coverage.
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

Here's a demo of ``valideer`` using the following `Wikipedia JSON schema example`_::

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

This can be specified in ``valideer`` by passing a similar but more compact (and
extensible, see `Defining Custom Validators`_) structure to the ``Validator.parse()``
static method::

	>>> from valideer import Validator, Range
	>>> validator = Validator.parse({
	...     "+id": "number",
	...     "+name": "string",
	...     "+price": Range("number", min_value=0),
	...     "tags": ["string"],
	...     "stock": {
	...         "warehouse": "number",
	...         "retail": "number",
	...     }
	... })

``Validator.parse`` returns a ``Validator`` instance, which can be used to
validate and/or adapt input.

Validation
~~~~~~~~~~
To check if an input is valid call the ``is_valid()`` method:

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

Another option is to call ``validate()``. If the input is invalid, it raises a
``ValidationError``::

	>>> from valideer import ValidationError
	>>> try:
	...     validator.validate(product2)
	... except ValidationError as ex:
	...     print ex
	...
	Invalid value {'price': 123, 'id': 1}: Missing required properties: ['name']

Adaptation
~~~~~~~~~~

Validating and adapting function inputs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Using the Python API
~~~~~~~~~~~~~~~~~~~~


Builtin Validators
-------------------


Defining Custom Validators
--------------------------


.. _valideer: https://github.com/podio/valideer
.. _JSON Schema: http://en.wikipedia.org/wiki/JSON#Schema
.. _Podio API: https://developers.podio.com
.. _nose: http://pypi.python.org/pypi/nose
.. _coverage: http://pypi.python.org/pypi/coverage
.. _Wikipedia JSON schema example: http://en.wikipedia.org/wiki/JSON#Schema
