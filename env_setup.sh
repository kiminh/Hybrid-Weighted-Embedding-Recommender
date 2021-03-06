#!/usr/bin/env bash

pip install --upgrade pip
pip uninstall -y tensorflow-gpu
cat requirements.txt | xargs -n 1 pip install
pip install gpustat
pip install scikit-learn
pip install cython
pip install --upgrade gensim
pip install node2vec
pip install -e .

git config --global user.name "Faizan Ahemad"
git config --global user.email fahemad3@gmail.com

# install tf
# install fasttext