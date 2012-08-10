from datetime import date, datetime
from decimal import Decimal
from functools import partial
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

    @classmethod
    def setUpClass(cls):
        V.Object.REQUIRED_PROPERTIES = True
        cls.complex_validator = V.Validator.parse({
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
            self.assertFalse(V.Validator.parse(obj).is_valid(None))

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

    def test_required_properties(self):
        self._testValidation({"foo": "number", "?bar": "boolean", "baz":"string"},
                             valid=[{"foo":-23., "baz":"yo"}],
                             invalid=[{},
                                      {"bar":True},
                                      {"baz":"yo"},
                                      {"foo":3},
                                      {"bar":False, "baz":"yo"},
                                      {"bar":True, "foo":3.1}])

    def test_adapt_missing_property(self):
        self._testValidation({"foo": "number", "?bar": V.Nullable("boolean", False)},
                             adapted=[({"foo":-12}, {"foo":-12, "bar":False})])

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
            self.assertRaises(V.SchemaError, V.Validator.parse, obj)

    def test_not_implemented_validation(self):
        class MyValidator(V.Validator):
            pass

        validator = MyValidator()
        self.assertRaises(NotImplementedError, validator.validate, 1)

    def test_register(self):
        V.Validator.register("to_int", V.AdaptTo(int, traps=(ValueError, TypeError)))
        self._testValidation("to_int",
                             invalid=["12b", "1.2"],
                             adapted=[(12, 12), ("12", 12), (1.2, 1)])

        self.assertRaises(TypeError, V.Validator.register, "to_int", int)

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

    def test_error_message(self):
        self._testValidation({"+foo": "number", "?bar":["integer"]}, errors=[
            (42,
             "Invalid value 42: Must be Mapping"),
            ({},
             "Invalid value {}: Missing required properties: ['foo']"),
            ({"foo": "3"},
             "Invalid value '3': Must be Number (at foo)"),
            ({"foo": 3, "bar":None},
             "Invalid value None: Must be Sequence (at bar)"),
            ({"foo": 3, "bar":[1, "2", 3]},
             "Invalid value '2': Must be Integral (at bar[1])"),
        ])

    def _testValidation(self, obj, invalid=(), valid=(), adapted=(), errors=()):
        validator = V.Validator.parse(obj)
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
                self.assertEqual(str(ex), error, "Actual error: %r" % str(ex))


class OptionalPropertiesTestValidator(TestValidator):

    @classmethod
    def setUpClass(cls):
        super(OptionalPropertiesTestValidator, cls).setUpClass()
        V.Object.REQUIRED_PROPERTIES = False
        cls.complex_validator = V.Validator.parse({
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

    def test_required_properties(self):
        self._testValidation({"+foo": "number", "bar": "boolean", "+baz":"string"},
                             valid=[{"foo":-23., "baz":"yo"}],
                             invalid=[{},
                                      {"bar":True},
                                      {"baz":"yo"},
                                      {"foo":3},
                                      {"bar":False, "baz":"yo"},
                                      {"bar":True, "foo":3.1}])
