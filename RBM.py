# -*- coding: utf-8 -*-
"""
Created on Sun Dec 27 18:32:44 2015

@author: navrug
"""

"""
Boltzmann Machines (BMs) are a particular form of energy-based model which
contain hidden variables. Restricted Boltzmann Machines further restrict BMs
to those without visible-visible and hidden-hidden connections.
"""

import numpy as np
import sys

def sigmoid(x):
    return 1/(1+np.exp(-x))
    
def softmax(x):
    exp = np.exp(x)
    return exp / np.sum(exp, axis=1)[:,None]

class RBM(object):
    """Restricted Boltzmann Machine (RBM)  """
    def __init__(
        self,
        n_visible,
        n_hidden,
        batch_size,
        dropout_rate=0.0,
        W=None,
        hbias=None,
        vbias=None,
        np_rng=None,
    ):
        """
        RBM constructor. Defines the parameters of the model along with
        basic operations for inferring hidden from visible (and vice-versa),
        as well as for performing CD updates.

        :param input: None for standalone RBMs or symbolic variable if RBM is
        part of a larger graph.

        :param n_visible: number of visible units
        
        :param n_visible: number of visible units that are labels

        :param n_hidden: number of hidden units"

        :param W: None for standalone RBMs or symbolic variable pointing to a
        shared weight matrix in case RBM is part of a DBN network; in a DBN,
        the weights are shared between RBMs and layers of a MLP

        :param hbias: None for standalone RBMs or symbolic variable pointing
        to a shared hidden units bias vector in case RBM is part of a
        different network

        :param vbias: None for standalone RBMs or a symbolic variable
        pointing to a shared visible units bias
        """

        self.n_visible = n_visible
        self.n_hidden = n_hidden
        self.batch_size = batch_size
        self.dropout_rate = dropout_rate

        if np_rng is None:
            # create a number generator
            np_rng = np.random.RandomState(0)

        if W is None:
            # W is initialized with `initial_W` which is uniformely
            # sampled from -4*sqrt(6./(n_visible+n_hidden)) and
            # 4*sqrt(6./(n_hidden+n_visible)) the output of uniform if
            # converted using asarray to dtype theano.config.floatX so
            # that the code is runable on GPU
        
            # Recurrent error at this line "AttributeError: 'TensorVariable' 
            # object has no attribute 'sqrt'. I try to convert n_visible
            # to int.
        
            # n_visible in a TensorVariable object, see:
            # http://deeplearning.net/software/theano/library/tensor/basic.html
            W = np.asarray(
                    np_rng.uniform(
                        low=-4 * np.sqrt(6. / (n_hidden + n_visible)),
                        high=4 * np.sqrt(6. / (n_hidden + n_visible)),
                        size=(n_visible, n_hidden)
                    ),
                    dtype=float
                )
            
        if hbias is None:
            # create shared variable for hidden units bias
            hbias = np.zeros(n_hidden, dtype=float)

        if vbias is None:
            # create shared variable for visible units bias
            vbias = np.zeros(n_visible, dtype=float)
            
        self.W = W
        self.hbias = hbias
        self.vbias = vbias
        self.persistent = None

        
    def clone(self, rbm_object):
        self.n_visible = rbm_object.n_visible
        self.n_labels = rbm_object.n_labels
        self.n_hidden = rbm_object.n_hidden
        self.W = rbm_object.W
        self.hbias = rbm_object.hbias
        self.vbias = rbm_object.vbias
        
    # TODO: Use logaddexp (and maybe log1p) for numerical stability.
    def propup(self, v, r):
        '''This function propagates the visible units activation upwards to
        the hidden units
        '''
        return r*sigmoid(np.dot(v, self.W) + self.hbias)


    def sample_h_given_v(self, v, r):
        ''' This function infers state of hidden units given visible units.
            Dropout is applied.
            Using rand() instead of binomial() gives a x10 speedup because
            it is faster to sample iid rv.'''
        h_mean = self.propup(v, r)
        return (np.random.uniform(size=h_mean.shape) < h_mean).astype(float)


    def propdown(self, h):
        '''This function propagates the hidden units activation downwards to
        the visible units
        '''
        return sigmoid(np.dot(h, self.W.T) + self.vbias)
        

    def sample_v_given_h(self, h):
        ''' This function infers state of visible units given hidden units.
            Using rand() instead of binomial() gives a x10 speedup because
            it is faster to sample iid rv.'''
        v_mean = self.propdown(h)
        return (np.random.uniform(size=v_mean.shape) < v_mean).astype(float)


    def gibbs_hvh(self, h):
        ''' This function implements one step of Gibbs sampling,
            starting from the hidden state.
            Can be used on batches.'''
        v = self.sample_v_given_h(h)
        return self.sample_h_given_v(v)


    def gibbs_vhv(self, v, r):
        ''' This function implements one step of Gibbs sampling,
            starting from the visible state.
            Can be used on batches.'''
        h = self.sample_h_given_v(v, r)
        return self.sample_v_given_h(h)

        
        

    def update(self, batch, persistent=False, lr=0.1, k=1):
        """This functions implements one step of CD-k or PCD-k

        :param lr: learning rate used to train the RBM

        :param persistent: False for CD, true for PCD.

        :param k: number of Gibbs steps to do in CD-k/PCD-k

        """
        if persistent and self.persistent is None:
            self.persistent = batch.astype(float) # astype produces a deep copy.
                
        # decide how to initialize persistent chain:
        # for CD, we use the sample
        # for PCD, we initialize from the old state of the chain
        if self.persistent is None:
            batch_k = batch.astype(float) # astype produces a deep copy.
        else:
            batch_k = self.persistent[:len(batch),:] # shallow copy.
        
        # Draw dropout.
        dropout = np.random.binomial(size=(len(batch), self.n_hidden), n=1, p=(1-self.dropout_rate))        
        
        # Gibbs sampling
        for j in range(k):
            batch_k = self.gibbs_vhv(batch_k, dropout)
    
        # determine gradients on RBM parameters
        h_mean_0 = self.propup(batch, dropout)
        h_mean_k = self.propup(batch_k, dropout)
        self.W += lr*(np.dot(batch.T, h_mean_0) - np.dot(batch_k.T, h_mean_k))/len(batch)
        self.vbias += lr*(np.mean(batch, axis=0) - np.mean(batch_k, axis=0))
        self.hbias += lr*(np.mean(h_mean_0, axis=0) - np.mean(h_mean_k, axis=0))
        if persistent:
            self.persistent[:len(batch),:] = batch_k # shallow copy.



