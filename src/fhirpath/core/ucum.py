# _*_ coding: utf-8 _*_
"""Built-in subset of UCUM (https://ucum.org/ucum) for FHIRPath Quantity support.

Supports unit expressions built from the atoms below with SI prefixes on metric
atoms, integer exponents, ``.`` (multiplication), ``/`` (division), parentheses,
annotations (``{rbc}``) and the unity ``1``. Special (non-ratio) units ``Cel`` and
``[degF]`` convert to/from Kelvin but cannot take part in unit algebra.

All arithmetic uses :class:`decimal.Decimal` so no binary rounding is introduced.
"""

import re
from decimal import Decimal, localcontext
from functools import lru_cache
from typing import Dict, Optional, Tuple

__author__ = "Md Nazrul Islam <email2nazrul@gmail.com>"

D = Decimal
Dims = Tuple[Tuple[str, int], ...]

PREFIXES: Dict[str, Decimal] = {
    "Y": D("1e24"),
    "Z": D("1e21"),
    "E": D("1e18"),
    "P": D("1e15"),
    "T": D("1e12"),
    "G": D("1e9"),
    "M": D("1e6"),
    "k": D("1e3"),
    "h": D("1e2"),
    "da": D("1e1"),
    "d": D("1e-1"),
    "c": D("1e-2"),
    "m": D("1e-3"),
    "u": D("1e-6"),
    "n": D("1e-9"),
    "p": D("1e-12"),
    "f": D("1e-15"),
    "a": D("1e-18"),
    "z": D("1e-21"),
    "y": D("1e-24"),
    "Ki": D(1024),
    "Mi": D(1024**2),
    "Gi": D(1024**3),
    "Ti": D(1024**4),
}

