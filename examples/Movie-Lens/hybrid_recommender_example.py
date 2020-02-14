from hwer.validation import *
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import train_test_split

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
pd.options.display.width = 0
import warnings

warnings.filterwarnings('ignore')
import numpy as np

import movielens_data_reader as mdr
from param_fetcher import fetch_gcn_params, fetch_svdpp_params

dataset = "100K"
read_data = mdr.get_data_reader(dataset=dataset)
df_user, df_item, ratings = read_data()

#
test_data_subset = False
enable_baselines = False
enable_kfold = False
enable_error_analysis = False
n_neighbors = 200
verbose = 2  # if os.environ.get("LOGLEVEL") in ["DEBUG", "INFO"] else 0

if test_data_subset:
    n_neighbors = 5
    if True:
        item_counts = ratings.groupby(['item'])['user'].count().reset_index()
        item_counts = item_counts[(item_counts["user"] <= 200) & (item_counts["user"] >= 20)].head(100)
        items = set(item_counts["item"])
        ratings = ratings[ratings["item"].isin(items)]

        user_counts = ratings.groupby(['user'])['item'].count().reset_index()
        user_counts = user_counts[(user_counts["item"] <= 100) & (user_counts["item"] >= 20)].head(100)
        users = set(user_counts["user"])
        ratings = ratings[ratings["user"].isin(users)]

        # ratings = pd.concat((ratings[ratings.rating == 1].head(2), ratings[ratings.rating == 5].head(3)))
        users = set(ratings["user"])
        items = set(ratings["item"])
        df_user = df_user[df_user["user"].isin(ratings.user)]
        df_item = df_item[df_item["item"].isin(ratings.item)]
    else:
        cores = 10
        df_user, df_item, ratings = get_small_subset(df_user, df_item, ratings, cores)

prepare_data_mappers = mdr.get_data_mapper(df_user, df_item, dataset=dataset)
ratings = ratings[["user", "item", "rating"]]
user_item_affinities = [(row[0], row[1], float(row[2])) for row in ratings.values]
rating_scale = (np.min([r for u, i, r in user_item_affinities]), np.max([r for u, i, r in user_item_affinities]))

print("Total Samples Taken = %s, |Users| = %s |Items| = %s, Rating scale = %s" % (
    ratings.shape[0], len(df_user.user.values), len(df_item.item.values), rating_scale))

hyperparameter_content = dict(n_dims=40, combining_factor=0.1,
                              knn_params=dict(n_neighbors=n_neighbors,
                                              index_time_params={'M': 15, 'ef_construction': 200, }))

hyperparameters_svdpp = fetch_svdpp_params(dataset)

hyperparameters_gcn = fetch_gcn_params(dataset, "gcn", 2)

hyperparameters_gcn_ncf = fetch_gcn_params(dataset, "gcn_ncf", 2)

hyperparameters_surprise = {"svdpp": {"n_factors": 20, "n_epochs": 20},
                            "svd": {"biased": True, "n_factors": 20},
                            "algos": ["svd"]}

hyperparamters_dict = dict(gcn_hybrid=hyperparameters_gcn,
                           content_only=hyperparameter_content,
                           gcn_ncf=hyperparameters_gcn_ncf,
                           svdpp_hybrid=hyperparameters_svdpp, surprise=hyperparameters_surprise, )

content_only = False
svdpp_hybrid = False
surprise = False
gcn_hybrid = False
gcn_ncf = True

from pprint import pprint

pprint(hyperparamters_dict)

if not enable_kfold:
    train_affinities, validation_affinities = train_test_split(user_item_affinities, test_size=0.2,
                                                               stratify=[u for u, i, r in user_item_affinities])
    print("Train Length = ", len(train_affinities))
    print("Validation Length =", len(validation_affinities))
    recs, results, user_rating_count_metrics = test_once(train_affinities, validation_affinities,
                                                         list(df_user.user.values),
                                                         list(df_item.item.values),
                                                         hyperparamters_dict,
                                                         prepare_data_mappers, rating_scale,
                                                         svdpp_hybrid=svdpp_hybrid, gcn_hybrid=gcn_hybrid,
                                                         gcn_ncf=gcn_ncf,
                                                         surprise=surprise, content_only=content_only,
                                                         enable_error_analysis=enable_error_analysis,
                                                         enable_baselines=enable_baselines)
    results = display_results(results)
    user_rating_count_metrics = user_rating_count_metrics.sort_values(["algo", "user_rating_count"])
    # print(user_rating_count_metrics)
    # user_rating_count_metrics.to_csv("algo_user_rating_count_%s.csv" % dataset, index=False)
    # results.reset_index().to_csv("overall_results_%s.csv" % dataset, index=False)
    # visualize_results(results, user_rating_count_metrics, train_affinities, validation_affinities)
else:
    X = np.array(user_item_affinities)
    y = np.array([u for u, i, r in user_item_affinities])
    skf = StratifiedKFold(n_splits=5)
    results = []
    user_rating_count_metrics = pd.DataFrame([],
                                             columns=["algo", "user_rating_count", "rmse", "mae", "map", "train_rmse",
                                                      "train_mae"])
    for train_index, test_index in skf.split(X, y):
        train_affinities, validation_affinities = X[train_index], X[test_index]
        train_affinities = [(u, i, int(r)) for u, i, r in train_affinities]
        validation_affinities = [(u, i, int(r)) for u, i, r in validation_affinities]
        #
        recs, res, ucrms = test_once(train_affinities, validation_affinities, list(df_user.user.values),
                                     list(df_item.item.values),
                                     hyperparamters_dict,
                                     prepare_data_mappers, rating_scale,
                                     svdpp_hybrid=svdpp_hybrid, gcn_hybrid=gcn_hybrid,
                                     gcn_ncf=gcn_ncf,
                                     surprise=surprise, content_only=content_only,
                                     enable_error_analysis=False, enable_baselines=False)

        user_rating_count_metrics = pd.concat((user_rating_count_metrics, ucrms))
        res = display_results(res)
        results.append(res)
        print("#" * 80)

    results = pd.concat(results)
    results = results.groupby(["algo"]).mean().reset_index()
    user_rating_count_metrics = user_rating_count_metrics.groupby(["algo", "user_rating_count"]).mean().reset_index()
    display_results(results)
    visualize_results(results, user_rating_count_metrics, train_affinities, validation_affinities)
