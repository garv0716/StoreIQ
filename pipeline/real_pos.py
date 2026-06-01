import pandas as pd

FILE = "data/Brigade_Bangalore_10_April_26 (1)bc6219c.csv"

def pos_analytics():

    df = pd.read_csv(FILE)

    revenue = round(
        df["total_amount"].sum(),
        2
    )

    top_brand = (
        df.groupby("brand_name")
        ["total_amount"]
        .sum()
        .sort_values(
            ascending=False
        )
        .head(5)
        .to_dict()
    )

    top_category = (
        df.groupby("dep_name")
        ["total_amount"]
        .sum()
        .sort_values(
            ascending=False
        )
        .head(5)
        .to_dict()
    )

    top_salesperson = (
        df.groupby(
            "salesperson_name"
        )["total_amount"]
        .sum()
        .sort_values(
            ascending=False
        )
        .head(5)
        .to_dict()
    )

    return {

        "total_revenue": revenue,

        "top_brands":
            top_brand,

        "top_categories":
            top_category,

        "top_salespeople":
            top_salesperson
    }