# atom -> (metric?, definition expression or base dimension, factor)
# A definition of None means a base unit whose dimension is the atom itself.
_ATOMS: Dict[str, Tuple[bool, Optional[str], Decimal]] = {
    # base units
    "m": (True, None, D(1)),
    "s": (True, None, D(1)),
    "g": (True, None, D(1)),
    "rad": (True, None, D(1)),
    "K": (True, None, D(1)),
    "C": (True, None, D(1)),
    "cd": (True, None, D(1)),
    # dimensionless
    "10*": (False, "1", D(10)),
    "10^": (False, "1", D(10)),
    "[pi]": (False, "1", D("3.1415926535897932384626433832795028841971693993751")),
    "%": (False, "1", D("0.01")),
    "[ppth]": (False, "1", D("1e-3")),
    "[ppm]": (False, "1", D("1e-6")),
    "[ppb]": (False, "1", D("1e-9")),
    "[pptr]": (False, "1", D("1e-12")),
    "mol": (True, "1", D("6.02214076e23")),
    "sr": (True, "rad2", D(1)),
    # SI derived
    "Hz": (True, "s-1", D(1)),
    "N": (True, "kg.m/s2", D(1)),
    "Pa": (True, "N/m2", D(1)),
    "J": (True, "N.m", D(1)),
    "W": (True, "J/s", D(1)),
    "A": (True, "C/s", D(1)),
    "V": (True, "J/C", D(1)),
    "F": (True, "C/V", D(1)),
    "Ohm": (True, "V/A", D(1)),
    "S": (True, "Ohm-1", D(1)),
    "Wb": (True, "V.s", D(1)),
    "T": (True, "Wb/m2", D(1)),
    "H": (True, "Wb/A", D(1)),
    "lm": (True, "cd.sr", D(1)),
    "lx": (True, "lm/m2", D(1)),
    "Bq": (True, "s-1", D(1)),
    "Gy": (True, "J/kg", D(1)),
    "Sv": (True, "J/kg", D(1)),
    "kat": (True, "mol/s", D(1)),
    "U": (True, "umol/min", D(1)),
    "eq": (True, "mol", D(1)),
    "osm": (True, "mol", D(1)),
    # time
    "min": (False, "s", D(60)),
    "h": (False, "min", D(60)),
    "d": (False, "h", D(24)),
    "wk": (False, "d", D(7)),
    "a_t": (False, "d", D("365.24219")),
    "a_j": (False, "d", D("365.25")),
    "a_g": (False, "d", D("365.2425")),
    "a": (False, "a_j", D(1)),
    "mo_s": (False, "d", D("29.53059")),
    "mo_j": (False, "a_j/12", D(1)),
    "mo_g": (False, "a_g/12", D(1)),
    "mo": (False, "mo_j", D(1)),
    # volume / area / length / mass (metric)
    "L": (True, "dm3", D(1)),
    "l": (True, "dm3", D(1)),
    "ar": (True, "m2", D(100)),
    "t": (True, "kg", D(1000)),
    "u": (True, "g", D("1.66053906660e-24")),
    "Ao": (False, "nm", D("0.1")),
    "bar": (True, "Pa", D(100000)),
    "atm": (False, "Pa", D(101325)),
    "m[Hg]": (True, "kPa", D("133.3220")),
    "m[H2O]": (True, "kPa", D("9.80665")),
    "eV": (True, "J", D("1.602176634e-19")),
    "cal": (True, "J", D("4.184")),
    "[Cal]": (False, "kcal", D(1)),
    "deg": (
        False,
        "rad",
        D("3.1415926535897932384626433832795028841971693993751") / D(180),
    ),
    "gon": (False, "deg", D("0.9")),
    "''": (False, "deg/60", D(1)),
    "'": (False, "deg/60", D(1)),
    "g%": (True, "g/dL", D(1)),
    # international customary units
    "[in_i]": (False, "cm", D("2.54")),
    "[ft_i]": (False, "[in_i]", D(12)),
    "[yd_i]": (False, "[ft_i]", D(3)),
    "[mi_i]": (False, "[ft_i]", D(5280)),
    "[nmi_i]": (False, "m", D(1852)),
    "[sin_i]": (False, "[in_i]2", D(1)),
    "[sft_i]": (False, "[ft_i]2", D(1)),
    "[cin_i]": (False, "[in_i]3", D(1)),
    "[cft_i]": (False, "[ft_i]3", D(1)),
    "[mil_i]": (False, "[in_i]", D("1e-3")),
    "[hd_i]": (False, "[in_i]", D(4)),
    "[lb_av]": (False, "g", D("453.59237")),
    "[oz_av]": (False, "[lb_av]", D(1) / D(16)),
    "[dr_av]": (False, "[oz_av]", D(1) / D(16)),
    "[gr]": (False, "mg", D("64.79891")),
    "[stone_av]": (False, "[lb_av]", D(14)),
    "[ston_av]": (False, "[lb_av]", D(2000)),
    "[lton_av]": (False, "[lb_av]", D(2240)),
    "[oz_tr]": (False, "[gr]", D(480)),
    "[lb_tr]": (False, "[oz_tr]", D(12)),
    # US volumes
    "[gal_us]": (False, "[in_i]3", D(231)),
    "[qt_us]": (False, "[gal_us]/4", D(1)),
    "[pt_us]": (False, "[qt_us]/2", D(1)),
    "[cup_us]": (False, "[pt_us]/2", D(1)),
    "[foz_us]": (False, "[gil_us]/4", D(1)),
    "[gil_us]": (False, "[pt_us]/4", D(1)),
    "[tbs_us]": (False, "[foz_us]/2", D(1)),
    "[tsp_us]": (False, "[tbs_us]/3", D(1)),
    "[foz_m]": (False, "mL", D(30)),
    "[cup_m]": (False, "mL", D(240)),
    "[tsp_m]": (False, "mL", D(5)),
    "[tbs_m]": (False, "mL", D(15)),
    # British
    "[gal_br]": (False, "L", D("4.54609")),
    "[pt_br]": (False, "[gal_br]/8", D(1)),
    # clinical
    "[drp]": (False, "mL/20", D(1)),
    "[mesh_i]": (False, "/[in_i]", D(1)),
    "[CFU]": (True, "[CFU]", D(1)),
    "[iU]": (True, "[IU]", D(1)),
    "[IU]": (True, "[IU]", D(1)),
    "[arb'U]": (True, "[arb'U]", D(1)),
    "[USP'U]": (True, "[USP'U]", D(1)),
    "[pH]": (False, "[pH]", D(1)),
    "[HPF]": (False, "1", D(1)),
    "[LPF]": (False, "1", D(100)),
    "[degRe]": (False, "K", D("1.25")),
    "bit": (True, "1", D(1)),
    "By": (True, "bit", D(8)),
    "Bd": (True, "/s", D(1)),
}

#: units that are not proportional (offset scales); value -> Kelvin
SPECIAL_UNITS = {
    "Cel": (lambda v: v + D("273.15"), lambda k: k - D("273.15")),
    "[degF]": (
        lambda v: (v + D("459.67")) * D(5) / D(9),
        lambda k: k * D(9) / D(5) - D("459.67"),
    ),
}

