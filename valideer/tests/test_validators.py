from datetime import date, datetime
from decimal import Decimal
from functools import partial
import collections
import json
import re
import unittest
import valideer as V


class Fraction(V.Type):
    name = "fraction"
    accept_types = (float, complex, Decimal)

class Gender(V.Enum):
    name = "gender"
    values = ("male", "female", "it's complicated")


class TestValidator(unittest.TestCase):

    parse = staticmethod(V.parse)

    def setUp(self):
        V.Object.REQUIRED_PROPERTIES = True
        V.base.reset_type_names()
        self.complex_validator = self.parse({
            "n": "number",
            "?i": V.Nullable("integer", 0),
            "?b": bool,
            "?e": V.Enum(["r", "g", "b"]),
            "?d": V.AnyOf("date", "datetime"),
            "?s": V.String(min_length=1, max_length=8),
            "?p": V.Nullable(re.compile(r"\d{1,4}$")),
            "?l": [{"+s2": "string"}],
            "?t": (unicode, "number"),
            "?h": V.Mapping(int, ["string"]),
            "?o": V.NonNullable({"+i2": "integer"}),
        })

    def test_none(self):
        for obj in ["boolean", "integer", "number", "string",
                    V.HomogeneousSequence, V.HeterogeneousSequence,
                    V.Mapping, V.Object, int, float, str, unicode,
                    Fraction, Fraction(), Gender, Gender()]:
            self.assertFalse(self.parse(obj).is_valid(None))

    def test_boolean(self):
        for obj in "boolean", V.Boolean, V.Boolean():
            self._testValidation(obj,
                                 valid=[True, False],
                                 invalid=[1, 1.1, "foo", u"bar", {}, []])

    def test_integer(self):
        for obj in "integer", V.Integer, V.Integer():
            self._testValidation(obj,
                                 valid=[1],
                                 invalid=[1.1, "foo", u"bar", {}, [], False, True])

    def test_int(self):
        # bools are ints
        self._testValidation(int,
                             valid=[1, True, False],
                             invalid=[1.1, "foo", u"bar", {}, []])

    def test_number(self):
        for obj in "number", V.Number, V.Number():
            self._testValidation(obj,
                                 valid=[1, 1.1],
                                 invalid=["foo", u"bar", {}, [], False, True])

    def test_float(self):
        self._testValidation(float,
                             valid=[1.1],
                             invalid=[1, "foo", u"bar", {}, [], False, True])

    def test_string(self):
        for obj in "string", V.String, V.String():
            self._testValidation(obj,
                                 valid=["foo", u"bar"],
                                 invalid=[1, 1.1, {}, [], False, True])

    def test_string_min_length(self):
        self._testValidation(V.String(min_length=2),
                             valid=["foo", u"fo"],
                             invalid=[u"f", "", False])

    def test_string_max_length(self):
        self._testValidation(V.String(max_length=2),
                             valid=["", "f", u"fo"],
                             invalid=[u"foo", [1, 2, 3]])

    def test_pattern(self):
        self._testValidation(re.compile(r"a*$"),
                             valid=["aaa"],
                             invalid=[u"aba", "baa"])

    def test_range(self):
        self._testValidation(V.Range("integer", 1),
                             valid=[1, 2, 3],
                             invalid=[0, -1])
        self._testValidation(V.Range("integer", max_value=2),
                             valid=[-1, 0, 1, 2],
                             invalid=[3])
        self._testValidation(V.Range("integer", 1, 2),
                             valid=[1, 2],
                             invalid=[-1, 0, 3])
        self._testValidation(V.Range(min_value=1, max_value=2),
                             valid=[1, 2],
                             invalid=[-1, 0, 3])

    def test_homogeneous_sequence(self):
        for obj in V.HomogeneousSequence, V.HomogeneousSequence():
            self._testValidation(obj,
                                 valid=[[], [1], (1, 2), [1, (2, 3), 4]],
                                 invalid=[1, 1.1, "foo", u"bar", {}, False, True])
        self._testValidation(["number"],
                             valid=[[], [1, 2.1, 3L], (1, 4L, 6)],
                             invalid=[[1, 2.1, 3L, u"x"]])

    def test_heterogeneous_sequence(self):
        for obj in V.HeterogeneousSequence, V.HeterogeneousSequence():
            self._testValidation(obj,
                                 valid=[(), []],
                                 invalid=[1, 1.1, "foo", u"bar", {}, False, True])
        self._testValidation(("string", "number"),
                             valid=[("a", 2), [u"b", 4.1]],
                             invalid=[[], (), (2, "a"), ("a", "b"), (1, 2)])

    def test_sequence_min_length(self):
        self._testValidation(V.HomogeneousSequence(int, min_length=2),
                             valid=[[1, 2, 4], (1, 2)],
                             invalid=[[1], [], (), "123", "", False])

    def test_sequence_max_length(self):
        self._testValidation(V.HomogeneousSequence(int, max_length=2),
                             valid=[[], (), (1,), (1, 2), [1, 2]],
                             invalid=[[1, 2, 3], "123", "f"])

    def test_mapping(self):
        for obj in V.Mapping, V.Mapping():
            self._testValidation(obj,
                                 valid=[{}, {"foo": 3}],
                                 invalid=[1, 1.1, "foo", u"bar", [], False, True])
        self._testValidation(V.Mapping("string", "number"),
                             valid=[{"foo": 3},
                                    {"foo": 3, u"bar":-2.1, "baz":Decimal("12.3")}],
                             invalid=[{"foo": 3, ("bar",):-2.1},
                                      {"foo": 3, "bar":"2.1"}])

    def test_object(self):
        for obj in V.Object, V.Object():
            self._testValidation(obj,
                                 valid=[{}, {"foo": 3}],
                                 invalid=[1, 1.1, "foo", u"bar", [], False, True])
        self._testValidation({"foo": "number", "bar": "string"},
                             valid=[{"foo": 1, "bar": "baz"},
                                    {"foo": 1, "bar": "baz", "quux": 42}],
                             invalid=[{"foo": 1, "bar": []},
                                      {"foo": "baz", "bar": 2.3}])

    def test_required_properties_global(self):
        self._testValidation({"foo": "number", "?bar": "boolean", "baz":"string"},
                             valid=[{"foo":-23., "baz":"yo"}],
                             invalid=[{},
                                      {"bar":True},
                                      {"baz":"yo"},
                                      {"foo":3},
                                      {"bar":False, "baz":"yo"},
                                      {"bar":True, "foo":3.1}])

    def test_required_properties_parse_parameter(self):
        schema = {
            "foo": "number",
            "?bar": "boolean",
            "?nested": [{
                "baz": "string"
            }]
        }
        missing_properties = [{}, {"bar":True}, {"foo":3, "nested":[{}]}]
        for _ in xrange(3):
            self._testValidation(V.parse(schema, required_properties=True),
                                 invalid=missing_properties)
            self._testValidation(V.parse(schema, required_properties=False),
                                 valid=missing_properties)

    def test_parsing_required_properties(self):
        get_schema = lambda: {
            "foo": V.Nullable("number"),
            "?nested": [V.Nullable({
                "baz": "string"
            })]
        }
        valid = [{"foo":3, "nested":[None]}]
        missing_properties = [{}, {"foo":3, "nested":[{}]}]
        for _ in xrange(3):
            with V.parsing(required_properties=False):
                self._testValidation(get_schema(),
                                     valid=valid + missing_properties)

            with V.parsing(required_properties=True):
                self._testValidation(get_schema(),
                                     valid=valid, invalid=missing_properties)

            # gotcha: calling parse() with required_properties=True is not
            # equivalent to the above call because the V.Nullable() calls in
            # get_schema have already called implicitly parse() without parameters.
            if V.Object.REQUIRED_PROPERTIES:
                self._testValidation(V.parse(get_schema(), required_properties=True),
                                     invalid=[missing_properties[1]])
            else:
                self._testValidation(V.parse(get_schema(), required_properties=True),
                                     valid=[missing_properties[1]])

    def test_adapt_missing_property(self):
        self._testValidation({"foo": "number", "?bar": V.Nullable("boolean", False)},
                             adapted=[({"foo":-12}, {"foo":-12, "bar":False})])

    def test_no_additional_properties(self):
        self._testValidation(V.Object(required={"foo": "number"},
                                      optional={"bar": "string"},
                                      additional=False),
                             valid=[{"foo":23},
                                    {"foo":-23., "bar":"yo"}],
                             invalid=[{"foo":23, "xyz":1},
                                      {"foo":-23., "bar":"yo", "xyz":1}]
                             )

    def test_remove_additional_properties(self):
        self._testValidation(V.Object(required={"foo": "number"},
                                      optional={"bar": "string"},
                                      additional=V.Object.REMOVE),
                             adapted=[({"foo":23}, {"foo":23}),
                                      ({"foo":-23., "bar":"yo"}, {"foo":-23., "bar":"yo"}),
                                      ({"foo":23, "xyz":1}, {"foo":23}),
                                      ({"foo":-23., "bar":"yo", "xyz":1}, {"foo":-23., "bar":"yo"})]
                             )

    def test_additional_properties_schema(self):
        self._testValidation(V.Object(required={"foo": "number"},
                                      optional={"bar": "string"},
                                      additional="boolean"),
                             valid=[{"foo":23, "bar":"yo", "x1":True, "x2":False}],
                             invalid=[{"foo":23, "x1":1},
                                      {"foo":-23., "bar":"yo", "x1":True, "x2":0}]
                             )

    def test_additional_properties_parse_parameter(self):
        schema = {
            "?bar": "boolean",
            "?nested": [{
                "?baz": "integer"
            }]
        }
        values = [{"x1": "yes"},
                  {"bar":True, "nested": [{"x1": "yes"}]}]
        for _ in xrange(3):
            self._testValidation(V.parse(schema, additional_properties=True),
                                 valid=values)
            self._testValidation(V.parse(schema, additional_properties=False),
                                 invalid=values)
            self._testValidation(V.parse(schema, additional_properties=V.Object.REMOVE),
                                 adapted=[(values[0], {}),
                                          (values[1], {"bar":True, "nested": [{}]})])
            self._testValidation(V.parse(schema, additional_properties="string"),
                                 valid=values,
                                 invalid=[{"x1": 42},
                                          {"bar":True, "nested": [{"x1": 42}]}])

    def test_parsing_additional_properties(self):
        get_schema = lambda: {
            "?bar": "boolean",
            "?nested": [V.Nullable({
                "?baz": "integer"
            })]
        }
        values = [{"x1": "yes"},
                  {"bar":True, "nested": [{"x1": "yes"}]}]
        for _ in xrange(3):
            with V.parsing(additional_properties=True):
                self._testValidation(get_schema(), valid=values)

            with V.parsing(additional_properties=False):
                self._testValidation(get_schema(), invalid=values)
            # gotcha: calling parse() with additional_properties=False is not
            # equivalent to the above call because the V.Nullable() calls in
            # get_schema have already called implicitly parse() without parameters.
            # The 'additional_properties' parameter effectively is applied at
            # the top level dict only
            self._testValidation(V.parse(get_schema(), additional_properties=False),
                                 invalid=values[:1], valid=values[1:])

            with V.parsing(additional_properties=V.Object.REMOVE):
                self._testValidation(get_schema(),
                                     adapted=[(values[0], {}),
                                              (values[1], {"bar":True, "nested": [{}]})])
            # same gotcha as above
            self._testValidation(V.parse(get_schema(), additional_properties=V.Object.REMOVE),
                                 adapted=[(values[0], {}),
                                          (values[1], values[1])])

            with V.parsing(additional_properties="string"):
                self._testValidation(get_schema(),
                                     valid=values,
                                     invalid=[{"x1": 42},
                                              {"bar":True, "nested": [{"x1": 42}]}])
            # same gotcha as above
            self._testValidation(V.parse(get_schema(), additional_properties="string"),
                                 invalid=[{"x1": 42}],
                                 valid=[{"bar":True, "nested": [{"x1": 42}]}])

    def test_nested_parsing(self):
        get_schema = lambda: {
            "bar": "integer",
            "?nested": [V.Nullable({
                "baz": "number"
            })]
        }
        values = [
            {"bar": 1},
            {"bar": 1, "nested":[{"baz": 0}, None]},
            {"bar": 1, "xx":2},
            {"bar": 1, "nested": [{"baz": 2.1, "xx": 1}]},
            {},
            {"bar": 1, "nested": [{}]},
        ]

        if V.Object.REQUIRED_PROPERTIES:
            self._testValidation(get_schema(),
                                valid=values[:4], invalid=values[4:])
        else:
            self._testValidation(get_schema(), valid=values)

        with V.parsing(required_properties=True):
            self._testValidation(get_schema(),
                                valid=values[:4], invalid=values[4:])
            with V.parsing(additional_properties=False):
                self._testValidation(get_schema(),
                                    valid=values[:2], invalid=values[2:])
            self._testValidation(get_schema(),
                                valid=values[:4], invalid=values[4:])

        if V.Object.REQUIRED_PROPERTIES:
            self._testValidation(get_schema(),
                                valid=values[:4], invalid=values[4:])
        else:
            self._testValidation(get_schema(), valid=values)

    def test_enum(self):
        self._testValidation(V.Enum([1, 2, 3]),
                             valid=[1, 2, 3], invalid=[0, 4, "1", [1]])
        self._testValidation(V.Enum([u"foo", u"bar"]),
                             valid=["foo", "bar"], invalid=["", "fooabar", ["foo"]])
        self._testValidation(V.Enum([True]),
                             valid=[True], invalid=[False, [True]])
        self._testValidation(V.Enum([{"foo" : u"bar"}]),
                             valid=[{u"foo" : "bar"}])
        self._testValidation(V.Enum([{"foo" : u"quux"}]),
                             invalid=[{u"foo" : u"bar"}])

    def test_enum_class(self):
        for obj in "gender", Gender, Gender():
            self._testValidation(obj,
                                 valid=["male", "female", "it's complicated"],
                                 invalid=["other", ""])

    def test_nullable(self):
        for obj in "?integer", V.Nullable(V.Integer()), V.Nullable("+integer"):
            self._testValidation(obj,
                                 valid=[None, 0],
                                 invalid=[1.1, True, False])
        self._testValidation(V.Nullable(["?string"]),
                             valid=[None, [], ["foo"], [None], ["foo", None]],
                             invalid=["", [None, "foo", 1]])

    def test_nullable_with_default(self):
        self._testValidation(V.Nullable("integer", -1),
                             adapted=[(None, -1), (0, 0)],
                             invalid=[1.1, True, False])
        self._testValidation(V.Nullable("integer", lambda:-1),
                             adapted=[(None, -1), (0, 0)],
                             invalid=[1.1, True, False])

    def test_nonnullable(self):
        for obj in V.NonNullable, V.NonNullable():
            self._testValidation(obj,
                                 invalid=[None],
                                 valid=[0, False, "", (), []])
        for obj in "+integer", V.NonNullable(V.Integer()), V.NonNullable("?integer"):
            self._testValidation(obj,
                                 invalid=[None, False],
                                 valid=[0, 2L])

    def test_anyof(self):
        self._testValidation(V.AnyOf("integer", {"foo" : "integer"}),
                             valid=[1, {"foo" : 1}],
                             invalid=[{"foo" : 1.1}])

    def test_allof(self):
        self._testValidation(V.AllOf({"id": "integer"}, V.Mapping("string", "number")),
                             valid=[{"id": 3}, {"id": 3, "bar": 4.5}],
                             invalid=[{"id" : 1.1, "bar":4.5},
                                      {"id" : 3, "bar": True},
                                      {"id" : 3, 12: 4.5}])

        self._testValidation(V.AllOf("number",
                                     lambda x: x > 0,
                                     V.AdaptBy(datetime.fromtimestamp)),
                            adapted=[(1373475820, datetime(2013, 7, 10, 20, 3, 40))],
                            invalid=["1373475820", -1373475820])

    def test_chainof(self):
        self._testValidation(V.ChainOf(V.AdaptTo(int),
                                       V.Condition(lambda x: x > 0),
                                       V.AdaptBy(datetime.fromtimestamp)),
                            adapted=[(1373475820, datetime(2013, 7, 10, 20, 3, 40)),
                                     ("1373475820", datetime(2013, 7, 10, 20, 3, 40))],
                            invalid=["nan", -1373475820])

    def test_condition(self):
        def is_odd(n): return n % 2 == 1
        is_even = lambda n: n % 2 == 0

        class C(object):
            def is_odd_method(self, n): return is_odd(n)
            def is_even_method(self, n): return is_even(n)
            is_odd_static = staticmethod(is_odd)
            is_even_static = staticmethod(is_even)

        for obj in is_odd, C().is_odd_method, C.is_odd_static:
            self._testValidation(obj,
                                 valid=[1, 3L, -11, 9.0, True],
                                 invalid=[6, 2.1, False, "1", []])

        for obj in is_even, C().is_even_method, C.is_even_static:
            self._testValidation(obj,
                                 valid=[6, 2L, -42, 4.0, 0, 0.0, False],
                                 invalid=[1, 2.1, True, "2", []])

        self._testValidation(str.isalnum,
                             valid=["abc", "123", "ab32c"],
                             invalid=["a+b", "a 1", "", True, 2])

        self.assertRaises(TypeError, V.Condition, C)
        self.assertRaises(TypeError, V.Condition(is_even, traps=()).validate, [2, 4])


    def test_adapt_by(self):
        self._testValidation(V.AdaptBy(hex, traps=TypeError),
                             invalid=[1.2, "1"],
                             adapted=[(255, "0xff"), (0, "0x0")])
        self._testValidation(V.AdaptBy(int, traps=(ValueError, TypeError)),
                             invalid=["12b", "1.2", {}, (), []],
                             adapted=[(12, 12), ("12", 12), (1.2, 1)])
        self.assertRaises(TypeError, V.AdaptBy(hex, traps=()).validate, 1.2)

    def test_adapt_to(self):
        self.assertRaises(TypeError, V.AdaptTo, hex)
        for exact in False, True:
            self._testValidation(V.AdaptTo(int, traps=(ValueError, TypeError), exact=exact),
                                 invalid=["12b", "1.2", {}, (), []],
                                 adapted=[(12, 12), ("12", 12), (1.2, 1)])

        class smallint(int):
            pass
        i = smallint(2)
        self.assertIs(V.AdaptTo(int).validate(i), i)
        self.assertIsNot(V.AdaptTo(int, exact=True).validate(i), i)

    def test_fraction(self):
        for obj in "fraction", Fraction, Fraction():
            self._testValidation(obj,
                                 valid=[1.1, 0j, 5 + 3j, Decimal(1) / Decimal(8)],
                                 invalid=[1, "foo", u"bar", {}, [], False, True])

    def test_reject_types(self):
        ExceptionValidator = V.Type(accept_types=Exception, reject_types=Warning)
        ExceptionValidator.validate(KeyError())
        self.assertRaises(V.ValidationError, ExceptionValidator.validate, UserWarning())

    def test_accepts(self):
        @V.accepts(a="fraction", b=int, body={"+field_ids": ["integer"],
                                               "?is_ok": bool,
                                               "?sex": "gender"})
        def f(a, b=1, **body):
            pass

        valid = [
            partial(f, 2.0, field_ids=[]),
            partial(f, Decimal(1), b=5, field_ids=[1], is_ok=True),
            partial(f, a=3j, b= -1, field_ids=[1L, 2, 5L], sex="male"),
            partial(f, 5 + 3j, 0, field_ids=[-12L, 0, 0L], is_ok=False, sex="female"),
            partial(f, 2.0, field_ids=[], additional="extra param allowed"),
        ]

        invalid = [
            partial(f, 1), # 'a' is not a fraction
            partial(f, 1.0), # missing 'field_ids' from body
            partial(f, 1.0, b=4.1, field_ids=[]), # 'b' is not int
            partial(f, 1.0, b=2, field_ids=3), # 'field_ids' is not a list
            partial(f, 1.0, b=1, field_ids=[3.0]), # 'field_ids[0]' is not a integer
            partial(f, 1.0, b=1, field_ids=[], is_ok=1), # 'is_ok' is not bool
            partial(f, 1.0, b=1, field_ids=[], sex="m"), # 'sex' is not a gender
        ]

        for fcall in valid:
            fcall()
        for fcall in invalid:
            self.assertRaises(V.ValidationError, fcall)

    def test_adapts(self):
        @V.adapts(body={"+field_ids": ["integer"],
                         "?scores": V.Mapping("string", float),
                         "?users": [{
                            "+name": ("+string", "+string"),
                            "?sex": "gender",
                            "?active": V.Nullable("boolean", True),
                         }]})
        def f(body):
            return body

        adapted = f({
                    "field_ids": [1, 5],
                    "scores": {"foo": 23.1, "bar": 2.0},
                    "users": [
                        {"name": ("Nick", "C"), "sex": "male"},
                        {"name": ("Kim", "B"), "active": False},
                        {"name": ("Joe", "M"), "active": None},
                    ]})

        self.assertEqual(adapted["field_ids"], [1, 5])
        self.assertEqual(adapted["scores"]["foo"], 23.1)
        self.assertEqual(adapted["scores"]["bar"], 2.0)

        self.assertEqual(adapted["users"][0]["name"], ("Nick", "C"))
        self.assertEqual(adapted["users"][0]["sex"], "male")
        self.assertEqual(adapted["users"][0]["active"], True)

        self.assertEqual(adapted["users"][1]["name"], ("Kim", "B"))
        self.assertEqual(adapted["users"][1].get("sex"), None)
        self.assertEqual(adapted["users"][1]["active"], False)

        self.assertEqual(adapted["users"][2]["name"], ("Joe", "M"))
        self.assertEqual(adapted["users"][2].get("sex"), None)
        self.assertEqual(adapted["users"][2].get("active"), True)

        invalid = [
            # missing 'field_ids' from body
            partial(f, {}),
            # score value is not float
            partial(f, {"field_ids": [], "scores":{"a": "2.3"}}),
            # 'name' is not a length-2 tuple
            partial(f, {"field_ids": [], "users":[{"name": ("Bob", "R", "Junior")}]}),
            # name[1] is not a string
            partial(f, {"field_ids": [], "users":[{"name": ("Bob", 12)}]}),
            # name[1] is required
            partial(f, {"field_ids": [], "users":[{"name": ("Bob", None)}]}),
        ]
        for fcall in invalid:
            self.assertRaises(V.ValidationError, fcall)

    def test_adapts_varargs(self):
        @V.adapts(a="integer",
                   b="number",
                   nums=["number"])
        def f(a, b=1, *nums, **params):
            return a * b + sum(nums)

        self.assertEqual(f(2), 2)
        self.assertEqual(f(2, b=2), 4)
        self.assertEqual(f(2, 2.5, 3), 8)
        self.assertEqual(f(2, 2.5, 3, -2.5), 5.5)

    def test_adapts_kwargs(self):
        @V.adapts(a="integer",
                   b="number",
                   params={"?foo": int, "?bar": float})
        def f(a, b=1, **params):
            return a * b + params.get("foo", 1) * params.get("bar", 0.0)

        self.assertEqual(f(1), 1)
        self.assertEqual(f(1, 2), 2)
        self.assertEqual(f(1, b=2.5, foo=3), 2.5)
        self.assertEqual(f(1, b=2.5, bar=3.5), 6.0)
        self.assertEqual(f(1, foo=2, bar=3.5), 8.0)
        self.assertEqual(f(1, b=2.5, foo=2, bar=3.5), 9.5)

    def test_adapts_varargs_kwargs(self):
        @V.adapts(a="integer",
                   b="number",
                   nums=["number"],
                   params={"?foo": int, "?bar": float})
        def f(a, b=1, *nums, **params):
            return a * b + sum(nums) + params.get("foo", 1) * params.get("bar", 0.0)

        self.assertEqual(f(2), 2)
        self.assertEqual(f(2, b=2), 4)
        self.assertEqual(f(2, 2.5, 3), 8)
        self.assertEqual(f(2, 2.5, 3, -2.5), 5.5)
        self.assertEqual(f(1, b=2.5, foo=3), 2.5)
        self.assertEqual(f(1, b=2.5, bar=3.5), 6.0)
        self.assertEqual(f(1, foo=2, bar=3.5), 8.0)
        self.assertEqual(f(1, b=2.5, foo=2, bar=3.5), 9.5)
        self.assertEqual(f(2, 2.5, 3, foo=2), 8.0)
        self.assertEqual(f(2, 2.5, 3, bar=3.5), 11.5)
        self.assertEqual(f(2, 2.5, 3, foo=2, bar=3.5), 15.0)

    def test_schema_errors(self):
        for obj in [
            True,
            1,
            3.2,
            "foo",
            object(),
            ["foo"],
            {"field": "foo"},
        ]:
            self.assertRaises(V.SchemaError, self.parse, obj)

    def test_not_implemented_validation(self):
        class MyValidator(V.Validator):
            pass

        validator = MyValidator()
        self.assertRaises(NotImplementedError, validator.validate, 1)

    def test_register(self):
        for register in V.register, V.Validator.register:
            register("to_int", V.AdaptTo(int, traps=(ValueError, TypeError)))
            self._testValidation("to_int",
                                 invalid=["12b", "1.2"],
                                 adapted=[(12, 12), ("12", 12), (1.2, 1)])

            self.assertRaises(TypeError, register, "to_int", int)

    def test_complex_validation(self):

        for valid in [
            {'n': 2},
            {'n': 2.1, 'i':3},
            {'n':-1, 'b':False},
            {'n': Decimal(3), 'e': "r"},
            {'n': 2L, 'd': datetime.now()},
            {'n': 0, 'd': date.today()},
            {'n': 0, 's': "abc"},
            {'n': 0, 'p': None},
            {'n': 0, 'p': "123"},
            {'n': 0, 'l': []},
            {'n': 0, 'l': [{"s2": "foo"}, {"s2": ""}]},
            {'n': 0, 't': (u"joe", 3.1)},
            {'n': 0, 'h': {5: ["foo", u"bar"], 0: []}},
            {'n': 0, 'o': {"i2": 3}},
        ]:
            self.complex_validator.validate(valid, adapt=False)

        for invalid in [
            None,
            {},
            {'n': None},
            {'n': True},
            {'n': 1, 'e': None},
            {'n': 1, 'e': "a"},
            {'n': 1, 'd': None},
            {'n': 1, 's': None},
            {'n': 1, 's': ''},
            {'n': 1, 's': '123456789'},
            {'n': 1, 'p': '123a'},
            {'n': 1, 'l': None},
            {'n': 1, 'l': [None]},
            {'n': 1, 'l': [{}]},
            {'n': 1, 'l': [{'s2': None}]},
            {'n': 1, 'l': [{'s2': 1}]},
            {'n': 1, 't': ()},
            {'n': 0, 't': (3.1, u"joe")},
            {'n': 0, 't': (u"joe", None)},
            {'n': 1, 'h': {5: ["foo", u"bar"], "0": []}},
            {'n': 1, 'h': {5: ["foo", 2.1], 0: []}},
            {'n': 1, 'o': {}},
            {'n': 1, 'o': {"i2": "2"}},
        ]:
            self.assertRaises(V.ValidationError,
                              self.complex_validator.validate, invalid, adapt=False)

    def test_complex_adaptation(self):
        for value in [
            {'n': 2},
            {'n': 2.1, 'i':3},
            {'n':-1, 'b':False},
            {'n': Decimal(3), 'e': "r"},
            {'n': 2L, 'd': datetime.now()},
            {'n': 0, 'd': date.today()},
            {'n': 0, 's': "abc"},
            {'n': 0, 'p': None},
            {'n': 0, 'p': "123"},
            {'n': 0, 'l': []},
            {'n': 0, 'l': [{"s2": "foo"}, {"s2": ""}]},
            {'n': 0, 't': (u"joe", 3.1)},
            {'n': 0, 'h': {5: ["foo", u"bar"], 0: []}},
            {'n': 0, 'o': {"i2": 3}},
        ]:
            adapted = self.complex_validator.validate(value)
            self.assertTrue(isinstance(adapted["n"], (int, long, float, Decimal)))
            self.assertTrue(isinstance(adapted["i"], (int, long)))
            self.assertTrue(adapted.get("b") is None or isinstance(adapted["b"], bool))
            self.assertTrue(adapted.get("d") is None or isinstance(adapted["d"], (date, datetime)))
            self.assertTrue(adapted.get("e") is None or adapted["e"] in "rgb")
            self.assertTrue(adapted.get("s") is None or isinstance(adapted["s"], basestring))
            self.assertTrue(adapted.get("l") is None or isinstance(adapted["l"], list))
            self.assertTrue(adapted.get("t") is None or isinstance(adapted["t"], tuple))
            self.assertTrue(adapted.get("h") is None or isinstance(adapted["h"], dict))
            if adapted.get("l") is not None:
                self.assertTrue(all(isinstance(item["s2"], basestring)
                                    for item in adapted["l"]))
            if adapted.get("t") is not None:
                self.assertEqual(len(adapted["t"]), 2)
                self.assertTrue(isinstance(adapted["t"][0], unicode))
                self.assertTrue(isinstance(adapted["t"][1], float))
            if adapted.get("h") is not None:
                self.assertTrue(all(isinstance(key, int)
                                    for key in adapted["h"].keys()))
                self.assertTrue(all(isinstance(value_item, basestring)
                                    for value in adapted["h"].values()
                                    for value_item in value))
            if adapted.get("o") is not None:
                self.assertTrue(isinstance(adapted["o"]["i2"], (int, long)))

    def test_humanized_names(self):
        class DummyValidator(V.Validator):
            name = "dummy"
            def validate(self, value, adapt=True):
                return value

        self.assertEqual(DummyValidator().humanized_name, "dummy")
        self.assertEqual(V.Nullable(DummyValidator()).humanized_name, "dummy or null")
        self.assertEqual(V.AnyOf("boolean", DummyValidator()).humanized_name,
                         "boolean or dummy")

    def test_error_message(self):
        self._testValidation({"+foo": "number", "?bar":["integer"]}, errors=[
            (42,
             "Invalid value 42 (int): must be Mapping"),
            ({},
             "Invalid value {} (dict): missing required properties: ['foo']"),
            ({"foo": "3"},
             "Invalid value '3' (str): must be number (at foo)"),
            ({"foo": 3, "bar":None},
             "Invalid value None (NoneType): must be Sequence (at bar)"),
            ({"foo": 3, "bar":[1, "2", 3]},
             "Invalid value '2' (str): must be integer (at bar[1])"),
        ])

    def test_error_message_custom_repr_value(self):
        self._testValidation({"+foo": "number", "?bar":["integer"]},
                             error_value_repr=json.dumps,
                             errors=[
            (42,
             "Invalid value 42 (int): must be Mapping"),
            ({},
             "Invalid value {} (dict): missing required properties: ['foo']"),
            ({"foo": "3"},
             'Invalid value "3" (str): must be number (at foo)'),
            ({"foo": [3]},
             'Invalid value [3] (list): must be number (at foo)'),
            ({"foo": 3, "bar":None},
             "Invalid value null (NoneType): must be Sequence (at bar)"),
            ({"foo": 3, "bar": False},
             "Invalid value false (bool): must be Sequence (at bar)"),
            ({"foo": 3, "bar":[1, {u'a': 3}, 3]},
             'Invalid value {"a": 3} (dict): must be integer (at bar[1])'),
        ])

    def test_error_message_json_type_names(self):
        V.set_name_for_types("null", type(None))
        V.set_name_for_types("integer", int, long)
        V.set_name_for_types("number", float)
        V.set_name_for_types("string", str, unicode)
        V.set_name_for_types("array", list, collections.Sequence)
        V.set_name_for_types("object", dict, collections.Mapping)

        self._testValidation({"+foo": "number",
                              "?bar":["integer"],
                              "?baz": V.AnyOf("number", ["number"]),
                              "?opt": "?string",
                              }, errors=[
            (42,
             "Invalid value 42 (integer): must be object"),
            ({},
             "Invalid value {} (object): missing required properties: ['foo']"),
            ({"foo": "3"},
             "Invalid value '3' (string): must be number (at foo)"),
            ({"foo": None},
             "Invalid value None (null): must be number (at foo)"),
            ({"foo": 3, "bar":None},
             "Invalid value None (null): must be array (at bar)"),
            ({"foo": 3, "bar":[1, "2", 3]},
             "Invalid value '2' (string): must be integer (at bar[1])"),
            ({"foo": 3, "baz":"23"},
             "Invalid value '23' (string): must be number or must be array (at baz)"),
            ({"foo": 3, "opt":12},
             "Invalid value 12 (integer): must be string (at opt)"),
            ])

    def _testValidation(self, obj, invalid=(), valid=(), adapted=(), errors=(),
                        error_value_repr=repr):
        validator = self.parse(obj)
        for value in invalid:
            self.assertFalse(validator.is_valid(value))
            self.assertRaises(V.ValidationError, validator.validate, value, adapt=False)
        for value in valid:
            validator.validate(value)
            self.assertTrue(validator.is_valid(value))
            self.assertEqual(validator.validate(value), value)
        for from_value, to_value in adapted:
            validator.validate(from_value, adapt=False)
            self.assertTrue(validator.is_valid(from_value))
            self.assertEqual(validator.validate(from_value), to_value)
        for value, error in errors:
            try:
                validator.validate(value)
            except V.ValidationError as ex:
                error_repr = ex.to_string(error_value_repr)
                self.assertEqual(error_repr, error, "Actual error: %r" % error_repr)


class TestValidatorModuleParse(TestValidator):

    parse = staticmethod(V.Validator.parse)


class OptionalPropertiesTestValidator(TestValidator):

    def setUp(self):
        super(OptionalPropertiesTestValidator, self).setUp()
        V.Object.REQUIRED_PROPERTIES = False
        self.complex_validator = self.parse({
            "+n": "+number",
            "i": V.Nullable("integer", 0),
            "b": bool,
            "e": V.Enum(["r", "g", "b"]),
            "d": V.AnyOf("date", "datetime"),
            "s": V.String(min_length=1, max_length=8),
            "p": V.Nullable(re.compile(r"\d{1,4}$")),
            "l": [{"+s2": "string"}],
            "t": (unicode, "number"),
            "h": V.Mapping(int, ["string"]),
            "o": V.NonNullable({"+i2": "integer"}),
        })

    def test_required_properties_global(self):
        self._testValidation({"+foo": "number", "bar": "boolean", "+baz":"string"},
                             valid=[{"foo":-23., "baz":"yo"}],
                             invalid=[{},
                                      {"bar":True},
                                      {"baz":"yo"},
                                      {"foo":3},
                                      {"bar":False, "baz":"yo"},
                                      {"bar":True, "foo":3.1}])
