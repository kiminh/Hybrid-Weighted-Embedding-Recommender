import time
from collections import Counter
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow.keras.backend as K
from bidict import bidict
from more_itertools import flatten
from sklearn.model_selection import StratifiedKFold
from surprise import Dataset
from surprise import Reader
from surprise import SVDpp
from tensorflow import keras

from .hybrid_recommender import HybridRecommender
from .logging import getLogger
from .recommendation_base import EntityType
from .utils import RatingPredRegularization, get_rng, \
    LRSchedule, resnet_layer_with_content, ScaledGlorotNormal, root_mean_squared_error, mean_absolute_error, \
    normalize_affinity_scores_by_user_item_bs


class SVDppDNN(HybridRecommender):
    def __init__(self, embedding_mapper: dict, knn_params: Optional[dict], rating_scale: Tuple[float, float],
                 n_content_dims: int = 32, n_collaborative_dims: int = 32, fast_inference: bool = False):
        super().__init__(embedding_mapper, knn_params, rating_scale, n_content_dims, n_collaborative_dims, fast_inference)
        self.log = getLogger(type(self).__name__)

    def __build_dataset__(self, user_ids: List[str], item_ids: List[str],
                          user_item_affinities: List[Tuple[str, str, float]],
                          user_content_vectors: np.ndarray, item_content_vectors: np.ndarray,
                          user_vectors: np.ndarray, item_vectors: np.ndarray,
                          user_id_to_index: Dict[str, int], item_id_to_index: Dict[str, int],
                          rating_scale: Tuple[float, float], hyperparams: Dict):
        batch_size = hyperparams["batch_size"] if "batch_size" in hyperparams else 512
        padding_length = hyperparams["padding_length"] if "padding_length" in hyperparams else 100
        noise_augmentation = hyperparams["noise_augmentation"] if "noise_augmentation" in hyperparams else False
        use_content = hyperparams["use_content"] if "use_content" in hyperparams else True
        rng = get_rng(noise_augmentation)
        user_content_vectors_mean = np.mean(user_content_vectors)
        item_content_vectors_mean = np.mean(item_content_vectors)
        user_vectors_mean = np.mean(user_vectors)
        item_vectors_mean = np.mean(item_vectors)
        self.log.debug("user_content_vectors_mean = %s,  item_content_vectors_mean = %s, user_vectors_mean = %s, item_vectors_mean = %s",
                       user_content_vectors_mean, item_content_vectors_mean, user_vectors_mean, item_vectors_mean)

        ###
        ratings = np.array([r for u, i, r in user_item_affinities])
        min_affinity = np.min(ratings)
        max_affinity = np.max(ratings)
        mu, user_bias, item_bias, _, _ = normalize_affinity_scores_by_user_item_bs(user_item_affinities, rating_scale)
        affinity_range = max_affinity - min_affinity

        user_bias = np.array([user_bias[u] if u in user_bias else 0.0 for u in user_ids])
        item_bias = np.array([item_bias[i] if i in item_bias else 0.0 for i in item_ids])
        self.log.debug("Mu = %.4f, Max User Bias = %.4f, Max Item Bias = %.4f, min-max-affinity = %s",
                       mu, np.abs(np.max(user_bias)),
                       np.abs(np.max(item_bias)), (min_affinity, max_affinity))

        ratings_count_by_user = Counter([u for u, i, r in user_item_affinities])
        ratings_count_by_item = Counter([i for u, i, r in user_item_affinities])

        ratings_count_by_user = defaultdict(int, {k: 1/np.sqrt(v) for k, v in ratings_count_by_user.items()})
        ratings_count_by_item = defaultdict(int, {k: 1/np.sqrt(v) for k, v in ratings_count_by_item.items()})

        user_item_list = defaultdict(list)
        item_user_list = defaultdict(list)
        for i, j, r in user_item_affinities:
            user_item_list[i].append(item_id_to_index[j])
            item_user_list[j].append(user_id_to_index[i])
        for k, v in user_item_list.items():
            user_item_list[k] = np.array(v)[:padding_length] + 1

        for k, v in item_user_list.items():
            item_user_list[k] = np.array(v)[:padding_length] + 1

        def gen_fn(i, j):
            user = user_id_to_index[i]
            item = item_id_to_index[j]
            items = user_item_list[i]
            items = np.pad(items, (padding_length - len(items), 0), constant_values=(0, 0))

            users = item_user_list[j]
            users = np.pad(users, (padding_length - len(users), 0), constant_values=(0, 0))

            nu = ratings_count_by_user[i]
            ni = ratings_count_by_item[j]
            if use_content:
                ucv = user_content_vectors[user]
                uv = user_vectors[user]
                icv = item_content_vectors[item]
                iv = item_vectors[item]
                return user, item, users, items, nu, ni, ucv, uv, icv, iv
            return user, item, users, items, nu, ni

        def generate_training_samples(affinities: List[Tuple[str, str, float]]):
            def generator():
                for i, j, r in affinities:
                    r = r + rng(1, 0.01 * affinity_range)
                    yield gen_fn(i, j), r

            return generator

        prediction_output_shape = ((), (), padding_length, padding_length, (), ())
        prediction_output_types = (tf.int64, tf.int64, tf.int64, tf.int64, tf.float64, tf.float64)
        if use_content:
            prediction_output_shape = prediction_output_shape + (self.n_content_dims, self.n_collaborative_dims, self.n_content_dims, self.n_collaborative_dims)
            prediction_output_types = prediction_output_types + (tf.float64, tf.float64, tf.float64, tf.float64)
        output_shapes = (prediction_output_shape, ())
        output_types = (prediction_output_types, tf.float64)

        train = tf.data.Dataset.from_generator(generate_training_samples(user_item_affinities),
                                               output_types=output_types, output_shapes=output_shapes, )

        train = train.shuffle(batch_size*10).batch(batch_size).prefetch(32)
        return mu, user_bias, item_bias, train, \
               ratings_count_by_user, ratings_count_by_item, \
               min_affinity, max_affinity, user_item_list, item_user_list, \
               gen_fn, prediction_output_shape, prediction_output_types

    def __build_prediction_network__(self, user_ids: List[str], item_ids: List[str],
                                     user_item_affinities: List[Tuple[str, str, float]],
                                     user_content_vectors: np.ndarray, item_content_vectors: np.ndarray,
                                     user_vectors: np.ndarray, item_vectors: np.ndarray,
                                     user_id_to_index: Dict[str, int], item_id_to_index: Dict[str, int],
                                     rating_scale: Tuple[float, float], hyperparams: Dict):
        self.log.debug(
            "Start Building Prediction Network, collaborative vectors shape = %s, content vectors shape = %s",
            (user_vectors.shape, item_vectors.shape), (user_content_vectors.shape, item_content_vectors.shape))

        lr = hyperparams["lr"] if "lr" in hyperparams else 0.001
        epochs = hyperparams["epochs"] if "epochs" in hyperparams else 15
        batch_size = hyperparams["batch_size"] if "batch_size" in hyperparams else 512
        verbose = hyperparams["verbose"] if "verbose" in hyperparams else 1
        bias_regularizer = hyperparams["bias_regularizer"] if "bias_regularizer" in hyperparams else 0.0
        padding_length = hyperparams["padding_length"] if "padding_length" in hyperparams else 100
        use_content = hyperparams["use_content"] if "use_content" in hyperparams else False
        kernel_l2 = hyperparams["kernel_l2"] if "kernel_l2" in hyperparams else 0.0
        n_collaborative_dims = user_vectors.shape[1]
        network_width = hyperparams["network_width"] if "network_width" in hyperparams else 128
        network_depth = hyperparams["network_depth"] if "network_depth" in hyperparams else 3
        dropout = hyperparams["dropout"] if "dropout" in hyperparams else 0.0
        use_resnet = hyperparams["use_resnet"] if "use_resnet" in hyperparams else False

        assert user_content_vectors.shape[1] == item_content_vectors.shape[1]
        assert user_vectors.shape[1] == item_vectors.shape[1]

        mu, user_bias, item_bias, train, \
        ratings_count_by_user, ratings_count_by_item, \
        min_affinity, \
        max_affinity, user_item_list, item_user_list, \
        gen_fn, prediction_output_shape, prediction_output_types = self.__build_dataset__(user_ids, item_ids,
                                                                              user_item_affinities,
                                                                              user_content_vectors,
                                                                              item_content_vectors,
                                                                              user_vectors, item_vectors,
                                                                              user_id_to_index,
                                                                              item_id_to_index,
                                                                              rating_scale, hyperparams)
        input_user = keras.Input(shape=(1,))
        input_item = keras.Input(shape=(1,))
        input_items = keras.Input(shape=(padding_length,))
        input_users = keras.Input(shape=(padding_length,))
        input_nu = keras.Input(shape=(1,))
        input_ni = keras.Input(shape=(1,))

        inputs = [input_user, input_item, input_users, input_items, input_nu, input_ni]
        if use_content:
            input_ucv = keras.Input(shape=(self.n_content_dims,))
            input_uv = keras.Input(shape=(self.n_collaborative_dims,))
            input_icv = keras.Input(shape=(self.n_content_dims,))
            input_iv = keras.Input(shape=(self.n_collaborative_dims,))
            inputs.extend([input_ucv, input_uv, input_icv, input_iv])

        embeddings_initializer = tf.keras.initializers.Constant(user_bias)
        user_bias = keras.layers.Embedding(len(user_ids), 1, input_length=1, embeddings_initializer=embeddings_initializer)(input_user)

        item_initializer = tf.keras.initializers.Constant(item_bias)
        item_bias = keras.layers.Embedding(len(item_ids), 1, input_length=1, embeddings_initializer=item_initializer)(input_item)
        user_bias = keras.layers.ActivityRegularization(l2=bias_regularizer)(user_bias)
        item_bias = keras.layers.ActivityRegularization(l2=bias_regularizer)(item_bias)
        user_bias = tf.keras.layers.Flatten()(user_bias)
        item_bias = tf.keras.layers.Flatten()(item_bias)

        def main_network():
            embeddings_initializer = tf.keras.initializers.Constant(user_vectors)
            user_vec = keras.layers.Embedding(len(user_ids), n_collaborative_dims, input_length=1)(input_user)

            item_initializer = tf.keras.initializers.Constant(item_vectors)
            item_vec = keras.layers.Embedding(len(item_ids), n_collaborative_dims, input_length=1,
                                              embeddings_initializer=item_initializer)(input_item)

            user_initializer = tf.keras.initializers.Constant(
                np.concatenate((np.array([[0.0] * n_collaborative_dims]), user_vectors), axis=0))
            user_vecs = keras.layers.Embedding(len(user_ids) + 1, n_collaborative_dims,
                                               input_length=padding_length, mask_zero=True)(input_users)
            user_vecs = keras.layers.ActivityRegularization(l2=bias_regularizer)(user_vecs)
            user_vecs = tf.keras.layers.GlobalAveragePooling1D()(user_vecs)
            user_vecs = user_vecs * input_ni

            item_initializer = tf.keras.initializers.Constant(
                np.concatenate((np.array([[0.0] * n_collaborative_dims]), item_vectors), axis=0))
            item_vecs = keras.layers.Embedding(len(item_ids) + 1, n_collaborative_dims,
                                               input_length=padding_length, mask_zero=True,
                                               embeddings_initializer=item_initializer)(input_items)
            item_vecs = keras.layers.ActivityRegularization(l2=bias_regularizer)(item_vecs)
            item_vecs = tf.keras.layers.GlobalAveragePooling1D()(item_vecs)
            item_vecs = item_vecs * input_nu

            user_vec = keras.layers.ActivityRegularization(l2=bias_regularizer)(user_vec)
            item_vec = keras.layers.ActivityRegularization(l2=bias_regularizer)(item_vec)
            user_vec = tf.keras.layers.Flatten()(user_vec)
            item_vec = tf.keras.layers.Flatten()(item_vec)
            user_item_vec_dot = tf.keras.layers.Dot(axes=1, normalize=False)([user_vec, item_vec])
            item_items_vec_dot = tf.keras.layers.Dot(axes=1, normalize=False)([item_vec, item_vecs])
            user_user_vec_dot = tf.keras.layers.Dot(axes=1, normalize=False)([user_vec, user_vecs])
            implicit_term = user_item_vec_dot + item_items_vec_dot + user_user_vec_dot

            if use_content:
                user_item_content_similarity = tf.keras.layers.Dot(axes=1, normalize=True)([input_ucv, input_icv])
                user_item_collab_similarity = tf.keras.layers.Dot(axes=1, normalize=True)([input_uv, input_iv])
                vectors = [input_ucv, input_uv, input_icv, input_iv]
                meta_data = [implicit_term, user_item_vec_dot, item_items_vec_dot, user_user_vec_dot,
                            input_ni, input_nu, user_item_content_similarity, user_item_collab_similarity,
                            user_bias, item_bias]
                vectors = K.concatenate(vectors)
                meta_data = K.concatenate(meta_data)
                meta_data = keras.layers.Dense(64, activation="tanh", kernel_regularizer=keras.regularizers.l1_l2(l2=kernel_l2))(meta_data)
                vectors = keras.layers.Dense(2 * (self.n_collaborative_dims + self.n_content_dims), activation="tanh", kernel_regularizer=keras.regularizers.l1_l2(l2=kernel_l2))(vectors)
                dense_rep = K.concatenate([vectors, meta_data])
                for i in range(network_depth):
                    dense_rep = tf.keras.layers.Dropout(dropout)(dense_rep)
                    if use_resnet:
                        dense_rep = resnet_layer_with_content(network_width, network_width, dropout, kernel_l2)(
                            dense_rep)
                    else:
                        dense_rep = keras.layers.Dense(network_width, activation="tanh",
                                                       kernel_regularizer=keras.regularizers.l1_l2(l2=kernel_l2))(dense_rep)
                    dense_rep = tf.keras.layers.BatchNormalization()(dense_rep)
                rating = keras.layers.Dense(1, activation="tanh",
                                            kernel_regularizer=keras.regularizers.l1_l2(l2=kernel_l2))(dense_rep)
                implicit_term = implicit_term + rating

            return implicit_term

        rating = mu + user_bias + item_bias + main_network()

        self.log.debug("Rating Shape = %s", rating.shape)

        model = keras.Model(inputs=inputs, outputs=[rating])

        sgd = tf.keras.optimizers.SGD(learning_rate=lr, momentum=0.9, nesterov=True)
        model.compile(optimizer=sgd,
                      loss=[root_mean_squared_error], metrics=[root_mean_squared_error, mean_absolute_error])

        model.fit(train, epochs=epochs, callbacks=[], verbose=verbose)

        prediction_artifacts = {"model": model, "user_item_list": user_item_list,
                                "item_user_list": item_user_list,
                                "ratings_count_by_user": ratings_count_by_user, "padding_length": padding_length,
                                "ratings_count_by_item": ratings_count_by_item,
                                "batch_size": batch_size, "gen_fn": gen_fn,
                                "user_content_vectors": user_content_vectors, "item_content_vectors": item_content_vectors,
                                "user_vectors": user_vectors, "item_vectors": item_vectors,
                                "prediction_output_shape": prediction_output_shape,
                                "prediction_output_types": prediction_output_types}
        self.log.info("Built Prediction Network, model params = %s", model.count_params())
        return prediction_artifacts

    def predict(self, user_item_pairs: List[Tuple[str, str]], clip=True) -> List[float]:
        start = time.time()
        model = self.prediction_artifacts["model"]
        ratings_count_by_user = self.prediction_artifacts["ratings_count_by_user"]
        ratings_count_by_item = self.prediction_artifacts["ratings_count_by_item"]
        batch_size = self.prediction_artifacts["batch_size"]
        user_item_list = self.prediction_artifacts["user_item_list"]
        item_user_list = self.prediction_artifacts["item_user_list"]
        padding_length = self.prediction_artifacts["padding_length"]
        user_content_vectors = self.prediction_artifacts["user_content_vectors"]
        user_vectors = self.prediction_artifacts["user_vectors"]
        item_content_vectors = self.prediction_artifacts["item_content_vectors"]
        item_vectors = self.prediction_artifacts["item_vectors"]
        gen_fn = self.prediction_artifacts["gen_fn"]
        prediction_output_shape = self.prediction_artifacts["prediction_output_shape"]
        prediction_output_types = self.prediction_artifacts["prediction_output_types"]
        batch_size = max(1024, batch_size)

        def generate_prediction_samples(affinities: List[Tuple[str, str]],
                                        user_id_to_index: Dict[str, int], item_id_to_index: Dict[str, int],
                                        ratings_count_by_user: Counter, ratings_count_by_item: Counter):
            def generator():
                for i, j in affinities:
                    yield gen_fn(i, j)
            return generator

        if self.fast_inference:
            return self.fast_predict(user_item_pairs)

        predict = tf.data.Dataset.from_generator(generate_prediction_samples(user_item_pairs,
                                                                             self.user_id_to_index, self.item_id_to_index,
                                                                             ratings_count_by_user, ratings_count_by_item),
                                                 output_types=prediction_output_types, output_shapes=prediction_output_shape, )
        predict = predict.batch(batch_size).prefetch(16)
        predictions = np.array(list(flatten([model.predict(x).reshape((-1)) for x in predict])))
        assert len(predictions) == len(user_item_pairs)
        if clip:
            predictions = np.clip(predictions, self.rating_scale[0], self.rating_scale[1])
        self.log.info("Finished Predicting for n_samples = %s, time taken = %.2f",
                      len(user_item_pairs),
                      time.time() - start)
        return predictions