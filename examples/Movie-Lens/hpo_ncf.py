from hyperopt import fmin, tpe, hp, STATUS_OK, STATUS_FAIL, Trials
import argparse
import copy
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import train_test_split
from hpo_base import optimisation_objective, init_args
from param_fetcher import get_best_params
import numpy as np
from hwer.validation import *
import dill as pkl
import sys
import hyperopt

enable_kfold = False

TRIALS_FOLDER = 'hyperopt_trials'
NUMBER_TRIALS_PER_RUN = 1

# https://github.com/MilesCranmer/easy_distributed_hyperopt

def report(imv, step):
    pass


def build_params(args, objective, params):
    params = copy.deepcopy(params)
    params["collaborative_params"]["prediction_network_params"]["lr"] = args["lr"]
    params["collaborative_params"]["prediction_network_params"]["epochs"] = int(args["epochs"])
    params["collaborative_params"]["prediction_network_params"]["kernel_l2"] = args["kernel_l2"]
    params["collaborative_params"]["prediction_network_params"]["batch_size"] = int(args["batch_size"])
    params["collaborative_params"]["prediction_network_params"]["conv_depth"] = int(args["conv_depth"])
    params["collaborative_params"]["prediction_network_params"]["gaussian_noise"] = args["gaussian_noise"]
    params["collaborative_params"]["prediction_network_params"]["gcn_layers"] = int(args["gcn_layers"])
    params["collaborative_params"]["prediction_network_params"]["ncf_layers"] = int(args["ncf_layers"])
    params["collaborative_params"]["prediction_network_params"]["ns_proportion"] = float(args["ns_proportion"])
    params["collaborative_params"]["prediction_network_params"]["ps_proportion"] = float(args["ps_proportion"])
    params["collaborative_params"]["prediction_network_params"]["margin"] = float(args["margin"])
    params["collaborative_params"]["prediction_network_params"]["nsh"] = float(args["nsh"])
    params["n_dims"] = int(args["n_dims"])

    return params


def run_trial(args):
    """Evaluate the model loss using the hyperparams in args
    :args: A dictionary containing all hyperparameters
    :returns: Dict with status and loss from cross-validation
    """

    loss = np.nan
    hyperparams = build_params(args, objective, params)
    import traceback
    try:
        rmse, ndcg, ncf_ndcg = optimisation_objective(hyperparams, algo, report, dataset, test_method)
        loss = 1 - ncf_ndcg
    except Exception as e:
        traceback.print_exc()
    return {
        'status': 'fail' if np.isnan(loss) else 'ok',
        'loss': loss
    }


def define_search_space(objective, starting_params):
    prediction = starting_params["collaborative_params"]["prediction_network_params"]
    space = {
        'lr': hp.qlognormal("lr", np.log(prediction["lr"]),
                            0.5 * prediction["lr"],
                            0.05 * prediction["lr"]),
        'epochs': hp.quniform('epochs',
                              prediction["epochs"] - 10,
                              prediction["epochs"] + 20, 5),
        'kernel_l2': hp.choice('kernel_l2',
                               [0.0, hp.qloguniform('kernel_l2_choice', np.log(1e-9), np.log(1e-5), 5e-9)]),
        'batch_size': hp.qloguniform('batch_size', np.log(1024), np.log(4096), 1024),
        'conv_depth': hp.quniform('conv_depth', 1, prediction["conv_depth"] + 2, 1),
        'gcn_layers': hp.quniform('gcn_layers', 1, prediction["gcn_layers"] + 1, 1),
        'ncf_layers': hp.quniform('ncf_layers', 1, prediction["ncf_layers"] + 1, 1),
        'ps_proportion': hp.choice('ps_proportion',
                                    [0.0, hp.qloguniform('ps_proportion_choice', np.log(0.1), np.log(prediction["ps_proportion"] + 1.0), 0.05)]),
        'ns_proportion': hp.quniform('ns_proportion', 0.0, prediction["ns_proportion"] + 2.0, 0.1),
        'nsh': hp.quniform('nsh', 0.0, prediction["nsh"] + 2.0, 0.1),
        # 'gaussian_noise': hp.qlognormal('gaussian_noise', np.log(prediction["gaussian_noise"]),
        #                                 0.5 * prediction["gaussian_noise"], 0.005),
        'gaussian_noise': hp.choice('gaussian_noise',
                               [0.0, hp.qloguniform('gaussian_noise_choice', np.log(1e-3), np.log(0.5), 1e-3)]),
        'margin': hp.choice('margin',
                                    [0.0, hp.qloguniform('margin_choice', np.log(1e-4), np.log(0.05), 5e-4)]),
        'n_dims': hp.quniform('n_dims',
                              starting_params["n_dims"] - 16,
                              starting_params["n_dims"] + 64, 16),
    }
    return space


