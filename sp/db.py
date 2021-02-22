import os
import sys
from datetime import datetime
from  enum import  Enum
from functools import partial
from typing import List, Tuple, Optional

from returns.converters import flatten
from returns.curry import partial
from returns.functions import tap
#from returns.iterables import Fold
from returns.pipeline import flow, pipe
from returns.pointfree import bind, map_
from returns.result import Failure, Result, Success, safe
from sqlalchemy import Column, create_engine, select, table
from sqlalchemy.orm import joinedload_all, raiseload, sessionmaker, joinedload
from sqlalchemy.orm.query import Query
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.inspection import inspect
from sp.config import CONN_STR, CONN_ARGS

SessionLocal = None


def set_session(conn_str: str):
    global SessionLocal
    if not SessionLocal:
        engine = create_engine(conn_str, echo=True, **CONN_ARGS)
        SessionLocal = sessionmaker(bind=engine)


@safe
def get_db(conn_str: str = CONN_STR):
    try:
        set_session(conn_str)
        db = SessionLocal()
        yield db
    finally:
        if db:
            db.close()


@safe
def add_db(model, data):
    import json

    print("Add data" + json.dumps(data, default=str))
    values = [ model.from_dict(item) for item  in (data if isinstance(data, list) else [data])]
    # print("got db" + json.dumps(value.to_dict()))
    def _merge(_db):
        for value in  values:
            _db.merge(value)
        _db.commit()

    return flow(get_db().bind(next), _merge)


@safe
def delete_db(model, id):
    def _delete(db):
        db.query(model).filter_by(id=id).delete()
        db.commit()

    return flow(get_db().bind(next), _delete)


@safe
def joined_query(db, model, filter_clause):
    """ performed a joined query to fetch first level relationships"""
    mapper = inspect(model)
    query = db.query(model).options(
        *[joinedload(k) for k in mapper.relationships.keys()], raiseload("*")
    )
    if filter_clause:
        return query.filter_by(**filter_clause)
    return query


@safe
def update_db(model, id, data, synchronize_session):
    """Updates a record belonging to the specific model
    syncronize false, to avoid selecting the row into state
    """
    db = next(get_db())
    db.query(model).filter_by(id=id).update(data, synchronize_session=synchronize_session)
    db.commit()


def select_db(model, where=None) -> Result[Query, Exception]:
    jq = partial(joined_query, model=model, filter_clause=where)
    return flow(get_db(), map_(next), bind(jq))


def select_first_db(model, where=None):
    _first = lambda q: q.first()
    res = select_db(model, where).map(_first)
    return res


def select_all_db(model, where=None):
    _all = lambda q: q.all()
    res = select_db(model, where).map(_all)
    return res


@safe
def select_options(model: DeclarativeMeta,) -> List[Tuple[str, List[Tuple[str, str]]]]:
    options_results: List[List[Tuple[str, str]]] = []
    options_names: List[str] = []
    for fk in [list(col.foreign_keys) for col in inspect(model).columns if col.foreign_keys]:
        if len(fk) > 1:
            raise Exception("Unsupported option, column in only allowed one fk reference")
        options_names.append(fk[0].parent.name)
        options_results.append(flatten(select_option(model._decl_class_registry[fk[0].column.table.name])).unwrap())
    _zip = lambda x: list(zip(options_names, x))
    #return Fold.collect(options_results, Success(())).map(_zip).unwrap()
    return zip(options_names, options_results)

@safe
def select_option(model: DeclarativeMeta):
    _formatter = lambda res: [
        {"key": getattr(k, "key"), "value": getattr(k, "label")} for k in res
    ]
    return select_all_db(model).map(_formatter)

@safe
def add_option(model: DeclarativeMeta, option: Enum):
    data = [{ "key":c.value, "label": c.name } for b,c  in option.__members__.items()]
    return add_db(model, data)