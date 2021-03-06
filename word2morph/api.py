from typing import List, Tuple, overload

import joblib
import numpy as np
from keras import Model
from keras.utils import CustomObjectScope
from keras_contrib.layers import CRF
from keras_contrib.losses import crf_loss
from keras_contrib.metrics import crf_viterbi_accuracy
from tqdm import tqdm

from word2morph.data.generators import DataGenerator
from word2morph.data.processing import DataProcessor
from word2morph.entities.dataset import Dataset
from word2morph.entities.sample import Sample
from word2morph.models.cnn import CNNModel
from word2morph.models.rnn import RNNModel
from word2morph.util.metrics import Evaluate
from word2morph.util.utils import download

BASE_URL = 'https://github.com/MartinXPN/word2morph/releases/download'


class Word2Morph(object):
    def __init__(self, model: Model, processor: DataProcessor):
        self.model = model
        self.processor = processor

    def predict(self, inputs: List[Sample], batch_size: int, verbose: bool = False) -> List[Sample]:
        """
        :param inputs: List of Samples
        :param batch_size: batch size in which to process the data
        :param verbose: display progress or no
        :return: Predicted samples in the order they were given as an input
        """
        data_generator = DataGenerator(dataset=Dataset(samples=inputs), processor=self.processor, batch_size=batch_size,
                                       with_samples=True, shuffle=False)

        predicted_samples: List[Sample] = []
        for inputs, _, samples in tqdm(data_generator, disable=not verbose):
            predictions = self.model.predict(inputs)
            predicted_samples += [self.processor.to_sample(word=sample.word, prediction=prediction)
                                  for sample, prediction in zip(samples, predictions)]
        return predicted_samples

    def evaluate(self, inputs: List[Sample], batch_size: int) -> Tuple[List[Tuple[Sample, Sample]],
                                                                       List[Tuple[Sample, Sample]],
                                                                       List[Sample]]:
        """
        :param inputs: List of Sample-s
        :param batch_size: batch size in which to process the data
        :return: (list of correct predictions, list of wrong predictions, list of all predictions in the input order)
                    each list item is (predicted_sample, correct_sample)
        """
        ''' Show Evaluation metrics '''
        data_generator: DataGenerator = DataGenerator(dataset=Dataset(samples=inputs), processor=self.processor,
                                                      batch_size=batch_size, with_samples=True, shuffle=False)
        evaluate = Evaluate(data_generator=data_generator, to_sample=self.processor.to_sample,
                            nb_steps=len(data_generator), prepend_str='test_')
        evaluate.model = self.model
        return evaluate.on_epoch_end(epoch=0)

    @overload
    def __getitem__(self, item: str) -> Sample:
        ...

    @overload
    def __getitem__(self, item: Sample) -> Sample:
        ...

    def __getitem__(self, item) -> Sample:
        sample = Sample(word=item, segments=tuple()) if type(item) == str else item
        inputs, _ = self.processor.parse_one(sample=sample)
        prediction: np.ndarray = self.model.predict(x=np.array([inputs]))[0]
        return self.processor.to_sample(word=sample.word, prediction=prediction)

    def save(self, path):
        joblib.dump(self, filename=path, compress=('lzma', 3))

    @classmethod
    @overload
    def load_model(cls, path: str) -> 'Word2Morph':
        ...

    @classmethod
    @overload
    def load_model(cls, url: str, path: str) -> 'Word2Morph':
        ...

    @classmethod
    @overload
    def load_model(cls, locale: str, version: str = None) -> 'Word2Morph':
        ...

    @classmethod
    def load_model(cls, path: str = None, url: str = None, locale: str = None, version: str = None) -> 'Word2Morph':
        from word2morph import __version__

        if locale:
            version = version or __version__
            url = f'{BASE_URL}/v{version}/{locale}.joblib'
            path = path or f'logs/{locale}-{version}.joblib'

        if url and path:
            download(url, path, exists_ok=True)
        elif url:
            raise ValueError('Both URL and save path needs to be specified!')

        with CustomObjectScope({'CNNModel': CNNModel, 'RNNModel': RNNModel,
                                'CRF': CRF, 'crf_loss': crf_loss, 'crf_viterbi_accuracy': crf_viterbi_accuracy}):
            return joblib.load(filename=path)
