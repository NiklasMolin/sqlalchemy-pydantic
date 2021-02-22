from returns.converters import flatten
from returns.functions import tap
from returns.pipeline import flow, is_successful, pipe
from returns.pointfree import bind, map_
from returns.result import Failure, Result, Success, safe


@safe
def a(b: int):
    return b

def b(b: int):
    return Success(b)

@safe
def c(b: int):
    return b


def d(b:int):
    return Failure(b)

@safe
def e(b: int):
    raise Exception("erre")
    return b*b

def test_a():
    assert a(10) == Success(10)
    assert flow(10, a, bind(b),bind(c)) == Success(10)
    assert flow(10, a, bind(d),bind(e)) == Failure(10)
