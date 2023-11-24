# Authors: Albert Thomas
#          Alexandre Gramfort
# License: BSD (3-clause)

# Anomaly detection estimators used in the papers. Except for the ones based
# on k-NN (AverageKLPE, MaxKLPE), the others are implemented in scikit-learn.

import numpy as np
import pandas as pd

from sklearn import ensemble
from sklearn.base import BaseEstimator
from sklearn.svm import OneClassSVM
from sklearn.neighbors import NearestNeighbors, KernelDensity
from hdbscan import HDBSCAN


class HDBSCAN_(BaseEstimator):
    def __init__(self,
                 min_cluster_size=15,
                 min_samples=None,
                 cluster_selection_method='leaf',
                 metric='euclidean',
                 contamination=0.1,
                ):

        self.min_cluster_size = min_cluster_size
        self.min_samples = min_samples
        self.metric = metric
        self.cluster_selection_method = cluster_selection_method
        self.hdbscan = HDBSCAN(min_cluster_size=self.min_cluster_size,
                               min_samples=self.min_samples,
                               cluster_selection_method=self.cluster_selection_method,
                               metric=self.metric,
                               )
        self.contamination = contamination

    def fit(self, X):
        self.hdbscan.fit(X)
        self.scores_fit_ = - self.hdbscan.outlier_scores_

        return self

    def score_samples(self, X):
        self.hdbscan.fit(X)
        scores = - self.hdbscan.outlier_scores_
        return scores

    def predict(self, X):
        threshold = np.percentile(self.scores_fit_, 100 * self.contamination)
        pred = (self.score_samples(X) >= threshold).astype(int)

        return pred

    def get_params(self, deep=True):
        return {'min_cluster_size': self.min_cluster_size,
                'min_samples': self.min_samples,
                'cluster_selection_method': self.cluster_selection_method,
                'metric': self.metric,
               }


class KLPE(BaseEstimator):
    """Anomaly detection scoring functions based on k nearest neighbors.

    Returns a scoring function that rank observations according to their
    degree of abnormality.

    The implementation is based on the scikit-learn implementation of nearest
    neighbors.

    Parameters
    ----------
    k : integer, optional (default=6)
        Number of neighbors to consider

    algo : string, optional (default='average')
        Specify how the scoring function is estimated. If algo is 'max', the
        score of x is the distance of x to its k-th nearest neighbor in the
        training data set.
        If algo is 'average', the score of x is the average of its distances
        to its k-th nearest neighbors in the training data set.

    novelty : boolean, optional (default=False)
        Whether the algorithm is to be applied for outlier detection
        (novelty=False) or novelty detection (novelty=True).
        If novelty=False then the score_samples method is only meant to be
        applied on the training samples, a query point not being considered
        its own neighbor. If novelty=True then the score_samples method is only
        meant to be applied on test samples.

    contamination : float, optional (default=0.05)
        Value to declare wether an observation is abnormal or not. An
        observation is declared abnormal if its score belongs to the
        (contamination * 100)% lowest scores of the training set.
        Should be in (0, 1).

    References
    ----------
    .. [1] Zhao, M. and Saligrama, V. "Anomaly Detection with Score functions
        based on Nearest Neighbor Graphs". In Advances in Neural Information
        Processing Systems 22. 2009.
    .. [2] Qian, J. and Saligrama, V. "New statistic in p-value estimation for
        anomaly detection". In Statistical Signal Processing Workshop (SSP),
        2012 IEEE. 2012.
    """

    def __init__(self, k=6, algo='average', novelty=False, contamination=0.05):

        self.k = k
        self.algo = algo
        self.contamination = contamination
        self.novelty = novelty

    def fit(self, X):
        """Fits a k nearest neighbors estimator and computes scores on the
        training samples.

        Parameters
        ----------
        X : array, shape (n_samples, n_features)
            Training data set.
        """

        k = self.k
        algo = self.algo

        nbrs = NearestNeighbors(n_neighbors=k).fit(X)
        self.nbrs_ = nbrs

        # Compute scores on training sample. The opposite of the scores
        # is returned to respect the convention "the higher the better".
        dist_fit, _ = nbrs.kneighbors()
        if algo == 'max':
            self.scores_fit_ = - np.max(dist_fit, axis=1)
        elif algo == 'average':
            self.scores_fit_ = - np.mean(dist_fit, axis=1)

        self.threshold_ = np.percentile(self.scores_fit_,
                                        100 * self.contamination)

        return self

    def score_samples(self, X):
        """Computes the score of each observation in the data set X with the
        convention "the higher the better", i.e. the smaller the score the
        more abnormal the observation.

        Parameters
        ----------
        X : array, shape (n_samples, n_features)
            Data set.

        Returns
        -------
        score : array, shape (n_samples,)
            Returns the scores of the samples.
        """

        algo = self.algo
        novelty = self.novelty
        nbrs = self.nbrs_

        # The opposite of the scores is returned to respect the convention
        # "the higher the better".
        if novelty:
            # Compute scores for test samples
            dists, _ = nbrs.kneighbors(X)
            if algo == 'max':
                scores = - np.max(dists, axis=1)
            elif algo == 'average':
                scores = - np.mean(dists, axis=1)
        else:
            # compute distances for training samples without considering the
            # query point its own neighbor
            scores = self.scores_fit_

        return scores

    def predict(self, X):
        """Predict class for X : +1 if normal, 0 if abnormal. Respects
        scikit-learn convention "the higher, the better".

        The anomalies are the observations whose scores belong to the
        (contamination * 100)% lowest scores of the training set.

        Parameters
        ----------
        X : array, shape (n_samples, n_features)
            Data set.

        Returns
        -------
        y : array, shape (n_samples,)
            Predicted classes.
        """

        pred = (self.score_samples(X) >= self.threshold_).astype(int)

        return pred


