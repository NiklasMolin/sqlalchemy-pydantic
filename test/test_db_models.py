import sys
from datetime import datetime
from enum import Enum
from functools import reduce, singledispatch
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

# from ..db import select_all_db, add_db , get_db
from unittest.mock import MagicMock, patch

import pytest

# import psycopg2
import sqlalchemy
from pydantic import BaseModel, Field
from pydantic.fields import ModelField

# from psycopg2 import Error
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    create_engine,
    event,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import as_declarative, declarative_base
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import (
    RelationshipProperty,
    backref,
    joinedload,
    raiseload,
    relationship,
    sessionmaker,
)
from sqlalchemy.util import symbol
from sqlalchemy_utils import force_instant_defaults

from sp.db_models import (
    ListField,
    MappedColumnTypes,
    RelationshipType,
    SubTable,
    TableAttribute,
    TableColumn,
    TableDef,
    collect_table,
    collect_tables,
    create_models,
    parse_field,
    parse_fields,
    parse_table,
    parse_table_attribute,
    parse_table_attributes,
    dbint
)

force_instant_defaults()
# Base = declarative_base(metadata=MetaData(schema="validation"))
BASE_COLS = ["created_at", "created_by", "updated_at", "updated_by"]

## Mapper sqlalchemy.orm.mapper.Mapper
## relationships sqlalchemy.util._collections.ImmutableProperties


@as_declarative()  # metadata=MetaData(schema="validation"))
class Base(object):
    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class Test(Base):
    __tablename__ = "tests"
    b = Column(String, primary_key=True)

    def __str__(self):
        return f"{self.b}"

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class TestSubClass(BaseModel):
    a: List[str]
    b: str


class Choice(Enum):
    a = "test"


class TestClass(BaseModel):
    id: dbint = Field(primary_key=True)
    a: int
    b: List[int]
    c: TestSubClass
    d: List[TestSubClass]
    e: str = Field(values=Choice)
    f: str = Field(values=Choice)

test_parse_field_results = (
    TableColumn(name="id", type_=MappedColumnTypes["dbint"].value, unique=False, kwargs={'primary_key': True}), 
    TableColumn(name="a", type_=MappedColumnTypes["int"].value, unique=False),
    SubTable(
        name="b",
        table=TableDef(
            name="b",
            attributes=[TableColumn(name="b", type_=MappedColumnTypes["int"].value, unique=False)],
        ),
        relationship_type=RelationshipType.one_to_many,
    ),
    SubTable(
        name="c",
        table=TableDef(
            name="c",
            attributes=[
                SubTable(
                    name="a",
                    table=TableDef(
                        name="a",
                        attributes=[
                            TableColumn(
                                name="a", type_=MappedColumnTypes["str"].value, unique=False,
                            )
                        ],
                    ),
                    relationship_type=RelationshipType.one_to_many,
                ),
                TableColumn(name="b", type_=MappedColumnTypes["str"].value, unique=False),
            ],
        ),
        relationship_type=RelationshipType.one_to_one,
    ),
    SubTable(
        name="d",
        table=TableDef(
            name="d",
            attributes=[
                SubTable(
                    name="a",
                    table=TableDef(
                        name="a",
                        attributes=[
                            TableColumn(
                                name="a", type_=MappedColumnTypes["str"].value, unique=False,
                            )
                        ],
                    ),
                    relationship_type=RelationshipType.one_to_many,
                ),
                TableColumn(name="b", type_=MappedColumnTypes["str"].value, unique=False),
            ],
        ),
        relationship_type=RelationshipType.one_to_many,
    ),
)


@pytest.mark.parametrize(
    "field, res", list(zip(TestClass.__fields__.items(), test_parse_field_results)),
)
def test_parse_field(field, res):
    assert parse_field(*field) == res


class TestSimple(BaseModel):
    a: int


def _test_table_def(name, attributes):
    return (name, attributes)


def test_parse_table():
    assert parse_table(TestSimple) == TableDef(
        name="TestSimple",
        attributes=[TableColumn(name="a", type_=MappedColumnTypes["int"].value, unique=False)],
    )
    assert parse_table(ListField(name="test", type_=MappedColumnTypes["int"].value)) == TableDef(
        name="test", attributes=[TableColumn(name="test", type_=MappedColumnTypes["int"].value)],
    )


def test_collect_table():
    assert list(
        collect_table(
            TableDef(name="niklas", attributes=[]),
            additional_options={"__table_args__": {"extend_existing": True}},
        ).__dict__.keys()
    ) == [
        "__table_args__",
        "__tablename__",
        "id",
        "__module__",
        "__doc__",
        "__table__",
        "_sa_class_manager",
        "__init__",
        "__mapper__",
    ]


def test_collect_tables():
    col = collect_tables(
        TableDef(
            name="niklas2",
            attributes=[
                SubTable(
                    name="SubTest1",
                    table=TableDef(name="subTest1", attributes=[]),
                    relationship_type="one_to_one",
                )
            ],
        ),
        additional_options={"__table_args__": {"extend_existing": True}},
    )
    assert list(col[0].__dict__.keys()) == [
        "__table_args__",
        "__tablename__",
        "id",
        "SubTest1",
        "__module__",
        "__doc__",
        "__table__",
        "_sa_class_manager",
        "__init__",
        "__mapper__",
    ]
    assert list(col[1].__dict__.keys()) == [
        "__table_args__",
        "__tablename__",
        "id",
        "niklas2_id",
        "niklas2",
        "__module__",
        "__doc__",
        "__table__",
        "_sa_class_manager",
        "__init__",
        "__mapper__",
    ]


def test_create_models():
    models = create_models(
        (TestClass,), additional_options={"__table_args__": {"extend_existing": True}},
    )
    assert tuple(c for c in models.models.keys()) == (
        "TestClass",
        "Choice",
        "TestClass_b",
        "TestClass_c",
        "TestClass_c_a",
        "TestClass_d",
        "TestClass_d_a",
    )


class TestError(BaseModel):
    a: dict
    b: str


def test_create_models_error():
    with pytest.raises(TypeError):
        db_model = create_models(TestError)