def merge_trials(trials1, trials2_slice):
    """Merge two hyperopt trials objects
    :trials1: The primary trials object
    :trials2_slice: A slice of the trials object to be merged,
        obtained with, e.g., trials2.trials[:10]
    :returns: The merged trials object
    """
    max_tid = 0
    if len(trials1.trials) > 0:
        max_tid = max([trial['tid'] for trial in trials1.trials])

    for trial in trials1.trials:
        for key in trial['misc']['idxs'].keys():
            if len(trial['misc']['vals'][key]) == 0:
                trial['misc']['idxs'][key] = []

    for trial in trials2_slice:
        tid = trial['tid'] + max_tid + 1
        hyperopt_trial = Trials().new_trial_docs(
                tids=[None],
                specs=[None],
                results=[None],
                miscs=[None])
        hyperopt_trial[0] = trial
        hyperopt_trial[0]['tid'] = tid
        hyperopt_trial[0]['misc']['tid'] = tid
        for key in hyperopt_trial[0]['misc']['idxs'].keys():
            if len(hyperopt_trial[0]['misc']['vals'][key]) == 0:
                hyperopt_trial[0]['misc']['idxs'][key] = []
            else:
                hyperopt_trial[0]['misc']['idxs'][key] = [tid]
        trials1.insert_trial_docs(hyperopt_trial)
        trials1.refresh()
    return trials1


def load_trials(algo, dataset, objective):
    loaded_fnames = []
    trials = None
    path = TRIALS_FOLDER + '/%s_%s_%s_*.pkl' % (algo, dataset, objective)
    for fname in glob.glob(path):
        trials_obj = pkl.load(open(fname, 'rb'))
        n_trials = trials_obj['n']
        trials_obj = trials_obj['trials']
        if len(loaded_fnames) == 0:
            trials = trials_obj
        else:
            print("Merging trials")
            trials = merge_trials(trials, trials_obj.trials[-n_trials:])

        loaded_fnames.append(fname)
    print("Loaded trials", len(loaded_fnames))
    return trials


def print_trial_details(trials):
    best_loss = np.inf
    best_trial = None
    vals = []
    for trial in trials:
        if trial['result']['status'] == 'ok':
            loss = trial['result']['loss']
            val = dict(copy.deepcopy(trial['misc']['vals']))
            val = {k: v[0] if len(v)>0 else "-" for k, v in val.items()}
            val['loss'] = loss
            vals.append(val)
            if loss < best_loss:
                best_loss = loss
                best_trial = trial
    print(pd.DataFrame.from_records(vals))
    print("Best = ", best_loss, best_trial['misc']['vals'])


if __name__ == '__main__':
    params, dataset, objective, algo, test_method = init_args()
    # Run new hyperparameter trials until killed
    while True:
        np.random.seed()

        # Load up all runs:
        import glob

        trials = load_trials(algo, dataset, objective)
        if trials is None:
            trials = Trials()
        else:
            print_trial_details(trials)

        n = NUMBER_TRIALS_PER_RUN
        try:
            best = fmin(run_trial,
                        space=define_search_space(objective, params),
                        algo=tpe.suggest,
                        max_evals=n + len(trials.trials),
                        trials=trials,
                        verbose=1,
                        rstate=np.random.RandomState(np.random.randint(1, 10 ** 6))
                        )
        except hyperopt.exceptions.AllTrialsFailed:
            continue

        print('current best', best)
        hyperopt_trial = Trials()

        # Merge with empty trials dataset:
        save_trials = merge_trials(hyperopt_trial, trials.trials[-n:])
        new_fname = TRIALS_FOLDER + '/%s_%s_%s_' % (algo, dataset, objective) + str(np.random.randint(0, sys.maxsize)) + '.pkl'
        pkl.dump({'trials': save_trials, 'n': n}, open(new_fname, 'wb'))




