import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import train_test_split
from hwer.validation import *
from hwer.utils import average_precision

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
pd.options.display.width = 0
import warnings
import os

from hwer import CategoricalEmbed, FlairGlove100AndBytePairEmbed, NumericEmbed, Node, Edge
from hwer.utils import merge_dicts_nested, build_row_dicts
from ast import literal_eval
import numpy as np


def get_data_mapper(df_user, df_item, dataset="100K"):

    def prepare_data_mappers_100K():
        user_nodes = [Node("user", n) for n in df_user.user.values]
        n_users = len(user_nodes)
        user_data = dict(zip(user_nodes, build_row_dicts("categorical", df_user[["gender", "age", "occupation", "zip"]].values)))
        user_numeric = dict(zip(user_nodes, build_row_dicts("numeric", df_user[["user_rating_mean", "user_rating_count"]].values)))
        user_data = merge_dicts_nested(user_data, user_numeric)

        item_nodes = [Node("item", i) for i in df_item.item.values]
        n_items = len(item_nodes)
        df_item.year = "_" + df_item.year.apply(str) + "_"
        item_text = dict(zip(item_nodes, build_row_dicts("text", df_item.text.values)))
        item_cats = dict(zip(item_nodes, build_row_dicts("categorical", df_item[["year", "genres"]].values)))
        item_numerics = dict(zip(item_nodes, build_row_dicts("numeric", np.abs(df_item[["title_length", "overview_length", "runtime", "item_rating_mean", "item_rating_count"]].values))))

        item_data = merge_dicts_nested(item_text, item_cats, item_numerics)
        assert len(user_data) == n_users
        assert len(item_data) == n_items

        node_data = dict(user_data)
        node_data.update(item_data)
        embedding_mapper = dict(user=dict(categorical=CategoricalEmbed(n_dims=32), numeric=NumericEmbed(32)),
                                item=dict(text=FlairGlove100AndBytePairEmbed(), categorical=CategoricalEmbed(n_dims=32), numeric=NumericEmbed(32)))
        return embedding_mapper, node_data

    def prepare_data_mappers_1M():
        user_nodes = [Node("user", n) for n in df_user.user.values]
        n_users = len(user_nodes)
        item_nodes = [Node("item", i) for i in df_item.item.values]
        n_items = len(item_nodes)

        user_data = dict(zip(user_nodes, build_row_dicts("categorical", df_user[["gender", "age", "occupation", "zip"]].values)))
        user_numeric = dict(zip(user_nodes, build_row_dicts("numeric", df_user[["user_rating_mean", "user_rating_count"]].values)))
        user_data = merge_dicts_nested(user_data, user_numeric)

        item_text = dict(zip(item_nodes, build_row_dicts("text", df_item.text.values)))
        item_cats = dict(zip(item_nodes, build_row_dicts("categorical", df_item["genres"].values)))
        item_numerics = dict(zip(item_nodes, build_row_dicts("numeric", np.abs(
            df_item[["title_length", "overview_length", "runtime", "item_rating_mean", "item_rating_count"]].values))))

        item_data = merge_dicts_nested(item_text, item_cats, item_numerics)
        assert len(user_data) == n_users
        assert len(item_data) == n_items
        node_data = dict(user_data)
        node_data.update(item_data)
        embedding_mapper = dict(user=dict(categorical=CategoricalEmbed(n_dims=32), numeric=NumericEmbed(32)),
                                item=dict(text=FlairGlove100AndBytePairEmbed(), categorical=CategoricalEmbed(n_dims=32),
                                          numeric=NumericEmbed(32)))

        return embedding_mapper, node_data

    if dataset == "100K":
        return prepare_data_mappers_100K
    elif dataset == "1M":
        return prepare_data_mappers_1M
    elif dataset == "20M":
        pass
    else:
        raise ValueError("Unsupported Dataset")


