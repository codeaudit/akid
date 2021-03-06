"""
Signals propagated in nature are all abstracted as a source. For instance, an
light source (which could be an image source or video source), an audio source,
etc.

As an example, saying in supervised setting, a source is a block that takes no
inputs (since it is a source), and outputs data. A concrete example could be
the source for the MNIST dataset::

    source = MNISTFeedSource(name="MNIST",
                            url='http://yann.lecun.com/exdb/mnist/',
                            work_dir=AKID_DATA_PATH + '/mnist',
                            center=True,
                            scale=True,
                            num_train=50000,
                            num_val=10000)

The above code creates a source for MNIST. It is supposed to provide data for
placeholders of tensorflow through method `get_batch`. Say::

    source.get_batch(100, get_val=False)

would return a tuple of numpy array of `(images, labels)`.

It could be used standalone, or passed to a `Sensor`.

Developer Note
================

A top level abstract class `Source` implements basic semantics of a natural
source. Other abstract classes keep implementing more concrete
sources. Abstract `Source` s need to be inherited and abstract methods
implemented before it could be used. To create a concrete `Source`, you could
use multiple inheritance to compose the `Source` you needs. Available sources
are kept under module `sources`.
"""
import abc
import sys
import inspect
import os
import urllib
import tarfile

import numpy as np
import tensorflow as tf

from .blocks import Block


# Basic model parameters as external flags.
flags = tf.app.flags
FLAGS = flags.FLAGS
flags.DEFINE_boolean('fake_data', False, 'If true, uses fake data '
                     'for unit testing.')


