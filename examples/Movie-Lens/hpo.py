from hwer.validation import *
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import train_test_split

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)
pd.options.display.width = 0
import warnings
import optuna

warnings.filterwarnings('ignore')
import numpy as np

import movielens_data_reader as mdr
from param_fetcher import fetch_svdpp_params, fetch_gcn_params
from optuna.pruners import PercentilePruner

dataset = "100K"
read_data = mdr.get_data_reader(dataset=dataset)
df_user, df_item, ratings = read_data()

#
enable_kfold = True
n_neighbors = 200
verbose = 2  # if os.environ.get("LOGLEVEL") in ["DEBUG", "INFO"] else 0

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

algo = "gcn_hybrid"
objective = "rmse" # or ndcg

from pprint import pprint

pprint(hyperparamters_dict)


def optimisation_objective(hyperparameters, algo, trial):
    if not enable_kfold:
        train_affinities, validation_affinities = train_test_split(user_item_affinities, test_size=0.2,
                                                                   stratify=[u for u, i, r in user_item_affinities])

        _, results, _, _, _ = test_hybrid(train_affinities, validation_affinities, list(df_user.user.values),
                                          list(df_item.item.values), hyperparameters,
                                          prepare_data_mappers, rating_scale, algo,
                                          enable_error_analysis=False, enable_baselines=False)
        rmse, ndcg = results[0]['rmse'], results[0]['ndcg']
    else:
        X = np.array(user_item_affinities)
        y = np.array([u for u, i, r in user_item_affinities])
        skf = StratifiedKFold(n_splits=5)
        results = []
        step = 0
        for train_index, test_index in skf.split(X, y):
            train_affinities, validation_affinities = X[train_index], X[test_index]
            train_affinities = [(u, i, int(r)) for u, i, r in train_affinities]
            validation_affinities = [(u, i, int(r)) for u, i, r in validation_affinities]
            #
            _, res, _, _, _ = test_hybrid(train_affinities, validation_affinities, list(df_user.user.values),
                                          list(df_item.item.values), hyperparameters,
                                          prepare_data_mappers, rating_scale, algo,
                                          enable_error_analysis=False, enable_baselines=False)
            results.extend(res)
            rmse, ndcg = results[0]['rmse'], results[0]['ndcg']
            imv = rmse if objective == "rmse" else 1 - ndcg
            trial.report(imv, step)
            if trial.should_prune():
                raise optuna.exceptions.TrialPruned()
            step += 1

        results = pd.DataFrame.from_records(results)
        results = results.groupby(["algo"]).mean().reset_index()
        rmse, ndcg = results["rmse"].values[0], results["ndcg"].values[0]
    print("RMSE = %.4f, NDCG = %.4f" % (rmse, ndcg))
    return rmse, ndcg


def rmse_objective(trial):
    conv_arch = trial.suggest_categorical('conv_arch', [1])
    network_depth = trial.suggest_int('network_depth', 2, 3)
    epochs = trial.suggest_discrete_uniform('epochs', 50, 100, 10)
    gaussian_noise = trial.suggest_uniform('gaussian_noise', 0., 0.15)
    lr = trial.suggest_loguniform('lr', 1e-2, 5e-2)
    batch_size = trial.suggest_discrete_uniform('batch_size', 512, 2048, 512)
    kernel_l2 = trial.suggest_loguniform('kernel_l2', 1e-9, 1e-7)
    dropout = trial.suggest_uniform('dropout', 0., 0.1)
    n_dims = trial.suggest_discrete_uniform('n_dims', 48, 96, 16)
    params = copy.deepcopy(hyperparamters_dict[algo])

    params["n_dims"] = int(n_dims)
    params["collaborative_params"]["prediction_network_params"]["lr"] = lr
    params["collaborative_params"]["prediction_network_params"]["gaussian_noise"] = gaussian_noise
    params["collaborative_params"]["prediction_network_params"]["epochs"] = int(epochs)
    params["collaborative_params"]["prediction_network_params"]["network_depth"] = int(network_depth)
    params["collaborative_params"]["prediction_network_params"]["conv_arch"] = conv_arch
    params["collaborative_params"]["prediction_network_params"]["kernel_l2"] = kernel_l2
    params["collaborative_params"]["prediction_network_params"]["dropout"] = dropout
    params["collaborative_params"]["prediction_network_params"]["batch_size"] = int(batch_size)
    rmse, _ = optimisation_objective(params, algo, trial)
    return rmse


def ndcg_objective(trial):
    gcn_lr = trial.suggest_loguniform('gcn_lr', 3e-4, 5e-2)
    gcn_epochs = trial.suggest_discrete_uniform('gcn_epochs', 10, 40, 5)
    gcn_layers = trial.suggest_int('gcn_layers', 1, 3)
    gcn_dropout = trial.suggest_uniform('gcn_dropout', 0., 0.1)
    gcn_kernel_l2 = trial.suggest_loguniform('gcn_kernel_l2', 1e-9, 1e-6)
    conv_arch = trial.suggest_categorical('conv_arch', [1])
    gaussian_noise = trial.suggest_uniform('gaussian_noise', 0., 0.2)
    margin = trial.suggest_discrete_uniform('margin', 1.0, 2.0, 0.2)
    n_dims = trial.suggest_discrete_uniform('n_dims', 48, 96, 16)
    params = copy.deepcopy(hyperparamters_dict[algo])
    params["n_dims"] = int(n_dims)
    params["collaborative_params"]["user_item_params"]["gcn_lr"] = gcn_lr
    params["collaborative_params"]["user_item_params"]["gcn_epochs"] = gcn_epochs
    params["collaborative_params"]["user_item_params"]["gcn_layers"] = gcn_layers
    params["collaborative_params"]["user_item_params"]["gcn_dropout"] = gcn_dropout
    params["collaborative_params"]["user_item_params"]["gcn_kernel_l2"] = gcn_kernel_l2
    params["collaborative_params"]["user_item_params"]["conv_arch"] = conv_arch
    params["collaborative_params"]["user_item_params"]["gaussian_noise"] = gaussian_noise
    params["collaborative_params"]["user_item_params"]["margin"] = margin

    _, ndcg = optimisation_objective(params, algo, trial)
    return 1 - ndcg


if __name__ == '__main__':
    storage = 'sqlite:///gcn.db'
    study = optuna.create_study(study_name=algo, storage='sqlite:///%s-%s.db' % (algo, objective),
                                load_if_exists=True,
                                pruner=PercentilePruner(percentile=25.0, n_startup_trials=2, n_warmup_steps=1, interval_steps=1))
    print("Previous Trials...")
    df = study.trials_dataframe(attrs=('number', 'value', 'params', 'state'))
    print(df)

    if objective == "rmse":
        study.optimize(rmse_objective, n_trials=10)
    if objective == "ndcg":
        study.optimize(ndcg_objective, n_trials=10)

    print("Current Trial Results...")
    print(study.best_params, study.best_value)
    print(study.best_value)
    print(study.best_trial)
    df = study.trials_dataframe(attrs=('number', 'value', 'params', 'state'))
    print(df)
