import csv

POS_FILE = "data/pos_transactions.csv"


def load_pos():

    rows=[]

    with open(POS_FILE) as f:

        reader=csv.DictReader(f)

        for r in reader:

            rows.append(r)

    return rows


def pos_summary():

    rows=load_pos()

    revenue=sum(
        float(r["basket_value_inr"])
        for r in rows
    )

    avg_basket=(
        revenue/len(rows)
        if rows else 0
    )

    top_txn=max(
        rows,
        key=lambda x:
        float(
            x["basket_value_inr"]
        )
    )

    return {

    "transactions":
    len(rows),

    "total_revenue":
    round(revenue,2),

    "avg_basket":
    round(avg_basket,2),

    "highest_sale":
    round(
        float(
            top_txn[
                "basket_value_inr"
            ]
        ),
        2
    ),

    "insight":

    f"Store generated ₹{round(revenue,0)} revenue with average basket ₹{round(avg_basket,0)}."
}