import keras.backend as K
from keras.layers import Layer
import numpy as np
import itertools

##############################
def my_loss(y_true, y_pred):
    diff = y_true - y_pred
    dist = (y_true[:, 0] - y_true[:, 1]) - (y_pred[:, 0] - y_pred[:, 1])
    mse = (K.square(diff[:, 0]) + K.square(diff[:, 1]) + K.square(dist)) / 3
    return mse


def my_acc(y_true, y_pred):
    true_winner = y_true[:, 0] - y_true[:, 1]
    pred_winner = K.round(y_pred[:, 0] - y_pred[:, 1])
    true_winner = K.round(K.clip(true_winner, -1, 1))
    pred_winner = K.round(K.clip(pred_winner, -1, 1))
    equal_tensor = K.equal(true_winner, pred_winner)
    count_equal = K.sum(K.cast(equal_tensor, "int32"))
    const_minus_one = K.constant(-1, "float32")
    count_all = K.greater_equal(true_winner, const_minus_one)
    count_all = K.sum(K.cast(count_all, "int32"))
    return count_equal / count_all


class ExponentialLayer(Layer):
    def __init__(self, num_outputs):
        super(ExponentialLayer, self).__init__()
        self.num_outputs = num_outputs

    def build(self, input_shape):
        pass

    def call(self, inputs):
        return K.exp(inputs)


class PowLayer(Layer):
    def __init__(self, num_outputs, pow_degree):
        super(PowLayer, self).__init__()
        self.num_outputs = num_outputs
        self.pow_degree = pow_degree

    def build(self, input_shape):
        pass

    def call(self, inputs):
        return K.pow(inputs, self.pow_degree)


class ControlledDropoutLayer(Layer):
    def __init__(self, dropout_list, **kwargs):
        """
        dropout_list: A list of dropout rates to apply at each training step. The length of the list should equal the
                      number of training steps.
        """
        super(ControlledDropoutLayer, self).__init__(**kwargs)
        self.dropout_list = dropout_list
        self.step = 0

    def build(self, input_shape):
        super(ControlledDropoutLayer, self).build(input_shape)

    def call(self, inputs, training=None):
        # Update the dropout rate to the rate corresponding to the current training step
        dropout_conf = self.dropout_list[self.step]
        self.step += 1
        if self.step >= len(self.dropout_list):
            self.step = 0
        # Apply dropout to the inputs
        return inputs * K.constant(dropout_conf)

    # def get_config(self):
    #     config = super().get_config()
    #     config.update({"dropout_list": self.dropout_list})
    #     return config


def dropout_conf_1(hidden_layer_size, opt_hidden_layer_size=None, cnn=False):
    if opt_hidden_layer_size == None:
        opt_hidden_layer_size = hidden_layer_size
    dropout_confs_1 = []
    # input pairs
    do_set = set()
    for i in range(7):
        for x in itertools.permutations(np.arange(7), i):
            dropout = np.ones(14)
            for z in x:
                dropout[(z * 2)] = 0
                dropout[(z * 2) + 1] = 0
            drop_rate = len(x) / 7
            dropout = dropout * (1 / (1 - drop_rate))
            do_set.add(tuple(dropout))

    for s in do_set:
        dropout_confs_1.append(list(s))
    dropout_confs_2 = []
    # add all ones for dropout 1 layer
    for _ in range(127):
        dropout_confs_2.append(list(np.ones(opt_hidden_layer_size)))

    if cnn:
        dropout_confs_1 = np.resize(dropout_confs_1, (len(dropout_confs_1), 16))
        dropout_confs_1 = np.reshape(dropout_confs_1, (len(dropout_confs_1), 4, 4))
    return dropout_confs_1, dropout_confs_2


def dropout_conf_2(hidden_layer_size, cnn=False):
    dropout_confs_1 = []
    do_set = set()
    for i in range(4):
        for x in itertools.permutations(np.arange(4), i):
            # all ones, except important
            dropout = np.ones(14)
            for z in x:
                dropout[(z + 8)] = 0  # 8 other features before
            drop_rate = len(x) / 14
            dropout = dropout * (1 / (1 - drop_rate))
            do_set.add(tuple(dropout))
            # all zeros, except important
            dropout = np.zeros(14)
            dropout[8] = 1
            dropout[9] = 1
            dropout[10] = 1
            dropout[11] = 1
            for z in x:
                dropout[(z + 8)] = 0  # 8 other features before
            drop_rate = (10 + len(x)) / 14
            dropout = dropout * (1 / (1 - drop_rate))
            do_set.add(tuple(dropout))

    for s in do_set:
        dropout_confs_1.append(list(s))
    dropout_confs_2 = []
    # add all ones for dropout 1 layer
    for _ in range(30):
        dropout_confs_2.append(list(np.ones(hidden_layer_size)))
    if cnn:
        dropout_confs_1 = np.resize(dropout_confs_1, (len(dropout_confs_1), 16))
        dropout_confs_1 = np.reshape(dropout_confs_1, (len(dropout_confs_1), 4, 4))
    return dropout_confs_1, dropout_confs_2


def dropout_conf_3(hidden_layer_size, opt_hidden_layer_size=None, cnn=False):
    if opt_hidden_layer_size == None:
        opt_hidden_layer_size = hidden_layer_size
    dropout_confs_1 = []
    # add all ones for dropout 2
    for _ in range(hidden_layer_size * 2):
        dropout_confs_1.append(list(np.ones(14)))
    dropout_confs_2 = []
    # add all ones for dropout 1 layer
    # input pairs
    do_set = set()
    for i in [1]:
        for x in itertools.permutations(np.arange(hidden_layer_size), i):
            dropout = np.ones(hidden_layer_size)
            for z in x:
                dropout[(z)] = 0
            drop_rate = len(x) / hidden_layer_size
            dropout = dropout * (1 / (1 - drop_rate))
            do_set.add(tuple(dropout))
            dropout = np.zeros(hidden_layer_size)
            for z in x:
                dropout[(z)] = 1
            drop_rate = (hidden_layer_size - len(x)) / hidden_layer_size
            dropout = dropout * (1 / (1 - drop_rate))
            do_set.add(tuple(dropout))
    for s in do_set:
        dropout_confs_2.append(list(s))
    if cnn:
        dropout_confs_1 = np.resize(dropout_confs_1, (len(dropout_confs_1), 16))
        dropout_confs_1 = np.reshape(dropout_confs_1, (len(dropout_confs_1), 4, 4))
    return dropout_confs_1, dropout_confs_2
