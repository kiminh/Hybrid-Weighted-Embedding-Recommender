import sys
import os
from os import path
from sklearn.preprocessing import MinMaxScaler
sys.path.append(path.join(path.dirname(__file__), '../'))

sys.path.insert(0, "../")

import sys
sys.path.append(os.getcwd())

from MulticoreTSNE import MulticoreTSNE as TSNE
from sklearn.manifold import TSNE as ScikitTSNE
from sklearn.decomposition import PCA, KernelPCA
from numpy.linalg import norm
from sklearn.utils import shuffle
import numpy as np
from umap import UMAP
import time
import numpy as np
import fitsne
from scipy.special import comb
from math import factorial


from utils import *



# from sklearn.datasets import load_digits
# digits = load_digits().data
# X = digits

(X, _), (_, _) = tf.keras.datasets.mnist.load_data() # [('PCA', '5.2', 0.3014303061728395), ('AutoEnc', '122.7', 0.2701841850617284)]
X = X.reshape(len(X),28*28)
print(X.shape)
# X = np.random.randn(100000, 128)



timings = []
X = unit_length(X, axis=1)
print(compare_embedding_global_distance_mismatches(X, X))





start = time.time()
ZPCA = PCA(n_components=16,).fit_transform(X)
end = time.time()
ZPCA = unit_length(ZPCA, axis=1)
score = compare_embedding_global_distance_mismatches(X, ZPCA)
print("PCA time = %.1f" % (end-start))
timings.append(("PCA", "%.1f"%(end-start),score))


start = time.time()
Zenc = auto_encoder_transform(X,X, n_dims=16,)
end = time.time()
Zenc = unit_length(Zenc, axis=1)
score = compare_embedding_global_distance_mismatches(X, Zenc)
print("AutoEnc time = %.1f" % (end-start))
timings.append(("AutoEnc", "%.1f"%(end-start),score))

start = time.time()
Xmm = MinMaxScaler(feature_range=(-0.95, 0.95)).fit_transform(X)
Zenc = auto_encoder_transform(Xmm,Xmm, n_dims=16,)
end = time.time()
Zenc = unit_length(Zenc, axis=1)
score = compare_embedding_global_distance_mismatches(X, Zenc)
print("AutoEnc time = %.1f" % (end-start))
timings.append(("AutoEnc", "%.1f"%(end-start),score))

#
# start = time.time()
# Z = fitsne.FItSNE(X, no_dims=32, nthreads=2, initialization=Zenc.copy(order='C').astype(np.float64), perplexity=5)
# end = time.time()
# score = dist_compare(X, Z)
# print("FitSNE time = %.1f" % (end-start))
# timings.append(("Initialized FitSNE","%.1f"%(end-start), score))
#
#
# start = time.time()
# Z = fitsne.FItSNE(X, no_dims=32, nthreads=2, perplexity=5)
# end = time.time()
# score = dist_compare(X, Z)
# print("FitSNE time = %.1f" % (end-start))
# timings.append(("FitSNE","%.1f"%(end-start), score))

#
# start = time.time()
# Z = UMAP(n_components=32,n_neighbors=10, metric="euclidean", init=ZPCA, min_dist=0.1,negative_sample_rate=10).fit_transform(X)
# end = time.time()
# score = dist_compare(X, Z)
# print("UMAP init time = %.1f" % (end-start))
# timings.append(("UMAP init","%.1f"%(end-start), score))
#
# start = time.time()
# Z = UMAP(n_components=32,n_neighbors=10, metric="euclidean", init="spectral",min_dist=0.1,negative_sample_rate=10).fit_transform(X)
# end = time.time()
# score = dist_compare(X, Z)
# print("UMAP time = %.1f" % (end-start))
# timings.append(("UMAP","%.1f"%(end-start), score))

# start = time.time()
# tsne_model = TSNE(2, n_jobs=2, perplexity=5.0)
# Z = tsne_model.fit_transform(X)
# end = time.time()
# score = dist_compare(X, Z)
# print("MulticoreTSNE time = %.1f" % (end-start))
# timings.append(("MulticoreTSNE", "%.1f"%(end-start),score))

# start = time.time()
# tsne_model = ScikitTSNE(32, method='exact')
# Z = tsne_model.fit_transform(X)
# end = time.time()
# print("Scikit TSNE time = %.1f" % (end-start))
# timings.append("%.1f"%(end-start))

#
# start = time.time()
# Z = KernelPCA(n_components=32,kernel="linear", n_jobs=2,).fit_transform(X)
# end = time.time()
# print("Linear Kernel PCA time = %.1f" % (end-start))
# timings.append(("Linear Kernel PCA","%.1f"%(end-start)))
#
# start = time.time()
# Z = KernelPCA(n_components=32,kernel="rbf", n_jobs=2).fit_transform(X)
# end = time.time()
# print("RBF PCA time = %.1f" % (end-start))
# timings.append(("RBF Kernel PCA","%.1f"%(end-start)))

print(timings)


