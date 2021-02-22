""" Defining a mechanism to transform a subset of pydantic functionality to an
sql alchemy model
"""
from datetime import datetime
from enum import Enum
from functools import reduce, singledispatch
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

import sqlalchemy
from dictalchemy.utils import asdict
from pydantic import BaseModel, Field
from pydantic.fields import ModelField
from pydantic.main import ModelMetaclass
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Integer,
)
from sqlalchemy.ext.declarative import DeclarativeMeta, as_declarative
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import RelationshipProperty, relationship
from sqlalchemy.util import symbol
from sqlalchemy_utils import force_instant_defaults

force_instant_defaults()
# Base = declarative_base(metadata=MetaData(schema="validation"))
BASE_COLS = ["created_at", "created_by", "updated_at", "updated_by"]
RELATIONSHIPS_TO_FOLLOW = [symbol("ONETOMANY")]
## Mapper sqlalchemy.orm.mapper.Mapper
## relationships sqlalchemy.util._collections.ImmutableProperties
MAPPED_COLUMN_TYPES: Dict[Type, Any] = {
    str: String,
    int: BigInteger,
    type(datetime): DateTime,
    bool: Boolean,
}

class dbint(int):
    pass

MappedColumnTypes = Enum(
    "MappedColumnTypes",
    [("str", String), ("int", BigInteger),("dbint",Integer), ("datetime", DateTime), ("bool", Boolean),],
)


def get_directional_rel(
    mapper: "sqlalchemy.orm.mapper.Mapper", direction: str
) -> Iterator["sqlalchemy.util._collections.ImmutableProperties"]:
    return filter(lambda m: m.direction is not symbol(direction), mapper.relationships)


def get_attr_columns(target: sqlalchemy.util._collections.ImmutableProperties,) -> Iterator[str]:
    """[summary]

    Args:
        target (sqlalchemy.util._collections.ImmutableProperties): [description]

    Returns:
        [type]: [description]

    Yields:
        Iterator[str]: [description]
    """
    return filter(
        lambda col: not (
            target.columns[col].foreign_keys or col in BASE_COLS or target.columns[col].primary_key
        ),
        target.columns.keys(),
    )


def remote_ref_col(fks: Set[Column]) -> str:
    """Get the name of the foregin key column if there is one
    otherwise throws exeception

    Args:
        fks (Set[Column]): [description]

    Raises:
        Exception: [description]

    Returns:
        str: the name of the foreign key column
    """
    if len(fks) > 1:
        raise Exception("Not supported to have rel to more than one col")
    return list(fks)[0].name


##@as_declarative()  # metadata=MetaData(schema="validation"))
class Base_:
    @classmethod
    def from_dict(cls, values: Dict[str, Any]) -> Optional["Base_"]:
        mapper = inspect(cls)
        for rel in filter(lambda m: m.direction in RELATIONSHIPS_TO_FOLLOW, mapper.relationships,):
            if values.get(rel.key):
                pk = (
                    {
                        remote_ref_col(rel._calculated_foreign_keys): values.get(
                            mapper.primary_key[0].name
                        )
                    }
                    if isinstance(values, dict) and values.get(mapper.primary_key[0].name)
                    else {}
                )
                if rel.uselist:
                    target_cols = list(get_attr_columns(rel.target))
                    if len(target_cols) > 1:
                        values = {
                            **values,
                            rel.key: [
                                rel.entity.class_.from_dict(item)
                                for item in values.get(rel.key, [])
                            ],
                        }
                    else:  # Allow entites with 1 attr to be specified as list
                        # , in another case to give clearer errors
                        values = {
                            **values,
                            rel.key: [
                                rel.entity.class_.from_dict({**item, **pk})
                                if isinstance(item, dict)
                                else rel.entity.class_.from_dict({target_cols[0]: item})
                                for item in values.get(rel.key, [])
                            ],
                        }
                else:
                    values = {
                        **values,
                        rel.key: rel.entity.class_.from_dict({**pk, **values.get(rel.key, {})}),
                    }
        if values:
            return cls(  # type:ignore
                **values
            )
        return None

    def to_dict(self, **kwargs: Dict[str, Any]) -> Dict[str, Any]:
        mapper = inspect(self.__class__)
        excluded_many_to_one = {
            col.name
            for m in mapper.relationships
            for col in m.local_columns
            if m.direction is symbol("MANYTOONE")
        }
        exclude_id = ["id"] if kwargs.get("exclude_id") else []
        res = asdict(
            model=self,
            exclude_id=True,
            include=kwargs.get("include", None),
            follow=[m.key for m in mapper.relationships if m.direction is symbol("ONETOMANY")],
            exclude=[*BASE_COLS, *excluded_many_to_one, *exclude_id],
            method="to_dict",
        )
        if len(res) > 1:
            return res
        return list(res.values())[0]