#: Arbitrary units: only comparable with themselves
_ARBITRARY = {"[CFU]", "[iU]", "[IU]", "[arb'U]", "[USP'U]", "[pH]"}

_TOKEN = re.compile(r"\{[^}]*\}|\[[^\]]*\]|[A-Za-z%'_\[\]0-9*^]+|[./()]")


class UcumError(ValueError):
    """Unit string is not valid / not supported."""


class Unit:
    """A parsed ratio unit: ``value_in_base = value * factor``; ``dims`` sorted."""

    __slots__ = ("factor", "dims", "terms")

    def __init__(self, factor: Decimal, dims: Dict[str, int], terms: Dict[str, int]):
        self.factor = factor
        self.dims: Dims = tuple(sorted((k, v) for k, v in dims.items() if v))
        # symbolic terms (prefixed atom -> exponent) for unit algebra rendering
        self.terms = {k: v for k, v in terms.items() if v}

    def __repr__(self):
        return "Unit(%s, %s)" % (self.factor, self.dims)


def _combine(target: Dict[str, int], source, power: int):
    for key, value in (source.items() if isinstance(source, dict) else source):
        target[key] = target.get(key, 0) + value * power


def _split_exponent(token: str) -> Tuple[str, int]:
    match = re.match(r"^(.*[^0-9+-])([+-]?\d+)$", token)
    if match and match.group(1) not in ("10*", "10^"):
        return match.group(1), int(match.group(2))
    return token, 1


@lru_cache(maxsize=4096)
def _atom(symbol: str) -> Tuple[Decimal, Dims]:
    """Resolve a (possibly prefixed) atom symbol."""
    candidates = []
    if symbol in _ATOMS:
        candidates.append((D(1), symbol))
    for prefix, factor in PREFIXES.items():
        if symbol.startswith(prefix) and symbol[len(prefix) :] in _ATOMS:
            atom = symbol[len(prefix) :]
            if _ATOMS[atom][0]:
                candidates.append((factor, atom))
    if not candidates:
        raise UcumError("unknown unit atom %r" % symbol)
    prefix_factor, atom = candidates[0]
    _, definition, factor = _ATOMS[atom]
    if definition is None or definition == atom:
        dims = ((atom if definition is None else definition, 1),)
        return prefix_factor * factor, dims
    unit = parse(definition)
    return prefix_factor * factor * unit.factor, unit.dims


def _parse_component(
    tokens, pos
) -> Tuple[Decimal, Dict[str, int], Dict[str, int], int]:
    token = tokens[pos]
    if token == "(":
        factor, dims, terms, pos = _parse_term(tokens, pos + 1)
        if pos >= len(tokens) or tokens[pos] != ")":
            raise UcumError("unbalanced parenthesis")
        pos += 1
        # optional exponent directly after ')'
        if pos < len(tokens) and re.match(r"^[+-]?\d+$", tokens[pos]):
            power = int(tokens[pos])
            pos += 1
            factor = factor**power
            dims = {k: v * power for k, v in dims.items()}
            terms = {k: v * power for k, v in terms.items()}
        return factor, dims, terms, pos
    if token.startswith("{"):
        return D(1), {}, {}, pos + 1
    # strip trailing annotation glued to the symbol (e.g. "mg{total}")
    symbol = re.sub(r"\{[^}]*\}$", "", token)
    if re.match(r"^\d+$", symbol):
        return D(symbol), {}, {}, pos + 1
    if symbol.startswith("10*") or symbol.startswith("10^"):
        exponent = int(symbol[3:] or 1)
        return D(10) ** exponent, {}, {}, pos + 1
    symbol, power = _split_exponent(symbol)
    factor, dims = _atom(symbol)
    return factor**power, {k: v * power for k, v in dims}, {symbol: power}, pos + 1


def _parse_term(tokens, pos) -> Tuple[Decimal, Dict[str, int], Dict[str, int], int]:
    factor, dims, terms = D(1), {}, {}
    if pos < len(tokens) and tokens[pos] == "/":
        operator = "/"
        pos += 1
    else:
        operator = "."
    while pos < len(tokens) and tokens[pos] != ")":
        f, d, t, pos = _parse_component(tokens, pos)
        power = 1 if operator == "." else -1
        factor = factor * f if power == 1 else factor / f
        _combine(dims, d, power)
        _combine(terms, t, power)
        if pos < len(tokens) and tokens[pos] in (".", "/"):
            operator = tokens[pos]
            pos += 1
        else:
            break
    return factor, dims, terms, pos


