import asyncio
import os
from typing import NamedTuple

import aiohttp
import time
import pandas as pd
from aiolimiter import AsyncLimiter
from geojson import Feature, FeatureCollection, Point, dump

FILENAME = "Post_Adressdaten20170425.csv"
BATCH_SIZE = 50000
limiter = AsyncLimiter(80, 1)  # 80 tasks per second


class Address(NamedTuple):
    street: str
    street_number: str
    zip: int
    locality: str


async def enrich_address(address: Address, semaphore) -> (float, float):
    url = f"http://localhost:5000/api/geo"
    json_body = {
        "Locality": str(address.locality),
        "Zip": str(address.zip),
        "Street": str(address.street),
        "StreetNumber": str(address.street_number),
    }
    async with aiohttp.ClientSession() as session:
        await semaphore.acquire()
        async with limiter:
            try:
                async with session.post(url, json=json_body) as resp:
                    # Would implement a proper retry policy which only retries on specific status codes and some
                    # sensible backoff
                    if resp.status != 200:
                        raise Exception(resp.status, resp.content)
                    content = await resp.json()
                    semaphore.release()
                    return content["latitude"], content["longitude"]
            except aiohttp.ClientConnectorError:
                # The server seems to reject too many connections - since the rate limit above might be too high,
                # we sleep if this happens
                print("rate limit")
                await asyncio.sleep(5)
                semaphore.release()


def read_in_file_to_df(filename: str) -> pd.DataFrame:
    header_list = [
        "Type",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
    ]
    return pd.read_csv(filename, sep=";", names=header_list, encoding="ISO-8859-1")


def extract_address_data(df: pd.DataFrame) -> pd.DataFrame:
    streets = df[df.Type == 4].iloc[:, [1, 2, 6]]
    streets.columns = ["STRID", "ONRP", "street"]
    streets = streets.astype({"ONRP": "int32", "STRID": "int32", "street": "string"})

    location = df[df.Type == 1].iloc[:, [1, 4, 8]]
    location.columns = ["ONRP", "zip", "locality"]
    location = location.astype({"ONRP": "int32", "zip": "int32", "locality": "string"})

    number = df[df.Type == 6].iloc[:, [2, 3, 4]]
    number.columns = ["STRID", "street_number", "HNRA"]
    number = number[~number["street_number"].isnull()]
    number["HNRA"] = number["HNRA"].fillna("")
    number = number.astype(
        {"STRID": "int32", "street_number": "int32", "HNRA": "string"}
    )
    number["street_number"] = number["street_number"].astype("string") + number["HNRA"]

    numbers_with_street = number.merge(streets, on="STRID", how="left")
    streets_with_location = numbers_with_street.merge(location, on="ONRP", how="left")
    return streets_with_location[["street_number", "street", "zip", "locality"]]


def to_geo_json(df: pd.DataFrame) -> None:
    features = []
    insert_features = lambda x: features.append(
        Feature(
            geometry=Point((x["longitude"], x["latitude"])),
            properties=dict(
                street=x["street"],
                street_number=x["street_number"],
                zip=x["zip"],
                locality=x["locality"],
            ),
        )
    )
    df.apply(insert_features, axis=1)
    feature_collection = FeatureCollection(features=features)
    json_filename = os.path.splitext(FILENAME)[0] + ".geojson"
    with open(json_filename, "w", encoding="utf-8") as f:
        dump(feature_collection, f, ensure_ascii=False)


async def main() -> None:
    semaphore = asyncio.Semaphore(value=252)
    df = read_in_file_to_df(FILENAME)
    address_df = extract_address_data(df)
    # This is a quick way to not create 1M+ tasks for all addresses at once. One could improve the performance here
    # by using some parallel processing framework like dask.
    dfs = []
    current_row = 0
    address_df = address_df[:10000]
    while current_row <= address_df.shape[0]:
        dfs.append(address_df[current_row : current_row + BATCH_SIZE])
        current_row += BATCH_SIZE
    for i, sub_df in enumerate(dfs):
        print(i)
        sub_df[["latitude", "longitude"]] = await asyncio.gather(
            *[enrich_address(v, semaphore) for v in sub_df.itertuples()]
        )
    to_geo_json(pd.concat(dfs))


if __name__ == "__main__":
    s = time.perf_counter()
    asyncio.run(main())
    elapsed = time.perf_counter() - s
    print(f"Execution time: {elapsed:0.2f} seconds.")