def get_base() -> DeclarativeMeta:
    return as_declarative()(type("Base", (Base_,), {}))


class RelationshipType(Enum):
    one_to_one = "one_to_one"
    one_to_many = "one_to_many"


class TableAttribute(BaseModel):
    """A table attribute"""

    name: str


class TableDef(BaseModel):
    """A table"""

    name: str
    attributes: List[TableAttribute]


class TableColumn(TableAttribute):
    """ A table column definition
    """

    type_: type
    kwargs: dict = Field(default_factory=lambda: {})

class OptionTableColumn(TableAttribute):
    """ A table column definition
    """

    type_: type
    values: Type[Enum]


class SubTable(TableAttribute):
    """  A SubTable definition
    """

    table: TableDef
    relationship_type: RelationshipType


def modelField_is_collection(field: ModelField, type_: Tuple[type]) -> bool:
    """Verified if a ModelField is of a given collection type

    Args:
        field (ModelField): [description]
        type_ (type): [description]

    Returns:
        bool: [description]
    """
    if not hasattr(field.outer_type_, "__origin__") or not getattr(field.outer_type_, "__origin__"):
        return False
    return field.outer_type_.__origin__ in (type_)


# A = TypeVar("A", int, str) # *MAPPED_COLUMN_TYPES.keys())


class ListField(BaseModel):
    """A convience object used in parsing
    """

    name: str
    type_: MappedColumnTypes


class BaseModelField(BaseModel):
    """A convience object used in parsing
    """

    name: str
    type_: ModelMetaclass


def parse_column_field(name: str, field: ModelField) -> TableAttribute:

    if field.field_info.extra.get("values"):
        return OptionTableColumn(
            name=name,
            type_=MappedColumnTypes[field.type_.__name__].value,
            values=field.field_info.extra.get("values"),
        )
    else:
        return TableColumn(
            name=name,
            type_=MappedColumnTypes[field.type_.__name__].value,
            kwargs=field.field_info.extra
        )


def parse_field(name: str, field: ModelField) -> TableAttribute:
    """Parse a ModelField to a TableAttribute

    Args:
        name (str): [description]
        field (ModelField): [description]

    Raises:
        TypeError: [description]

    Returns:
        TableAttribute: [description]
    """
    if modelField_is_collection(field, (List,list)):
        return SubTable(
            name=name,
            table=parse_table(
                ListField(name=name, type_=MappedColumnTypes[field.type_.__name__])
                if not isinstance(field.type_, type(BaseModel))
                else BaseModelField(name=name, type_=field.type_)
            ),
            relationship_type=RelationshipType.one_to_many,
        )
    if field.type_.__name__ in MappedColumnTypes.__members__ and not field.is_complex():
        return parse_column_field(name, field)
    if issubclass(field.type_, BaseModel) and field.type_ == field.outer_type_:
        return SubTable(
            name=name,
            table=parse_table(BaseModelField(name=name, type_=field.type_)),
            relationship_type=RelationshipType.one_to_one,
        )
    raise TypeError(f"Unsupported type {field}")


def parse_fields(fields: Dict[str, ModelField]) -> List[TableAttribute]:
    """Iterative parser for a models ModelFields

    Args:
        fields (Dict[str, ModelField]): [description]

    Returns:
        List[TableAttribute]: [description]
    """
    return [parse_field(name, field) for name, field in fields.items()]