class AverageKLPE(KLPE):
    """Anomaly detection estimator based on KLPE estimator with algo='average'

    Parameters
    ----------
    k : integer, optional (default=6)
        Number of neighbors to consider

    novelty : boolean, optional (default=False)
        Whether the algorithm is to be applied for outlier detection
        (novelty=False) or novelty detection (novelty=True).
        If novelty=False then the score_samples method is only meant to be
        applied on the training samples, a query point not being considered
        its own neighbor. If novelty=True then the score_samples method is only
        meant to be applied on test samples.

    contamination : float, optional (default=0.05)
        Value to declare wether an observation is abnormal or not. An
        observation is declared abnormal if its score belongs to the
        (contamination * 100)% lowest scores of the training set.
        Should be in (0, 1).
    """

    def __init__(self, k=6, novelty=False, contamination=0.05):

        super(AverageKLPE, self).__init__(k=k, algo='average', novelty=novelty,
                                          contamination=contamination)


class MaxKLPE(KLPE):
    """Anomaly detection estimator based on KLPE estimator with algo='max'

    Parameters
    ----------
    k : integer, optional (default=6)
        Number of neighbors to consider

    novelty : boolean, optional (default=False)
        Whether the algorithm is to be applied for outlier detection
        (novelty=False) or novelty detection (novelty=True).
        If novelty=False then the score_samples method is only meant to be
        applied on the training samples, a query point not being considered
        its own neighbor. If novelty=True then the score_samples method is only
        meant to be applied on test samples.

    contamination : float, optional (default=0.05)
        Value to declare wether an observation is abnormal or not. An
        observation is declared abnormal if its score belongs to the
        (contamination * 100)% lowest scores of the training set.
        Should be in (0, 1).
    """

    def __init__(self, k=6, novelty=False, contamination=0.05):

        super(MaxKLPE, self).__init__(k=k, algo='max', novelty=novelty,
                                      contamination=contamination)


class OCSVM(OneClassSVM):
    """Anomaly detection estimator based on the One-Class SVM. The kernel used
    is the Gaussian kernel defined as
                k(x, x') = exp(- norm(x-x',2)^2 / (2 * sigma^2))

    Parameters
    ----------
    sigma : float, optional (default=1.0)
        Gaussian kernel bandwidth. Should be > 0.

    nu : float, optional (default=0.4)
        nu parameter of the OneClassSVM algorithm. Should be in (0, 1].
    """

    def __init__(self, sigma=1.0, nu=0.4):
        gamma = 1. / (2. * sigma ** 2)
        super(OCSVM, self).__init__(gamma=gamma, nu=nu)
        self.sigma = sigma


class IsolationForest(ensemble.IsolationForest):
    """Anomaly detection estimator based on Isolation Forest."""

    def __init__(self,
                 n_estimators=100,
                 max_samples="auto",
                 contamination="auto",
                 max_features=1.,
                 bootstrap=False,
                 n_jobs=None,
                 random_state=None,
                 verbose=0):
        super().__init__(
            n_estimators=n_estimators,
            max_samples=max_samples,
            contamination=contamination,
            max_features=max_features,
            bootstrap=bootstrap,
            n_jobs=n_jobs,
            random_state=random_state,
            behaviour="new",
            verbose=verbose)


class KernelSmoothing(KernelDensity):
    """Anomaly detection estimator based on plug-in approach."""
