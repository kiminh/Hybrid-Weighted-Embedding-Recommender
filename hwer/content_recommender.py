from typing import List, Dict, Set

import numpy as np
from bidict import bidict
from sklearn.preprocessing import OneHotEncoder
from collections import defaultdict

from .embed import BaseEmbed
from .logging import getLogger
from .recommendation_base import RecommendationBase, NodeType, Node, Edge, FeatureName
from .utils import unit_length, auto_encoder_transform


class ContentRecommendation(RecommendationBase):
    def __init__(self, embedding_mapper: Dict[NodeType, Dict[str, BaseEmbed]],
                 node_types: Set[str],
                 n_dims: int = 32):
        super().__init__(node_types=node_types,
                         n_dims=n_dims)

        self.embedding_mapper: Dict[NodeType, Dict[str, BaseEmbed]] = embedding_mapper
        self.log = getLogger(type(self).__name__)

    def __build_content_embeddings__(self, nodes: List[Node], edges: List[Edge],
                                     node_data: Dict[Node, Dict[FeatureName, object]], n_dims):
        self.log.debug("ContentRecommendation::__build_embeddings__:: Started...")
        all_embeddings = None
        node_to_idx_internal = bidict()
        for nt in self.node_types:
            nt_embedding = None
            nt_nodes = list(filter(lambda n: n.node_type == nt, nodes))
            assert len(set(nt_nodes) - set(node_data.keys())) == 0 or len(set(nt_nodes) - set(node_data.keys())) == len(
                set(nt_nodes))
            assert len(set(nt_nodes)) == len(nt_nodes)
            if len(set(nt_nodes) - set(node_data.keys())) == len(set(nt_nodes)):
                nt_embedding = np.zeros((len(nt_nodes), 1))
            else:
                nt_nodes_features: List[Dict[FeatureName, object]] = [node_data[ntn] for ntn in nt_nodes]
                feature_names = list(nt_nodes_features[0].keys())

                for f in feature_names:
                    feature = [ntnf[f] for ntnf in nt_nodes_features]
                    embedding = self.embedding_mapper[nt][f].fit_transform(feature)
                    if nt_embedding is None:
                        nt_embedding = embedding
                    else:
                        np.concatenate((nt_embedding, embedding), axis=1)
                nt_embedding = unit_length(nt_embedding, axis=1)

            #
            cur_len = len(node_to_idx_internal)
            node_to_idx_internal.update(bidict(zip(nt_nodes, range(cur_len, cur_len + len(nt_nodes)))))
            if all_embeddings is None:
                all_embeddings = nt_embedding
            else:
                c1 = np.concatenate((all_embeddings, np.zeros((all_embeddings.shape[0], nt_embedding.shape[1]))),
                                    axis=1)
                c2 = np.concatenate((np.zeros((nt_embedding.shape[0], all_embeddings.shape[1])), nt_embedding), axis=1)
                all_embeddings = np.concatenate((c1, c2), axis=0)

        all_embeddings = all_embeddings[[node_to_idx_internal[n] for n in nodes]]
        nts = np.array([n.node_type for n in nodes]).reshape((-1, 1))
        ohe_node_types = OneHotEncoder(sparse=False).fit_transform(nts)
        all_embeddings = np.concatenate((all_embeddings, ohe_node_types), axis=1)
        self.log.debug(
            "ContentRecommendation::__build_embeddings__:: AutoEncoder with dims = %s" % str(all_embeddings.shape))
        n_dims = n_dims if n_dims is not None and not np.isinf(n_dims) else 2 ** int(np.log2(all_embeddings.shape[1]))
        from sklearn.decomposition import IncrementalPCA
        all_embeddings = IncrementalPCA(n_components=n_dims, batch_size=2**16).fit_transform(all_embeddings)
        all_embeddings = unit_length(all_embeddings, axis=1)
        extra_dims = 2 ** int(np.ceil(np.log2(ohe_node_types.shape[1]))) - ohe_node_types.shape[1]
        if extra_dims != 0:
            ohe_node_types = np.concatenate((ohe_node_types, np.zeros((ohe_node_types.shape[0], extra_dims))), axis=1)
        all_embeddings = np.concatenate((all_embeddings, ohe_node_types), axis=1)
        self.log.info("ContentRecommendation::__build_embeddings__:: Built Content Embedding with dims = %s" % str(
            all_embeddings.shape))
        edges = list(edges) + [Edge(n, n, 1.0) for n in nodes]
        adjacency_list = defaultdict(list)
        for src, dst, w in edges:
            adjacency_list[src].append(dst)
            adjacency_list[dst].append(src)
        nodes_to_idx = self.nodes_to_idx
        adjacent_vectors = np.vstack([all_embeddings[[nodes_to_idx[adj] for adj in adjacency_list[n]]].mean(0) for n in nodes])
        assert adjacent_vectors.shape == all_embeddings.shape
        all_embeddings = (all_embeddings + adjacent_vectors)/2.0
        return all_embeddings

    def fit(self,
            nodes: List[Node],
            edges: List[Edge],
            node_data: Dict[Node, Dict[FeatureName, object]],
            **kwargs):

        super().fit(nodes, edges, node_data)
        embeddings = self.__build_content_embeddings__(nodes, edges, node_data, self.n_dims)
        embeddings = unit_length(embeddings, axis=1)
        self.__build_knn__(embeddings)

        # AutoEncoder them so that error is minimised and distance is maintained
        # https://stats.stackexchange.com/questions/351212/do-autoencoders-preserve-distances
        # Distance Preserving vs Non Preserving

        self.fit_done = True
        return embeddings