# Create a single dispatch of this
#@singledispatch
#Comment out since single dispatch on these object doesn't seem to work on 3.6
# works just fine on 3.8
def parse_table(model: Any) -> TableDef:
    """Base case for table parser,  raises type error

    Args:
        model (Any): [description]

    Raises:
        TypeError: [description]

    Returns:
        TableDef: [description]
    """
    if isinstance(model, ListField):
        return parse_list_field(model)
    if isinstance(model, ModelMetaclass):
        return parse_model(model)
    if isinstance(model, BaseModelField):
        return parse_modelfield(model)

    raise TypeError(f"the type of {type(model)} is not a valid type for table parsing")


#@parse_table.register
def parse_list_field(model: ListField) -> TableDef:
    """Table parser for a list type object

    Args:
        model (ListField): [description]

    Returns:
        TableDef: [description]
    """
    return TableDef(
        name=model.name, attributes=[TableColumn(name=model.name, type_=model.type_.value)],
    )


#@parse_table.register
def parse_model(model: ModelMetaclass) -> TableDef:
    """Table parser for a pydantic model type

    Args:
        model (type): [description]

    Returns:
        TableDef: [description]
    """
    return TableDef(name=model.__name__, attributes=parse_fields(model.__fields__))


#@parse_table.register
def parse_modelfield(model: BaseModelField) -> TableDef:
    """Table parser for a pydantic model type

    Args:
        model (type): [description]

    Returns:
        TableDef: [description]
    """
    return TableDef(name=f"{model.name}", attributes=parse_fields(model.type_.__fields__),)


def get_sub_table_name(table: str, parent: Optional[str] = None) -> str:
    """Get the sub table name

    Args:
        attribute_name (str): [description]
        name (str): [description]

    Returns:
        str: [description]
    """
    if parent:
        return f"{parent}_{table}"
    return table


def get_option_table_name(options: OptionTableColumn, parent: Optional[str] = None) -> str:
    """Get the sub table name

    Args:
        attribute_name (str): [description]
        name (str): [description]

    Returns:
        str: [description]
    """
    return options.values.__name__
    if parent:
        return f"{parent}_{options.name}_{options.values.__name__}"
    return options.name


def parse_table_attribute(
    attribute: TableAttribute, name: str
) -> Union[Column, RelationshipProperty]:
    """Parsing of a table attribute

    Args:
        attribute (TableAttribute): [description]
        name (str): [description]

    Raises:
        Exception: [description]

    Returns:
        Union[Column, RelationshipProperty]: [description]
    """
    if isinstance(attribute, TableColumn):
        return Column(attribute.type_,**attribute.kwargs)
    if isinstance(attribute, OptionTableColumn):
        return Column(
            attribute.type_,
            ForeignKey(f"{get_option_table_name(attribute, name)}.key",),
        )
    if isinstance(attribute, SubTable):
        return relationship(
            get_sub_table_name(attribute.name, name),
            uselist=attribute.relationship_type == RelationshipType.one_to_many,
            back_populates=name,
            cascade="all,  delete",
            passive_deletes=True,
        )
    raise Exception(f"Ran into unsupported TableAttribute type {attribute}")


def parse_table_attributes(
    attributes: List[TableAttribute], name: str
) -> Dict[str, Union[Column, RelationshipProperty]]:
    """Iteration for a tables lists of tableAttributes

    Args:
        attributes (List[TableAttribute]): [description]
        name (str): [description]

    Returns:
        Dict[str, Union[Column, RelationshipProperty]]: [description]
    """
    return {attr.name: parse_table_attribute(attr, name) for attr in attributes}


def parse_parent_relationship(
    parent_table: Optional[str], name: str
) -> Dict[str, Union[Column, RelationshipProperty]]:
    """Create a parent relationship for a TableDef

    Args:
        parent_table_def (Optional[TableDef]): [description]
        name (str): [description]

    Returns:
        Dict[str, Union[Column, RelationshipProperty]]: [description]
    """
    if not parent_table:
        return {}
    return {
        f"{parent_table}_id": Column(
            BigInteger, ForeignKey(f"{parent_table}.id", ondelete="CASCADE")
        ),
        f"{parent_table}": relationship(f"{parent_table}", back_populates=name),
    }


