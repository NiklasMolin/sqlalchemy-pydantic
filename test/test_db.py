import os
import tempfile
from enum import Enum
import sqlite3

os.environ["PYTEST"] = "YES"
import pytest
from mock import patch
from sqlalchemy import create_engine
from returns.pipeline import is_successful
from sp.db_models import create_models
from sp.db import get_db, add_db, select_first_db, select_all_db, delete_db, add_option, select_options
from pydantic import BaseModel, Field
from sp.config import CONN_STR


class Test(BaseModel):
    a: int
    b: str


class Fruits(Enum):
    apple = 1
    orange = 2


class TestOption(BaseModel):
    fruit: int = Field(values=Fruits)


class SubTest(BaseModel):
    a: int
    b: str


class TestParent(BaseModel):
    flag: bool
    sub: SubTest


@pytest.fixture(scope="session")
def db_model():
    engine = create_engine(f"sqlite:///validation.db")
    db_model = create_models((TestParent, Test, TestOption))
    db_model.base.metadata.create_all(engine)
    return db_model


def test_table(db_model):
    _sql = "SELECT name FROM sqlite_master WHERE type ='table' AND  name NOT LIKE 'sqlite_%';"
    tables = sqlite3.connect(CONN_STR.replace("sqlite:///", "")).execute(_sql).fetchall()
    assert tables == [('TestParent',), ('Test',), ('Fruits',), ('TestParent_sub',), ('TestOption',)]

def test_add_option(db_model):
    res = add_option(db_model[Fruits], Fruits) 
    assert is_successful(res)

def test_select_options(db_model):
    res = select_options(db_model[TestOption]) 
    assert list(res.unwrap()) == [('fruit', [{'key': 1, 'value': 'apple'}, {'key': 2, 'value': 'orange'}])]

# BASE TEST
@pytest.mark.parametrize(
    "model, first, second",
    [
        (Test, {"a": 1, "b": "test"}, {"id": 1, "a": 2, "b": "test2"}),
        (TestOption, {"fruit": 1}, {"id": 1, "fruit": 2}),
    ],
)
def test_basic(db_model, model, first, second):
    res = add_db(db_model[model], first)
    assert is_successful(res)
    res = select_first_db(db_model[model])
    assert set(res.unwrap().to_dict().items()) >= set(first.items())
    res = add_db(db_model[model], second)
    assert is_successful(res)
    res = select_all_db(db_model[model])
    assert set(list(map(lambda x: x.to_dict(), res.unwrap()))[0].items()) >= set(second.items())
    res = delete_db(db_model[model], 1)
    assert is_successful(res)

"""
    res = rv.get_json()
    assert job_name == res.get("name")
    add2 = client.post(
        "/job",
        json={
            "id": res.get("id"),
            "name": job_name,
            "extra_jars": ["test2, test3"],
        },
    )
    assert (
        select_first_db(JobExtraJars, {"job_id": res.get("id")})
        .unwrap().to_dict()
        .get("name")
        == "test2, test3"
    )
    delete_res = client.get(f"/delete/job/{rv.get_json().get('id')}")
    assert delete_res.get_json() == {"status":"SUCCESS"}
    ##This should fail for postgres
    assert (
        select_first_db(JobExtraJars, {"job_id": rv.get_json().get("id")})
        .unwrap().to_dict()
        .get("name")
        == "test2, test3"
    )"""


# def test_get_job(client, job_name):
#    """Start with a blank database."""
#    rv = client.get(f"/job/{job_name}")
#    res = rv.get_json()
#    assert job_name in rv.get_json().get("name")
#    assert "test2" in rv.get_json().get("extra_jars")[0]
