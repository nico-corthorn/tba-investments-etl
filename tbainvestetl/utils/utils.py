import re
from concurrent import futures


def compute(args, fun, max_workers=4):
    """General purpose parallel computing function."""
    print("Processing elements in parallel")
    ex = futures.ThreadPoolExecutor(max_workers=max_workers)
    ex.map(fun, args)


def compute_loop(args, fun):
    """Simple for loop. For debugging purposes mainly."""
    print("Processing elements one by one")
    for symbol in args:
        fun(symbol)


def filter_elements_config(df, params, suffix=""):
    """
    Receives
        df: DataFrame with 'ticker', 'asset_types', 'exchanges' as columns (none index)
        params: dictionary with keys 'asset_types',
                'exchanges', 'additional_symbols', 'only_missing'
        suffix: String to add at the end of every key in params.
            For webScraper is ''
            For raw_factors is '_raw'
            For scale_factors is '_scale'

    Returns a filtered version of df (in rows only) satisfying the params constraints
    """
    if len(params["only_symbols" + suffix]) > 0:
        data = df.loc[df["ticker"].isin(params["only_symbols" + suffix]), :]
    else:
        cond_asset_types = df["asset_type"].isin(params["asset_types" + suffix])
        cond_exchange = df["exchange"].isin(params["exchanges" + suffix])
        cond_additional_symbols = df["ticker"].isin(params["additional_symbols" + suffix])
        cond = (cond_asset_types & cond_exchange) | cond_additional_symbols
        data = df.loc[cond, :]

    return data


def camel_to_snake(name: str):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def str2bool(v: str):
    return v.lower() in ("yes", "true", "t", "1")


def is_number(s: str):
    try:
        float(s)
        return True
    except ValueError:
        return False
