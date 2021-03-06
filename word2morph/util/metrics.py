from pprint import pprint
from typing import Tuple, List, Union

import numpy as np
from keras.callbacks import Callback
from sklearn.metrics import (confusion_matrix, precision_score, recall_score, f1_score,
                             accuracy_score, log_loss, roc_auc_score)
from sklearn.preprocessing import LabelBinarizer

from word2morph.data.generators import DataGenerator


def multi_class_roc_auc_score(y_test, y_pred, average="macro"):
    lb = LabelBinarizer()
    lb.fit(y_test)
    y_test = lb.transform(y_test)
    y_pred = lb.transform(y_pred)
    return roc_auc_score(y_test, y_pred, average=average)


class Evaluate(Callback):
    def __init__(self, data_generator: DataGenerator, to_sample,
                 nb_steps: int = None, prepend_str: str = 'val_'):
        super(Evaluate, self).__init__()
        self.data_generator = data_generator
        self.to_sample = to_sample
        self.nb_steps = nb_steps if nb_steps else len(data_generator)
        self.prepend_str = prepend_str

    def evaluate(self,
                 predictions: List[np.ndarray],
                 labels: List[np.ndarray]) -> Tuple[Tuple[str, Union[float, np.ndarray]], ...]:
        """
        Calculates:
         * word-level accuracy
         * char-level metrics: acc, loss, precision, recall, f1, auc, confusion matrix
        :return confusion_matrix, (word_acc, acc, loss, precision, recall, f1, auc)
        """

        ''' Calculate word-level accuracy '''
        correct = 0
        nb_words = 0
        for batch_prediction, batch_label in zip(predictions, labels):
            correct += sum([np.array_equal(np.argmax(word_prediction, axis=-1), np.argmax(word_label, axis=-1))
                            for word_prediction, word_label in zip(batch_prediction, batch_label)])
            nb_words += len(batch_label)

        ''' Calculate char-level metrics '''
        char_predictions = []
        char_labels = []
        for batch_prediction, batch_label in zip(predictions, labels):
            for word_prediction, word_label in zip(batch_prediction, batch_label):
                char_predictions += word_prediction.tolist()
                char_labels += word_label.tolist()

        char_predictions = np.array(char_predictions)
        char_labels = np.array(char_labels)

        t, p = np.argmax(char_labels, axis=-1), np.argmax(char_predictions, axis=-1)
        return tuple([('confusion_matrix', confusion_matrix(t, p)),
                      ('word_acc', correct / nb_words),
                      ('acc', accuracy_score(t, p)),
                      ('loss', log_loss(char_labels, char_predictions)),
                      ('precision', precision_score(t, p, average='macro')),
                      ('recall', recall_score(t, p, average='macro')),
                      ('f1', f1_score(t, p, average='macro')),
                      ('auc', multi_class_roc_auc_score(t, p))])

    def on_epoch_end(self, epoch, logs=None):
        logs = logs or {}

        epoch_labels = []
        epoch_predictions = []
        epoch_samples = []
        all_samples = []
        for i, (inputs, labels, samples) in zip(range(self.nb_steps), self.data_generator):
            predictions = self.model.predict(inputs)
            epoch_labels.append(labels)
            epoch_predictions.append(predictions)
            epoch_samples.append(samples)
            all_samples += samples

        metrics = self.evaluate(predictions=epoch_predictions, labels=epoch_labels)
        for metric_name, metric_value in metrics:
            logs[self.prepend_str + metric_name] = metric_value

        predicted_samples = []
        for batch_prediction, batch_label, batch_samples in zip(epoch_predictions, epoch_labels, epoch_samples):
            for word_prediction, word_label, word_sample in zip(batch_prediction, batch_label, batch_samples):
                valid_sample = self.to_sample(word=word_sample.word, prediction=word_prediction)
                predicted_samples.append(valid_sample)
        assert len(all_samples) == len(predicted_samples)

        metrics = self.evaluate(predictions=epoch_predictions, labels=epoch_labels)
        for metric_name, metric_value in metrics:
            logs[self.prepend_str + metric_name + '_processed'] = metric_value

        print(f'\nEvaluating for epoch {epoch + 1}...')
        pprint({k: v for k, v in logs.items() if isinstance(v, (int, float, str))})

        correct = [(pred, correct) for correct, pred in zip(all_samples, predicted_samples) if pred == correct]
        wrong = [(pred,   correct) for correct, pred in zip(all_samples, predicted_samples) if pred != correct]
        print('Sample accuracy:', len(correct) / len(all_samples))

        return correct, wrong, predicted_samples