class Source(Block):
    """
    An abstract class to model data source from the world.

    The forms in which certain data arrived varies as many ways as one could
    imagine. This class abstracts this complexity and provides a uniform
    interface for subsequent processing.

    According to how tensorflow supplies data, two ways existed to
    correspondingly, `FeedSource` and `TFSource`.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 url,
                 work_dir="data",
                 validation_rate=None,
                 **kwargs):
        """
        Args:
            url: str
                Uniform Resource Locator. It could point to a file or web
                address, where this source should fetch data from.
            work_dir: str
                Working directory of the `Source`. It may puts temporal files,
                such as downloaded dataset and so on. By default, use a folder
                named data under root directory.
        validation_rate: a percentage
            The proportion of training data to be used as validation set. If
            None, all training data will be used for training.
        """
        super(Source, self).__init__(**kwargs)
        self.url = url
        self.work_dir = work_dir

        if validation_rate:
            assert validation_rate >= 0 and validation_rate < 1,\
                "The percentage used for validation must be between 0-1."
            self.validation_rate = validation_rate
        else:
            self.validation_rate = 0

        if self.url:
            # Only download if url is specified. Ideally, the automatic
            # download is good, however, for fast prototype purpose, normally
            # people do not bother to automate the process, so it is better to
            # support this option.
            self._get_raw_data_if_not_yet()

    def _get_raw_data_if_not_yet(self):
        """
        Download anything pointed by `self.url` and save it under
        `self.work_dir`. If the file is a tarball, it will be extracted.
        """
        if not os.path.exists(self.work_dir):
            os.makedirs(self.work_dir)

        filename = self.url.split('/')[-1]
        filepath = os.path.join(self.work_dir, filename)
        if not os.path.exists(filepath):
            def _progress(count, block_size, total_size):
                sys.stdout.write(
                    '\r>> Downloading %s %.1f%%' %
                    (filename,
                        float(count * block_size) /
                        float(total_size) * 100.0))
                sys.stdout.flush()
            filepath, _ = urllib.urlretrieve(
                self.url, filepath, reporthook=_progress)
            print()
            statinfo = os.stat(filepath)
            print('Succesfully downloaded',
                  filename, statinfo.st_size, 'bytes.')
            # Extract if a tarball.
            suffixes = filename[filename.find('.')+1:]
            if suffixes == 'tar.gz':
                tarfile.open(filepath, 'r:gz').extractall(self.work_dir)

    def data(self):
        """
        This is the first place a multiple outputs mechanism is
        needed. However, a temporary solution is used now, so this method is
        actually not used yet.
        """
        assert False, "Program should not reach here."

    @property
    def training_datum(self):
        """
        An optional property to provide a datum of particular training data
        source. It is not made an abstract method given some sub-classes are
        only able to provide shape information, aka `FeedSource`.
        """
        raise NotImplementedError("The property `training_datum` is not"
                                  " implemented!")
        sys.exit()

    @property
    def val_datum(self):
        """
        An optional property to provide a validation datum of particular data
        source. It is not made abstract for the same reason with
        `training_data`.
        """
        raise NotImplementedError("The property `val_datum` is not"
                                  "implemented!")
        sys.exit()

    @property
    def shape(self):
        """
        An optional property to provide shape of particular training data
        source. It is not made an abstract method since if some `Source` class
        returns data tensor directly, it already contains shape information.
        """
        raise NotImplementedError("The property `shape` is not implemented!")
        sys.exit()


class SupervisedSource(Source):
    """
    An abstract class to model supervised data source.
    """
    @property
    def label_shape(self):
        """
        An optional property to provide shape of particular label of training
        data source. It is not made an abstract method for the same reason with
        `shape` of `Source`.
        """
        raise NotImplementedError("The property `label_shape` is not"
                                  " implemented!")
        sys.exit()

    @property
    def training_label(self):
        """
        An optional property to provide a training label of particular data
        source. It is not made an abstract method given some sub-classes are
        only able to provide shape information.

        If a sub-class decides to use this property, the setup of tensor
        `labels` should be in `_setup`.
        """
        raise NotImplementedError("The property `training_label` is not"
                                  " implemented!")
        sys.exit()

    @property
    def val_label(self):
        """
        An optional property to provide a validation label of particular data
        source. It is not made abstract for the reason same with property
        `training_labels`.

        If a sub-class decides to use this property, the setup of tensor
        `labels` should be in `_setup`.
        """
        raise NotImplementedError("The property `val_label` is not"
                                  " implemented!")
        sys.exit()


class StaticSource(Source):
    """
    An abstract class to model static dataset partitioned into training data
    and test data.
    """
    def __init__(self, num_train, num_val, **kwargs):
        super(StaticSource, self).__init__(**kwargs)
        self.num_train = num_train
        self.num_val = num_val

    @property
    # TODO(Shuai): This property should be used to deal with the case batch
    # cannot divide the number of test data. It should be updated
    # accordingly. For instance, for InMemoryFeedSource, the information comes
    # from `_epochs_completed` of `DataSet`.
    def epochs_completed(self):
        return self._epochs_completed


class FeedSource(Source):
    """
    An abstract class that supplies data in form of numpy.array.

    It does not create any tensor, and only plays the role to supply meta
    information of data to further `FeedSensor`, and of course supply actual
    data.

    Every concrete sub-class should implement a `get_batch` method to actually
    supply data, in the shape desired.
    """
    def __init__(self, center=False, scale=False, **kwargs):
        super(FeedSource, self).__init__(**kwargs)
        self.center = center
        self.scale = scale

    @abc.abstractmethod
    def get_batch(self, num, get_val):
        """
        Return `num` of datum, either in one numpy.array, or a tuple of
        numpy.array.

        Args:
            get_val: Boolean
                If True, get from validation samples or training samples.
        """
        raise NotImplementedError("Each sub `FeedSource` needs to implement"
                                  " this method to actually supply data.")
        sys.exit()


class InMemoryFeedSource(StaticSource, FeedSource):
    """
    An abstract class to load all data into memory.

    This class holds a private member `_data_sets` to hold all data.
    """
    def _setup(self):
        """
        Call `_load` to load datasets into memory.
        """
        # Read the whole dateset into memory.
        self.data_sets = self._load()

    def get_batch(self, num, get_val):
        if get_val:
            return self.data_sets.test.next_batch(num)
        else:
            return self.data_sets.training.next_batch(num)

    def get_all(self, train):
        """
        Get all samples in the source.

        Args:
            train: Boolean
                Get from training samples or test samples.

        Returns:
            dataset: datasets.Dataset
        """
        if train:
            return self.data_sets.training
        else:
            return self.data_sets.test

    @abc.abstractmethod
    def _load(self):
        """
        Load data into memory.

        Returns:
            datasets: dataset.DataSets
        """
        raise NotImplementedError("Each sub `InMemorySouce` needs to implement"
                                  " this method to load data.")
        sys.exit()


class TFSource(StaticSource):
    """
    An abstract class that uses Reader Op of tensorflow to supply data.

    It takes no inputs, and outputs four tensors --- training data, validation
    data, training labels, validation labels. Due to its clear semantics, each
    of those tensors is a property (instead of a list of tensors).

    Since normally usage of `TFSource` accompanies with data augmentation, and
    the way data augmentation works at the granularity of one sample, so
    `_setup` of `TFSource` should initialized `training_datum` and `val_datum`
    to a `tf.Tensor` that returns by some Reader Op of tensorflow. The data
    provided by this class of source has necessary information associated with
    the tensor variable, and could be used directly in the further pipeline.

    Note the optional properties of `Source`, is made abstract, consequently
    mandatory.
    """
    @abc.abstractmethod
    def _setup(self):
        self._read()
        """
        TFSource uses Reader Ops of Tensorflow to read data. So any sub-classes
        of `TFSource` should implement it to actually read data. If it is
        combined with `SupervisedSource`, then setup of `labels` should also be
        put here.
        """
        raise NotImplementedError("Each sub-class of TFSource needs to"
                                  " implement this method to read data!")
        sys.exit()

    @abc.abstractproperty
    def training_datum(self):
        """
        An abstract property to enforce any sub-classes to provide training
        data in form of tf.Tensor.
        """
        raise NotImplementedError("Each sub-class of TFSource needs to"
                                  " implement this method to provide a"
                                  " training datum!")
        sys.exit()

    @abc.abstractproperty
    def val_datum(self):
        """
        An abstract property to enforce any sub-classes to provide training
        data in form of tf.Tensor.
        """
        raise NotImplementedError("Each sub-class of TFSource needs to"
                                  " implement this method to provide"
                                  " a validation datum!")
        sys.exit()

    def _float_feature(self, value):
        """
        Helper method for construct Feature protobuf for tfrecord.

        `_int_feature`, `_bytes_feature` are similar methods.
        Args:
            value: list
                A list that holds float values to store.
        """
        return tf.train.Feature(float_list=tf.train.FloatList(value=value))

    def _int_feature(self, value):
        """
        See `_float_feature`.
        """
        return tf.train.Feature(int64_list=tf.train.Int64List(value=value))

    def _bytes_feature(self, value):
        """
        See `_float_feature`.
        """
        return tf.train.Feature(bytes_list=tf.train.BytesList(value=value))


class ClassificationTFSource(TFSource, SupervisedSource):
    """
    An abstract class supplies data using tfrecords for classification problem.

    It further makes concrete most of the abstract methods of its super
    classes.
    """
    @property
    def training_datum(self):
        return self._training_datum

    @property
    def val_datum(self):
        return self._val_datum

    @property
    def training_label(self):
        return self._training_label

    @property
    def val_label(self):
        return self._val_label

    def _convert_to_tf(self, images, labels, name):
        """
        Take a numpy array of images and corresponding labels and convert it to
        tfrecord format.

        Args:
            images: numpy array
                images of shape of shape [N, H, w, C].
            labels: numpy array of shape [N] or list
                corresponding labels
            name: a str
                The output tfrecord file will be named `name.tfrecords`.
        """
        num_examples = labels.shape[0]
        if images.shape[0] != num_examples:
            raise ValueError("Images size %d does not match label size %d." %
                             (images.shape[0], num_examples))
        row = images.shape[1]
        col = images.shape[2]
        depth = images.shape[3]

        filename = os.path.join(self.work_dir, name + '.tfrecords')
        print('Writing', filename)
        writer = tf.python_io.TFRecordWriter(filename)
        for index in range(num_examples):
            image_raw = np.reshape(images[index], -1).tolist()
            example = tf.train.Example(features=tf.train.Features(
                feature={
                    'height': self._int_feature([row]),
                    'width': self._int_feature([col]),
                    'depth': self._int_feature([depth]),
                    'label': self._int_feature([int(labels[index])]),
                    'image_raw': self._float_feature(image_raw)}))
            writer.write(example.SerializeToString())
        writer.close()


# TODO:
# The following lines are for a cleaner namespace for akid, since those
# modules, classes are introduced to akid by import *. However, if I do this,
# sphinx cannot find those classes as well. I think I should manual type in
# what classes I want in __all__. This change is cascaded --- all inspect code
# are deleted in all modules; no TODO in those places anymore..
# __all__ = [name for name, x in locals().items() if
#            not inspect.ismodule(x) and not inspect.isabstract(x)]