def _tokenize(unit: str):
    tokens = []
    pos = 0
    while pos < len(unit):
        char = unit[pos]
        if char in "./()":
            tokens.append(char)
            pos += 1
            continue
        # read a symbol up to an operator, keeping bracketed/braced parts whole
        start = pos
        depth_sq = depth_br = 0
        while pos < len(unit):
            c = unit[pos]
            if c == "[":
                depth_sq += 1
            elif c == "]":
                depth_sq -= 1
            elif c == "{":
                depth_br += 1
            elif c == "}":
                depth_br -= 1
            elif c in "./()" and depth_sq == 0 and depth_br == 0:
                break
            pos += 1
        tokens.append(unit[start:pos])
    return tokens


@lru_cache(maxsize=4096)
def parse(unit: str) -> Unit:
    """Parse a UCUM ratio unit expression. Raises :class:`UcumError`."""
    if unit in SPECIAL_UNITS:
        raise UcumError("special unit %r has no ratio form" % unit)
    if unit == "1" or unit == "":
        return Unit(D(1), {}, {})
    if " " in unit:
        raise UcumError("whitespace in unit %r" % unit)
    tokens = _tokenize(unit)
    with localcontext() as ctx:
        ctx.prec = 50
        factor, dims, terms, pos = _parse_term(tokens, 0)
    if pos != len(tokens):
        raise UcumError("cannot parse unit %r" % unit)
    return Unit(factor, dims, terms)


def is_valid(unit: str) -> bool:
    if unit in SPECIAL_UNITS:
        return True
    try:
        parse(unit)
    except (UcumError, ArithmeticError, ValueError):
        return False
    return True


def is_special(unit: str) -> bool:
    return unit in SPECIAL_UNITS


def _dims_of(unit: str) -> Optional[Dims]:
    if unit in SPECIAL_UNITS:
        return (("K", 1),)
    try:
        return parse(unit).dims
    except (UcumError, ArithmeticError, ValueError):
        return None


def commensurable(unit_a: str, unit_b: str) -> bool:
    dims_a, dims_b = _dims_of(unit_a), _dims_of(unit_b)
    return dims_a is not None and dims_a == dims_b


def factor(unit: str) -> Decimal:
    """Factor to base units (ratio units only)."""
    return parse(unit).factor


def convert(value: Decimal, from_unit: str, to_unit: str) -> Optional[Decimal]:
    """Convert ``value`` between commensurable units, ``None`` when impossible."""
    if from_unit == to_unit:
        return value
    if not commensurable(from_unit, to_unit):
        return None
    with localcontext() as ctx:
        ctx.prec = 34
        if from_unit in SPECIAL_UNITS or to_unit in SPECIAL_UNITS:
            if from_unit in SPECIAL_UNITS:
                kelvin = SPECIAL_UNITS[from_unit][0](value)
            else:
                kelvin = value * parse(from_unit).factor
            if to_unit in SPECIAL_UNITS:
                result = SPECIAL_UNITS[to_unit][1](kelvin)
            else:
                result = kelvin / parse(to_unit).factor
        else:
            result = value * parse(from_unit).factor / parse(to_unit).factor
    return clean(result)


def clean(value: Decimal) -> Decimal:
    """Drop conversion noise such as 0.04000000000000000000001."""
    if value == value.to_integral_value():
        return value.quantize(D(1))
    normalized = value.normalize()
    exponent = normalized.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -20:
        rounded = round(value, 20).normalize()
        return rounded
    return normalized


def multiply_units(unit_a: str, unit_b: str, power_b: int = 1) -> Optional[str]:
    """Symbolic product (``power_b=1``) or quotient (``power_b=-1``) of two units."""
    try:
        terms_a, terms_b = parse(unit_a).terms, parse(unit_b).terms
    except (UcumError, ArithmeticError, ValueError):
        return None
    terms = dict(terms_a)
    _combine(terms, terms_b, power_b)
    return render(terms)


def render(terms: Dict[str, int]) -> str:
    positive = [(k, v) for k, v in terms.items() if v > 0]
    negative = [(k, -v) for k, v in terms.items() if v < 0]

    def fmt(items):
        return ".".join(k + (str(v) if v != 1 else "") for k, v in items)

    if not positive and not negative:
        return "1"
    text = fmt(positive)
    if negative:
        text += (
            "/" + fmt(negative) if len(negative) == 1 else "/(" + fmt(negative) + ")"
        )
    return text


__all__ = [
    "UcumError",
    "parse",
    "is_valid",
    "is_special",
    "commensurable",
    "convert",
    "factor",
    "multiply_units",
]
