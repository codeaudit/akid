import inspect

import tensorflow as tf

from ..core.blocks import ProcessingLayer
from ..core.jokers import Joker
from ..utils import glog as log


class ReshapeLayer(ProcessingLayer):
    """
    Reshape data. Only intrinsic shape information of output data should be
    given. The dimension of batch size is not needed. If no shape is given, all
    dimensions beyond batch size dimension are flattened.
    """
    def __init__(self, shape=None, **kwargs):
        # Do not do summary since we just reshape the data.
        kwargs["do_summary"] = False
        if "name" not in kwargs:
            kwargs["name"] = "reshape"
        super(ReshapeLayer, self).__init__(**kwargs)
        self.intrinsic_shape = shape

    def _setup(self, input):
        batch_size = input.get_shape().as_list()[0]
        if self.intrinsic_shape:
            shape = list(self.intrinsic_shape)
        else:
            shape = [-1]
        shape.insert(0, batch_size)
        self._data = tf.reshape(input, shape)


class PaddingLayer(ProcessingLayer, Joker):
    """
    Zero padding on height and width dimensions of the input feature map.

    This layer can work with input shape [H, W, C] and [N, H, W, C].
    """
    def __init__(self, padding=[1, 1], **kwargs):
        """
        Args:
            padding: a two-element list or a list whose list is the same as the
                     input data.
                [H, W]. H holds how many padding will be added in height;
                similar W is for width. Padding is added symmetrically for each
                dimension. If not a two-element list, a full length list is
                needed.
        """
        # Do not do summary since we just pad the data.
        kwargs["do_summary"] = False
        if "name" not in kwargs:
            kwargs["name"] = "padding"
        super(PaddingLayer, self).__init__(**kwargs)
        self.padding = padding

    def _setup(self, input):
        shape = input.get_shape().as_list()
        assert len(shape) is 4 or 3,\
            "Shapes other than 4 or 3 are not supported."

        if len(self.padding) is 2:
            if len(shape) is 4:
                _padding = [
                    [0, 0],
                    [self.padding[0], self.padding[0]],
                    [self.padding[1], self.padding[1]],
                    [0, 0]
                ]
            else:
                _padding = [
                    [self.padding[0], self.padding[0]],
                    [self.padding[1], self.padding[1]],
                    [0, 0]
                ]
        else:
            if len(shape) is 4:
                _padding = [
                    [self.padding[0], self.padding[0]],
                    [self.padding[1], self.padding[1]],
                    [self.padding[2], self.padding[2]],
                    [self.padding[3], self.padding[3]]
                ]
            else:
                _padding = [
                    [self.padding[0], self.padding[0]],
                    [self.padding[1], self.padding[1]],
                    [self.padding[2], self.padding[2]]
                ]

        log.info("Padding: {}".format(_padding))
        self._data = tf.pad(input, paddings=_padding)


class MergeLayer(ProcessingLayer):
    """
    Merge layers with the same shape by element-wise addition.
    """
    def _setup(self, inputs):
        shape = inputs[0].get_shape().as_list()
        for t in inputs:
            t_shape = t.get_shape().as_list()
            assert t_shape == shape,\
                "Tensors to merge do not have the same shape as {} (found {})".format(shape, t_shape)

        sum = inputs[0]
        for t in inputs[1:]:
            sum += t

        self._data = sum


class ScatterLayer(ProcessingLayer):
    """
    Scatter the input to a list of tensor according to the scattering indices
    list by the list dimension.

    Args:
        input: Tensor
            The tensor to be scattered
        scatter_list: list
            The list of length of each scattered tensor. As an example, [2,
            3, 4] will scatter input tensor to three tensors: input[0:2],
            input[2:2+3], input[5:5+4]. The last index could be safely
            omitted. If not, and the overall length has not covered the whole
            input, the remaining dimensions in the input will not be used.
    """
    def __init__(self, scatter_len_list, **kwargs):
        self.scatter_len_list = scatter_len_list
        if not kwargs.has_key("name"):
            kwargs["name"] = "scatter"
        super(ScatterLayer, self).__init__(**kwargs)

    def _setup(self, input):
        scattered_list = []
        start_idx = 0
        for length in self.scatter_len_list:
            scattered_list.append(input[..., start_idx:start_idx+length])
            start_idx += length

        self._data = scattered_list

__all__ = [name for name, x in locals().items() if not inspect.ismodule(x)]