def collect_table(
    table_def: TableDef,
    parent_table: Optional[str] = None,
    additional_options: Optional[dict] = None,
    base: DeclarativeMeta = get_base(),
) -> Type[DeclarativeMeta]:
    """Create table model based on an Internal TableDef

    Args:
        table_def (TableDef): Table description
        parent_table_def (Optional[TableDef], optional): The parent table. Defaults to None.
        additional_options (dict, optional): used for testing, dditional table_args. Defaults to {}.

    Returns:
        Type[Base]: a sql alchemy models
    """
    _name = get_sub_table_name(table_def.name, parent_table)
    def_attr_def = {
        "__tablename__": _name,
        "id": Column(Integer, primary_key=True),
    }
    return type(
        _name,
        (base,),
        {
            **(additional_options or {}),
            **def_attr_def,
            **parse_parent_relationship(parent_table, table_def.name),
            **parse_table_attributes(table_def.attributes, _name),
        },
    )


def parse_enum_value_type(enum_type: Enum) -> str:
    types = list(set(map(lambda x: type(x.value), enum_type.__members__.values())))
    if len(types) == 1:
        return types[0]
    else:
        ValueError(f"Only enums of a single type is supported found {enum_type}")


def collect_option_table(
    optional: OptionTableColumn,
    parent_table: Optional[str] = None,
    additional_options: Optional[dict] = None,
    base: DeclarativeMeta = get_base(),
) -> Type[DeclarativeMeta]:
    """Create table model based on an Internal TableDef

    Args:
        table_def (TableDef): Table description
        parent_table_def (Optional[TableDef], optional): The parent table. Defaults to None.
        additional_options (dict, optional): used for testing, dditional table_args. Defaults to {}.

    Returns:
        Type[Base]: a sql alchemy models
    """
    _name = get_option_table_name(optional, parent_table)
    def_attr_def = {
        "__tablename__": _name,
        "key": Column(
            MappedColumnTypes[parse_enum_value_type(optional.values).__name__].value,
            primary_key=True,
        ),
        "label": Column(String, unique=True),
    }

    return type(_name, (base,), {**(additional_options or {}), **def_attr_def},)


def collect_tables(
    table_def: TableDef,
    parent_table: Optional[str] = None,
    additional_options: Optional[Dict[str, Any]] = None,
    base: DeclarativeMeta = get_base(),
) -> Tuple[DeclarativeMeta, ...]:
    """Create table models based on an Internal TableDef

    Args:
        table_def (TableDef): Table description
        parent_table_def (Optional[TableDef], optional): The parent table. Defaults to None.
        additional_options (dict, optional): used for testing, dditional table_args. Defaults to {}.

    Returns:
        Tuple[Type[Base]]: A tuple of sql alchemy models
    """
    base_case: Tuple[DeclarativeMeta, ...] = ()
    return (
        collect_table(table_def, parent_table, additional_options, base),
        *(
            collect_option_table(
                attr, get_sub_table_name(table_def.name, parent_table), additional_options, base,
            )
            for attr in table_def.attributes
            if isinstance(attr, OptionTableColumn)
        ),
        *reduce(
            lambda x, y: (*x, *y),
            (
                collect_tables(
                    attr.table,
                    get_sub_table_name(table_def.name, parent_table),
                    additional_options,
                    base,
                )
                for attr in table_def.attributes
                if isinstance(attr, SubTable)
            ),
            base_case,
        ),
    )


class DbModels(BaseModel):
    base: DeclarativeMeta
    models: Dict[str, DeclarativeMeta]

    def __getitem__(self, item: Union[str, BaseModel]) -> DeclarativeMeta:
        _name = item if  isinstance(item, str) else  item.__name__
        if self.models.get(_name):
            return self.models.get(_name)
        raise KeyError(f"The db models {_name} does not exist")



def create_models(
    models: Tuple[Type[BaseModel]],
    additional_options: Optional[Dict[str, Any]] = None,
    base: Callable[[], DeclarativeMeta] = get_base,
) -> DbModels:
    """ Create a tuple of specific set of sql alchemy modelf from a pydantic model

    Args:
        model (type[BaseModel]):The pydantic model to generate from
        additional_options (Optional[dict]): Used for testing, add additional table props

    Returns:
        [type]: A tuple of sql alchemy models
    """
    Base = base()
    tables = map(parse_table, models)
    models = map(
        lambda t: collect_tables(t, additional_options=additional_options or {}, base=Base), tables,
    )
    return DbModels(base=Base, models={m.__name__: m for model in models for m in model})