class SupervisedRBM(RBM):
    
    def __init__(
        self,
        n_visible,
        n_labels,
        n_hidden,
        batch_size,
        dropout_rate=0.0,
        W=None,
        hbias=None,
        vbias=None,
        np_rng=None,
    ):
        RBM.__init__(self,
                     n_visible,
                    n_hidden,
                    batch_size,
                    dropout_rate,
                    W,
                    hbias,
                    vbias,
                    np_rng)
        self.n_labels = n_labels
                    

    def propdown(self, h):
        '''This function propagates the hidden units activation downwards to
        the visible units
        '''
        pre_activation = np.dot(h, self.W.T) + self.vbias
        return softmax(pre_activation[:,:self.n_labels]), sigmoid(pre_activation[:,self.n_labels:])
        
        
    def sample_v_given_h(self, h):
        ''' This function infers state of visible units given hidden units.
            Using rand() instead of binomial() gives a x10 speedup because
            it is faster to sample iid rv.'''
        label_prob, v_mean = self.propdown(h)
        labels = np.zeros((len(h),self.n_labels), dtype=float)
        for i in range(len(h)):
            labels[i,:] = np.random.multinomial(1, label_prob[i,:])
        return np.concatenate((
                    labels,
                    np.random.uniform(size=v_mean.shape) < v_mean)
                ,axis=1)
                
                
    def predict_one(self, v):
        #P(v_{label}|v_{data}) \propto \exp(a_{label}) * \prod_i(1+\exp(b_i + (W[v_{label}|v_{data}])_i))n
        prediction_base = np.concatenate((np.eye(self.n_labels, dtype=float), np.tile(v[self.n_labels:].astype(float),(self.n_labels,1))), axis=1)
        logp = np.sum(np.logaddexp(0, self.hbias + np.dot(prediction_base,self.W)), axis=1) + (self.vbias[:self.n_labels])
        #p = np.prod(1 + np.exp(self.hbias + np.dot(prediction_base,self.W)), axis=1) * np.exp(self.vbias[:self.n_labels])
        return np.argmax(logp)
        
       
    def cv_accuracy(self, test_set):
        count = 0
        for i in range(len(test_set)):
            count += (np.argmax(test_set[i,:self.n_labels]) == self.predict_one(test_set[i,:]))
        return float(count)/len(test_set)
        

