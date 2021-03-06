# Hybrid-Weighted-Embedding-Recommendation
A Hybrid Recommendation system which uses Content embeddings and augments them with collaborative features. Weighted Combination of embeddings enables solving cold start with fast training and serving

# TODO:
- Improve docs
- Multi-item types
- Users-Multiple_item_types-Other-things enabled graph
- No users and items just unique str ids
- de-couple affinity vectors from rating vectors
- Proper example of how to build and test an external dataset with ML-100K
    - Example of using content data and not using it
- Make system independent of content so recsys with no content can be used.
- Make a section in readme of how to reproduce
- From Factorization meets the neighborhood paper take section 6 - `evaluation of a top-K recommender` and implement its metric system
- Priming of GCN vectors can be done by unbiased svd instead of word2vec
- Positive, Negative and Anchor can be weighed separately
- Validation module, try predicting link prediction accuracy by taking test links and mixing fake links in same proportion

# TODO:
- Paper: Figure out sections and relevant papers to take content arrangement hints.
- Figure out latex template codes for relevant conferences.
    - AMLC
    - ICLR/AAAI/NIPS/ICML/IEEE/ACM kdd, sigkdd, recsys
    
- ML-20M
- ML-100K/ML-1M/ML-20M vanilla, feat, text-feat
- Ablation Study
    - Resnet Arch vs Normal Arch
    - Text Features, other features, no features/ no content
    - No/Gaussian noise
    - Node2vec, triplet vectors input


# Environment Setup
- Install Anaconda from https://www.anaconda.com/distribution/

Add `.condarc` to your home dir with below contents

```bash
auto_update_conda: False
channels:
  - defaults
  - anaconda
  - conda-forge
always_yes: True
add_pip_as_python_dependency: True
use_pip: True
create_default_packages:
  - pip
  - ipython
  - jupyter
  - nb_conda
  - setuptools
  - wheel
```

`conda update conda`

`conda create -n hybrid-recsys python=3.7.4`

`conda activate hybrid-recsys`


Install [Fasttext](https://fasttext.cc/docs/en/supervised-tutorial.html)

```bash
wget https://github.com/facebookresearch/fastText/archive/v0.9.1.zip
unzip v0.9.1.zip
cd fastText-0.9.1 && make -j4 && pip install .
```

Install Tensorflow 2.0 from [here](https://www.tensorflow.org/install)
```bash
pip install --upgrade pip
pip install tensorflow
```

pip install -r requirements.txt


# Experiments
- Content Based
- Content + Collaborative with extra features
- Content + Collaborative with extra features with alpha tree

# TODO
- Add new item/user with content features https://stats.stackexchange.com/questions/320962/matrix-factorization-in-recommender-systems-adding-a-new-user?rq=1
- Add Testing for Implicit and content data framework like https://github.com/benfred/implicit and https://github.com/lyst/lightfm and https://maciejkula.github.io/spotlight/index.html
- Add Testing for Fast.ai recommendation framework
- Add `Recall@K` for user's with less than `L` ratings in training.
- Add support to detect if gpu present and change `env_setup.sh` accordingly. 
- Add Filter Function support for search functions
- Try Huber Loss
- Ability to Test with multiple recsys with different hyper-params
- Hyper param optimisation via bayesian opt
- Add Embedding layer to GCN Triplet training, see if time increases from 50s [Done]
- Try Normal triplet + GCN
- Image Auto-Encoder (De-noising) File based, Image Auto-Encoder DVAE. Use Average Rating for that item as a target too.
- In predict method, model.predict_generator instead of tfds for speed 

# Innovation
- Heterogenous Features via Deep Networks
- Weighted Triplet Loss
- Embedding Compression
    - We train in a higher Dimensional Space, After training we use autoencoders to reduce dimensionality. 
    - Since our task involves cosine distance, after auto-enc step we do another step where we use triplet loss with Distances calculated from initial bigger embeddings. 
    This is similar to TSNE.
    - the two steps can be combined into one encoder-decoder-triplet architecture where decoder loss and triplet loss are weighted and added.
    
- Combine Collaborative and Content Based Approach by 
    - building content embeddings first
    - enhancing them with collaborative relations
    - Balancing between them using a weighted scheme to solve cold start problem
- Multiple hybrid embeddings for sellers at different life-cycle stages. Multiple alpha


# References

### Interesting Papers
- [Deep Reinforcement Learning based Recommendation with Explicit User-Item Interactions Modeling](https://arxiv.org/pdf/1810.12027.pdf)
- [Inductive Representation Learning on Large Graphs](https://arxiv.org/abs/1706.02216)

### Datasets and Downloads
- https://github.com/celiao/tmdbsimple/
- https://www.kaggle.com/tmdb/tmdb-movie-metadata#tmdb_5000_movies.csv
- http://www.cs.cmu.edu/~ark/personas/ and https://github.com/askmeegs/movies
- https://www.kaggle.com/jrobischon/wikipedia-movie-plots/data#
- https://github.com/markriedl/WikiPlots
- https://www.kaggle.com/c/yelp-recsys-2013/data
- https://www.kaggle.com/rounakbanik/the-movies-dataset or [Google Drive Mirror](https://drive.google.com/open?id=1aBT4ojTiY-2I5NxUJAq2R1BtxbU7mpIQ)

### Misc References
- http://stevehanov.ca/blog/?id=145
- https://towardsdatascience.com/lossless-triplet-loss-7e932f990b24
- http://fastml.com/evaluating-recommender-systems/

### Triplet Loss
- https://www.tensorflow.org/addons/tutorials/losses_triplet
- https://github.com/noelcodella/tripletloss-keras-tensorflow/blob/master/tripletloss.py
- https://github.com/AdrianUng/keras-triplet-loss-mnist/blob/master/Triplet_loss_KERAS_semi_hard_from_TF.ipynb
- https://github.com/keras-team/keras/issues/9498
- https://github.com/maciejkula/triplet_recommendations_keras
- https://towardsdatascience.com/lossless-triplet-loss-7e932f990b24
    
### Dimensionality Reduction
- https://github.com/DmitryUlyanov/Multicore-TSNE
- https://github.com/lmcinnes/umap
- https://github.com/KlugerLab/FIt-SNE https://pypi.org/project/fitsne/0.1.10/
- https://stats.stackexchange.com/questions/402668/intuitive-explanation-of-how-umap-works-compared-to-t-sne
- https://github.com/nmslib/hnswlib

    
### Metrics
- https://stackoverflow.com/questions/34252298/why-rank-based-recommendation-use-ndcg
    

### Trouble-Shooting
- https://medium.com/@HojjatA/could-not-find-valid-device-for-node-while-eagerly-executing-8f2ff588d1e

### Tools
- https://docs.aws.amazon.com/codecommit/latest/userguide/setting-up-gc.html
- https://github.com/eliorc/node2vec

### Code
- https://github.com/lorenzMuller/kernelNet_MovieLens/blob/master/dataLoader.py