def get_data_reader(dataset="100K"):

    def read_data_100K(**kwargs):
        users = pd.read_csv("100K/users.csv", sep="\t")
        movies = pd.read_csv("100K/movies.csv", sep="\t")
        # Based on GC-MC Paper and code: https://github.com/riannevdberg/gc-mc/blob/master/gcmc/preprocessing.py#L326
        test_method = kwargs["test_method"] if "test_method" in kwargs else "random-split"
        if test_method == "random-split" or test_method == "stratified-split":
            if "fold" in kwargs and type(kwargs["fold"]) == int and 1 <= kwargs["fold"] <= 5:
                train_file = "100K/ml-100k/u%s.base" % kwargs["fold"]
                test_file = "100K/ml-100k/u%s.test" % kwargs["fold"]
            else:
                train_file = "100K/ml-100k/u1.base"
                test_file = "100K/ml-100k/u1.test"
            train = pd.read_csv(train_file, sep="\t", header=None, names=["user", "item", "rating", "timestamp"])[["user", "item", "rating"]]
            test = pd.read_csv(test_file, sep="\t", header=None, names=["user", "item", "rating", "timestamp"])[["user", "item", "rating"]]
        elif test_method == "ncf":
            train_file = "100K/ml-100k/u.data"
            train = pd.read_csv(train_file, sep="\t", header=None, names=["user", "item", "rating", "timestamp"])
            train["rating"] = 1
            test = train.groupby('user', group_keys=False).apply(lambda x: x.sort_values(["timestamp"]).tail(1))
            train = train.groupby('user', group_keys=False).apply(lambda x: x.sort_values(["timestamp"]).head(-1))
        else:
            raise ValueError()
        train = train[["user", "item", "rating"]]
        test = test[["user", "item", "rating"]]

        user_stats = train.groupby(["user"])["rating"].agg(["mean", "count"]).reset_index()
        item_stats = train.groupby(["item"])["rating"].agg(["mean", "count"]).reset_index()
        user_stats.rename(columns={"mean": "user_rating_mean", "count": "user_rating_count"}, inplace=True)
        item_stats.rename(columns={"mean": "item_rating_mean", "count": "item_rating_count"}, inplace=True)

        train["is_test"] = False
        test["is_test"] = True
        ratings = pd.concat((train, test))
        movies.genres = movies.genres.fillna("[]").apply(literal_eval)
        movies['year'] = movies['year'].fillna(-1).astype(int)
        movies.keywords = movies.keywords.fillna("[]").apply(literal_eval)
        movies.keywords = movies.keywords.apply(lambda x: " ".join(x))
        movies.tagline = movies.tagline.fillna("")
        text_columns = ["title", "keywords", "overview", "tagline", "original_title"]
        movies[text_columns] = movies[text_columns].fillna("")
        movies['text'] = movies["title"] + " " + movies["keywords"] + " " + movies["overview"] + " " + movies[
            "tagline"] + " " + \
                         movies["original_title"]
        movies["title_length"] = movies["title"].apply(len)
        movies["overview_length"] = movies["overview"].apply(len)
        movies["runtime"] = movies["runtime"].fillna(0.0)
        users.rename(columns={"id": "user"}, inplace=True)
        movies.rename(columns={"id": "item"}, inplace=True)

        users = users.merge(user_stats, how="left", on="user")
        movies = movies.merge(item_stats, how="left", on="item")
        movies = movies.fillna(movies.mean())
        users = users.fillna(users.mean())
        return users, movies, ratings

    def read_data_1M(**kwargs):
        test_method = kwargs["test_method"] if "test_method" in kwargs else "random-split"
        users = pd.read_csv("1M/users.csv", sep="\t", engine="python")
        movies = pd.read_csv("1M/movies.csv", sep="\t", engine="python")
        ratings = pd.read_csv("1M/ratings.csv", sep="\t", engine="python")

        ratings['movie_id'] = ratings['movie_id'].astype(str)
        ratings['user_id'] = ratings['user_id'].astype(str)
        ratings.rename(columns={"user_id": "user", "movie_id": "item"}, inplace=True)
        # Based on Paper https://arxiv.org/pdf/1605.09477.pdf (CF-NADE GC-MC)
        if test_method == "random-split":
            train = ratings.sample(frac=0.9)
            test = ratings[~ratings.index.isin(train.index)]
        elif test_method == "stratified-split":
            from sklearn.model_selection import train_test_split
            train, test = train_test_split(ratings, test_size=0.1, stratify=ratings["user"])
        elif test_method == "ncf":
            train = ratings
            train["rating"] = 1
            test = train.groupby('user', group_keys=False).apply(lambda x: x.sort_values(["timestamp"]).tail(1))
            train = train.groupby('user', group_keys=False).apply(lambda x: x.sort_values(["timestamp"]).head(-1))
        train = train[["user", "item", "rating"]]
        test = test[["user", "item", "rating"]]
        train["is_test"] = False
        test["is_test"] = True
        user_stats = train.groupby(["user"])["rating"].agg(["mean", "count"]).reset_index()
        item_stats = train.groupby(["item"])["rating"].agg(["mean", "count"]).reset_index()
        user_stats.rename(columns={"mean": "user_rating_mean", "count": "user_rating_count"}, inplace=True)
        item_stats.rename(columns={"mean": "item_rating_mean", "count": "item_rating_count"}, inplace=True)
        ratings = pd.concat((train, test))
        users['user_id'] = users['user_id'].astype(str)
        movies['movie_id'] = movies['movie_id'].astype(str)

        movies.genres = movies.genres.fillna("[]").apply(literal_eval)
        movies['year'] = movies['year'].fillna(-1).astype(int)
        movies.keywords = movies.keywords.fillna("[]").apply(literal_eval)
        movies.keywords = movies.keywords.apply(lambda x: " ".join(x))
        movies.tagline = movies.tagline.fillna("")
        text_columns = ["title", "keywords", "overview", "tagline", "original_title"]
        movies[text_columns] = movies[text_columns].fillna("")
        movies['text'] = movies["title"] + " " + movies["keywords"] + " " + movies["overview"] + " " + movies["tagline"] + " " + \
                         movies["original_title"]
        movies["title_length"] = movies["title"].apply(len)
        movies["overview_length"] = movies["overview"].apply(len)
        movies["runtime"] = movies["runtime"].fillna(0.0)
        movies.rename(columns={"movie_id": "item"}, inplace=True)
        users.rename(columns={"user_id": "user"}, inplace=True)
        users = users.merge(user_stats, how="left", on="user")
        movies = movies.merge(item_stats, how="left", on="item")
        movies = movies.fillna(movies.mean())
        users = users.fillna(users.mean())
        return users, movies, ratings

    if dataset == "100K":
        return read_data_100K
    elif dataset == "1M":
        return read_data_1M
    elif dataset == "20M":
        pass
    elif dataset == "netflix":
        pass
    elif dataset == "pinterest":
        pass
    elif dataset == "msd":
        pass
    elif dataset == "douban":
        pass
    else:
        raise ValueError("Unsupported Dataset")


def build_dataset(dataset, **kwargs):
    read_data = get_data_reader(dataset=dataset)
    df_user, df_item, ratings = read_data(**kwargs)
    prepare_data_mappers = get_data_mapper(df_user, df_item, dataset=dataset)
    user_nodes = [Node("user", n) for n in df_user.user.values]
    item_nodes = [Node("item", i) for i in df_item.item.values]
    nodes = user_nodes + item_nodes
    ratings = ratings.sample(frac=1.0)
    assert len(ratings.columns) == 4
    user_item_affinities = [(Node("user", row[0]), Node("item", row[1]),
                             float(row[2]), bool(row[3])) for row in ratings.values]
    user_item_affinities = [(Edge(src, dst, weight), train_test) for src, dst, weight, train_test in user_item_affinities]

    return nodes, user_item_affinities, {"user", "item"}, prepare_data_mappers