#==============================================================================
#     def generate(self, label, k):
#         '''\\
# v^{(0)} := [v_{label}|0]\\
# \text{Repeat k times:} \\
# ~~~~h \sim P(h|v^{(k-1)})\\
# ~~~~v \sim P(v^{(k-1)}|h)\\
# ~~~~v^{(k)} := [v_{label}|v^{(k-1)}_{data}]'''
#         v = np.zeros((1,self.n_visible))
#         v[0,label] = 1
#         count = 0
#         while count < k or v[0,label] != 1:
#             count += 1
#             v = self.gibbs_vhv(v, np.ones((1,self.n_hidden)))
#             print v[0,:self.n_labels]
#         print "Sampled in", count, "iterations."
#         return v
#==============================================================================
        
        
#==============================================================================
#     def generate(self, label, k):
#         '''\\
# v^{(0)} := [v_{label}|0]\\
# \text{Repeat k times:} \\
# ~~~~h \sim P(h|v^{(k-1)})\\
# ~~~~v \sim P(v^{(k-1)}|h)\\
# ~~~~v^{(k)} := [v_{label}|v^{(k-1)}_{data}]'''
# 
#         max_count = 1000
#         best = 0
#         best_count = 0
#         for i in range(k):
#             v = np.zeros((1,self.n_visible))
#             v[0,label] = 1
#             count = 0
#             while count < max_count and v[0,label] == 1:
#                 if count == max_count:
#                     return v
#                 count += 1
#                 save = v
#                 v = self.gibbs_vhv(v, np.ones((1,self.n_hidden)))
#             if count > best_count and np.sum(v) > 5:
#                 best_count = count
#                 best = save
#             print count
#         return best,best_count
#==============================================================================
        
    def generate(self, uniques, label, k, obj_ingr=1, n_chains=10):
        '''Sample from the RBM distribution.
        Since most of the time we get empty recipes, we run a number of chains
        in parallel to produce a satisfying number of recipes.'''
        v_label = np.zeros((n_chains,self.n_labels))
        v_label[:,label] = 1
        v = np.zeros((n_chains,self.n_visible))
        v[:,5] = 1
        v[:,7] = 1
        max_ingr = 0
        recipes = []
        r = np.ones((n_chains,self.n_hidden))
        for i in range(k):
            sys.stdout.write("\rGeneration advancement: %d%%" % (100*float(i)/k))
            sys.stdout.flush()
            v = self.gibbs_vhv(v, r)
            v[:,:self.n_labels] = v_label
            n_ingr = np.sum(v[:,self.n_labels:(self.n_labels+len(uniques))], axis=1)
            if np.max(n_ingr) > max_ingr:
                max_ingr = np.max(n_ingr)
                for j in range(len(v)):
                    if n_ingr[j] > obj_ingr:
                        print i,j, n_ingr[j]
                        num = np.nonzero(v[j,self.n_labels:(self.n_labels+len(uniques))])
                        recipe = uniques[num]
                        print recipe
                        recipes.append(recipe)
        print "Sampled in", k, "iterations, max_ingr is", max_ingr
