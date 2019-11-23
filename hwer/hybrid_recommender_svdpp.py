from .recommendation_base import RecommendationBase, Feature, FeatureSet
from typing import List, Dict, Tuple, Sequence, Type, Set, Optional
from sklearn.decomposition import PCA
from scipy.special import comb
from pandas import DataFrame
from .content_embedders import ContentEmbeddingBase
import tensorflow as tf
import time
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import re
from bidict import bidict
from joblib import Parallel, delayed
from collections import defaultdict
import gc
import sys
import os
from more_itertools import flatten
import dill
from collections import Counter
import operator
from tqdm import tqdm_notebook
import fasttext
from .recommendation_base import EntityType
from .content_recommender import ContentRecommendation
from .utils import unit_length, build_user_item_dict, build_item_user_dict, cos_sim, shuffle_copy, \
    normalize_affinity_scores_by_user, normalize_affinity_scores_by_user_item
import tensorflow as tf
from tensorflow import keras
from sklearn.model_selection import train_test_split
import tensorflow.keras.backend as K
from scipy.stats import describe
from surprise import SVD, SVDpp
from surprise import Dataset
from surprise import Reader


from .hybrid_recommender import HybridRecommender


class HybridRecommenderSVDpp(HybridRecommender):
    def __init__(self, embedding_mapper: dict, knn_params: Optional[dict], rating_scale: Tuple[float, float],
                 n_content_dims: int = 32, n_collaborative_dims: int = 32):
        super().__init__(embedding_mapper, knn_params, rating_scale, n_content_dims, n_collaborative_dims)

    def __build_prediction_network__(self, user_ids: List[str], item_ids: List[str],
                                     user_item_affinities: List[Tuple[str, str, float]],
                                     user_content_vectors: np.ndarray, item_content_vectors: np.ndarray,
                                     user_vectors: np.ndarray, item_vectors: np.ndarray,
                                     user_id_to_index: Dict[str, int], item_id_to_index: Dict[str, int],
                                     rating_scale: Tuple[float, float], hyperparams: Dict):

        # max_affinity = np.max([r for u, i, r in user_item_affinities])
        # min_affinity = np.min([r for u, i, r in user_item_affinities])
        lr = hyperparams["lr"] if "lr" in hyperparams else 0.001
        epochs = hyperparams["epochs"] if "epochs" in hyperparams else 15
        batch_size = hyperparams["batch_size"] if "batch_size" in hyperparams else 512
        network_width = hyperparams["network_width"] if "network_width" in hyperparams else 2
        network_depth = hyperparams["network_depth"] if "network_depth" in hyperparams else 3
        verbose = hyperparams["verbose"] if "verbose" in hyperparams else 1
        kernel_l1 = hyperparams["kernel_l1"] if "kernel_l1" in hyperparams else 0.001
        kernel_l2 = hyperparams["kernel_l2"] if "kernel_l2" in hyperparams else 0.001
        activity_l1 = hyperparams["activity_l1"] if "activity_l1" in hyperparams else 0.0005
        activity_l2 = hyperparams["activity_l2"] if "activity_l2" in hyperparams else 0.0005
        bias_regularizer = hyperparams["bias_regularizer"] if "bias_regularizer" in hyperparams else 0.01
        dropout = hyperparams["dropout"] if "dropout" in hyperparams else 0.1
        svdpp = hyperparams["svdpp"] if "svdpp" in hyperparams else {"n_factors":10, "n_epochs":10}

        max_affinity = rating_scale[1]
        min_affinity = rating_scale[0]
        n_content_dims = user_content_vectors.shape[1]
        n_collaborative_dims = user_vectors.shape[1]

        assert user_content_vectors.shape[1] == item_content_vectors.shape[1]
        assert user_vectors.shape[1] == item_vectors.shape[1]

        svd_train = pd.DataFrame(user_item_affinities)
        reader = Reader(rating_scale=rating_scale)
        svd_train = Dataset.load_from_df(svd_train, reader).build_full_trainset()
        svd_model = SVDpp(**svdpp)
        svd_model.fit(svd_train)

        svd_predictions = svd_model.test(svd_train.build_testset())
        user_item_affinities = [(p.uid, p.iid, p.r_ui - p.est) for p in svd_predictions]

        ###
        ratings = np.array([r for u, i, r in user_item_affinities])
        min_affinity = np.min(ratings)
        max_affinity = np.max(ratings)
        user_item_affinities = [(u, i, (2 * (r - min_affinity) / (max_affinity - min_affinity)) - 1) for u, i, r in
                                user_item_affinities]

        def inverse_fn(user_item_predictions):
            def inner(r):
                rscaled = ((r + 1) / 2) * (max_affinity - min_affinity) + min_affinity
                return rscaled
            rscaled = np.array([inner(r) for u, i, r in user_item_predictions])
            svd_predictions = np.array([svd_model.predict(u, i).est for u, i, r in user_item_predictions])
            return rscaled + svd_predictions

        mu, user_bias, item_bias, _, _ = normalize_affinity_scores_by_user_item(user_item_affinities)
        user_bias = np.array([user_bias[u] if u in user_bias else np.random.rand() * 0.01 for u in user_ids])
        item_bias = np.array([item_bias[i] if i in item_bias else np.random.rand() * 0.01 for i in item_ids])
        print("Mu = ", mu, " User Bias = ", np.abs(np.max(user_bias)), " Item Bias = ", np.abs(np.max(item_bias)))

        ratings_count_by_user = Counter([u for u, i, r in user_item_affinities])
        ratings_count_by_item = Counter([i for u, i, r in user_item_affinities])

        train_affinities, validation_affinities = train_test_split(user_item_affinities, test_size=0.5)

        def generate_training_samples(affinities: List[Tuple[str, str, float]]):
            def generator():
                for i, j, r in affinities:
                    user = user_id_to_index[i]
                    item = item_id_to_index[j]
                    user_content = user_content_vectors[user]
                    item_content = item_content_vectors[item]
                    user_collab = user_vectors[user]
                    item_collab = item_vectors[item]

                    ratings_by_user = np.log1p((ratings_count_by_user[i] + 10.0) / 10.0)
                    ratings_by_item = np.log1p((ratings_count_by_item[j] + 10.0) / 10.0)
                    yield (user, item, user_content, item_content, user_collab, item_collab,
                           ratings_by_user, ratings_by_item), r

            return generator

        output_shapes = (
            ((), (), (n_content_dims), (n_content_dims), (n_collaborative_dims), (n_collaborative_dims), (), ()),
            ())
        output_types = (
        (tf.int64, tf.int64, (tf.float64), (tf.float64), (tf.float64), (tf.float64), tf.float64, tf.float64),
        tf.float64)

        train = tf.data.Dataset.from_generator(generate_training_samples(train_affinities),
                                               output_types=output_types, output_shapes=output_shapes, )
        validation = tf.data.Dataset.from_generator(generate_training_samples(validation_affinities),
                                                    output_types=output_types,
                                                    output_shapes=output_shapes, )

        train = train.shuffle(batch_size).batch(batch_size)
        validation = validation.shuffle(batch_size).batch(batch_size)

        input_user = keras.Input(shape=(1,))
        input_item = keras.Input(shape=(1,))

        user = tf.keras.layers.Flatten()(input_user)
        item = tf.keras.layers.Flatten()(input_item)

        embeddings_initializer = tf.keras.initializers.Constant(user_bias)
        user_bias = keras.layers.Embedding(len(user_ids), 1, input_length=1,
                                           embeddings_initializer=embeddings_initializer)(user)

        item_initializer = tf.keras.initializers.Constant(item_bias)
        item_bias = keras.layers.Embedding(len(item_ids), 1, input_length=1,
                                           embeddings_initializer=item_initializer)(item)

        user_bias = keras.layers.Dense(1, activation="linear",
                                       kernel_regularizer=keras.regularizers.l1_l2(l1=0.0, l2=0.0),
                                       activity_regularizer=keras.regularizers.l1_l2(l1=0.0, l2=bias_regularizer))(
            user_bias)

        item_bias = keras.layers.Dense(1, activation="linear",
                                       kernel_regularizer=keras.regularizers.l1_l2(l1=0.0, l2=0.0),
                                       activity_regularizer=keras.regularizers.l1_l2(l1=0.0, l2=bias_regularizer))(
            item_bias)

        input_1 = keras.Input(shape=(n_content_dims,))
        input_2 = keras.Input(shape=(n_content_dims,))
        input_3 = keras.Input(shape=(n_collaborative_dims,))
        input_4 = keras.Input(shape=(n_collaborative_dims,))

        user_content = tf.keras.layers.Flatten()(input_1)
        item_content = tf.keras.layers.Flatten()(input_2)
        user_collab = tf.keras.layers.Flatten()(input_3)
        item_collab = tf.keras.layers.Flatten()(input_4)

        user_item_content_similarity = tf.keras.layers.Dot(axes=1, normalize=True)([user_content, item_content])
        user_item_collab_similarity = tf.keras.layers.Dot(axes=1, normalize=True)([user_collab, item_collab])
        user_item_content_similarity = tf.keras.layers.Flatten()(user_item_content_similarity)
        user_item_content_similarity = tf.keras.layers.Flatten()(user_item_content_similarity)
        input_5 = keras.Input(shape=(1,))
        input_6 = keras.Input(shape=(1,))

        ratings_by_user = tf.keras.layers.Flatten()(input_5)
        ratings_by_item = tf.keras.layers.Flatten()(input_6)

        user_content = keras.layers.Dense(n_content_dims * network_width, activation="tanh",
                                          kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1, l2=kernel_l2),
                                          activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1,
                                                                                        l2=activity_l2))(user_content)
        item_content = keras.layers.Dense(n_content_dims * network_width, activation="tanh",
                                          kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1, l2=kernel_l2),
                                          activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1,
                                                                                        l2=activity_l2))(item_content)
        user_collab = keras.layers.Dense(n_collaborative_dims * network_width, activation="tanh",
                                         kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1, l2=kernel_l2),
                                         activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1, l2=activity_l2))(
            user_collab)
        item_collab = keras.layers.Dense(n_collaborative_dims * network_width, activation="tanh",
                                         kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1, l2=kernel_l2),
                                         activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1, l2=activity_l2))(
            item_collab)
        user_content = tf.keras.layers.Dropout(dropout)(user_content)
        item_content = tf.keras.layers.Dropout(dropout)(item_content)
        user_collab = tf.keras.layers.Dropout(dropout)(user_collab)
        item_collab = tf.keras.layers.Dropout(dropout)(item_collab)

        vectors = K.concatenate([user_content, item_content, user_collab, item_collab])

        counts_data = keras.layers.Dense(8, activation="tanh")(K.concatenate([ratings_by_user, ratings_by_item]))
        meta_data = K.concatenate([counts_data, user_item_content_similarity, user_item_collab_similarity])
        meta_data = keras.layers.Dense(16, activation="tanh", )(meta_data)

        dense_representation = K.concatenate([meta_data, vectors])
        dense_representation = tf.keras.layers.BatchNormalization()(dense_representation)
        n_dims = 2 * (n_collaborative_dims * 4) + 2 * (n_content_dims * 4) + 8

        for i in range(network_depth):
            dense_representation = keras.layers.Dense(n_dims * network_width, activation="tanh",
                                                      kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1,
                                                                                                  l2=kernel_l2),
                                                      activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1,
                                                                                                    l2=activity_l2))(
                dense_representation)
            dense_representation = tf.keras.layers.BatchNormalization()(dense_representation)
            dense_representation = tf.keras.layers.Dropout(dropout)(dense_representation)

        dense_representation = keras.layers.Dense(n_dims * network_width * 4, activation="tanh",
                                                  kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1,
                                                                                              l2=kernel_l2),
                                                  activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1,
                                                                                                l2=activity_l2))(
            dense_representation)

        rating = keras.layers.Dense(1, activation="linear", use_bias=True,
                                    kernel_regularizer=keras.regularizers.l1_l2(l1=kernel_l1, l2=kernel_l2),
                                    activity_regularizer=keras.regularizers.l1_l2(l1=activity_l1, l2=activity_l2))(
            dense_representation)
        rating = tf.keras.backend.constant(mu) + user_bias + item_bias + rating
        # rating = K.clip(rating, -1.0, 1.0)
        model = keras.Model(inputs=[input_user, input_item, input_1, input_2, input_3, input_4,
                                    input_5, input_6],
                            outputs=[rating])

        adam = tf.keras.optimizers.Adam(lr=lr, beta_1=0.9, beta_2=0.999, epsilon=None, decay=0.01, amsgrad=False)
        model.compile(optimizer=adam,
                      loss=['mean_squared_error'])

        es = tf.keras.callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0, patience=3, verbose=0,
                                              restore_best_weights=True)
        reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.2, patience=1, min_lr=0.0001)
        callbacks = [es, reduce_lr]

        model.fit(train, epochs=epochs,
                  validation_data=validation, callbacks=callbacks, verbose=verbose)

        K.set_value(model.optimizer.lr, lr)

        es = tf.keras.callbacks.EarlyStopping(monitor='val_loss', min_delta=0.0, patience=3, verbose=0,
                                              restore_best_weights=True)
        reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", factor=0.2, patience=1, min_lr=0.0001)
        callbacks = [es, reduce_lr]

        model.fit(validation, epochs=epochs,
                  validation_data=train, callbacks=callbacks, verbose=verbose)
        print("Train Loss = ", model.evaluate(train), "validation Loss = ", model.evaluate(validation))

        prediction_artifacts = {"model": model, "inverse_fn": inverse_fn,
                                "ratings_count_by_user": ratings_count_by_user,
                                "ratings_count_by_item": ratings_count_by_item,
                                "batch_size": batch_size}
        return prediction_artifacts