from typing import List, Tuple, Union

import joblib
import numpy as np
from keras import Model
from keras.utils import CustomObjectScope
from tqdm import tqdm

from word2morph.data.generators import DataGenerator
from word2morph.data.processing import DataProcessor
from word2morph.entities.dataset import Dataset
from word2morph.entities.sample import Sample
from word2morph.models.cnn import CNNModel
from word2morph.models.rnn import RNNModel
from word2morph.util.metrics import Evaluate


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
        dataset: Dataset = Dataset(samples=inputs)
        predicted_samples: List[Sample] = []
        for batch_start in tqdm(range(0, len(dataset), batch_size), disable=not verbose):
            batch = dataset[batch_start: batch_start + batch_size]
            inputs, _ = self.processor.parse(batch, convert_one_hot=False)
            res: np.ndarray = self.model.predict(x=inputs)

            predicted_samples += [self.processor.to_sample(word=sample.word, prediction=prediction)
                                  for sample, prediction in zip(batch, res)]
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
        data_generator: DataGenerator = DataGenerator(dataset=Dataset(samples=inputs),
                                                      processor=self.processor,
                                                      batch_size=batch_size)
        evaluate = Evaluate(data_generator=iter(data_generator), nb_steps=len(data_generator), prepend_str='test_')
        evaluate.model = self.model
        evaluate.on_epoch_end(epoch=0)

        ''' Predict the result and print '''
        predicted_samples = self.predict(inputs=inputs, batch_size=batch_size, verbose=True)
        correct, wrong = [], []
        for correct_sample, predicted_sample in zip(inputs, predicted_samples):
            if predicted_sample == correct_sample:
                correct.append((predicted_sample, correct_sample))
            else:
                wrong.append((predicted_sample, correct_sample))
        print('Word accuracy after filtering only valid combinations:', len(correct) / len(inputs), flush=True)
        return correct, wrong, predicted_samples

    def __getitem__(self, item: Union[str, Sample]) -> Sample:
        sample = Sample(word=item, segments=tuple()) if type(item) == str else item
        inputs, _ = self.processor.parse_one(sample=sample)
        prediction: np.ndarray = self.model.predict(x=np.array([inputs]))[0]
        return self.processor.to_sample(word=sample.word, prediction=prediction)

    def save(self, path):
        joblib.dump(self, filename=path, compress=('lzma', 3))


def load_model(model_path: str) -> Word2Morph:
    with CustomObjectScope({'CNNModel': CNNModel, 'RNNModel': RNNModel}):
        return joblib.load(filename=model_path)