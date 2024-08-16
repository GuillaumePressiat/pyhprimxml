import polars as pl

# https://github.com/pola-rs/polars/issues/7078
def prefix_field(field):
    """Prefix struct fields with parent column name"""
    return pl.col(field).name.prefix_fields(f"{field}.")

def flatten(df):
    """Flatten one level of struct or list columns, and prefix flattened fields
    with parent column name
    """
    struct_cols = [col for col, dtype in zip(df.columns, df.dtypes) if type(dtype) is pl.Struct]
    list_cols = [col for col, dtype in zip(df.columns, df.dtypes) if type(dtype) is pl.List]

    return df.with_columns(
        *map(prefix_field, struct_cols),
        *map(
            lambda c: pl.col(c).list.to_struct(n_field_strategy='max_width', fields = lambda i: f"{c}.{i}"),
            list_cols,
        ),
    ).unnest(*struct_cols, *list_cols)

def recursively_flatten(df):
    """Recursively flatten list and struct columns"""
    while any(type(dtype) in (pl.Struct, pl.List) for dtype in df.dtypes):
        df = flatten(df)
    return df

def unpack(df: pl.DataFrame, col: str) -> pl.DataFrame:
    """flatten list or struct column"""

    if col not in df.columns:
        df = df.with_columns(pl.lit(None).alias(col))

    check_column_type = type(df.select(col).dtypes[0])
    check_list = check_column_type == pl.List
    check_struct = check_column_type == pl.Struct

    if check_list:
        return df.explode(col).unnest(col)
    else:
        return df.unnest(col)

