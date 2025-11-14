# model_pipeline/trainer/tests/test_task.py
import unittest
import tensorflow as tf
from ..task import create_model

class TestTask(unittest.TestCase):

    def test_create_model(self):
        """Tests that the model is created with the correct architecture."""
        model = create_model()
        self.assertIsInstance(model, tf.keras.Model)
        self.assertEqual(len(model.layers), 2)
        # For modern Keras, it's better to check the 'units' attribute
        # or build the model first to inspect the output shape.
        self.assertEqual(model.layers[0].units, 16)
        self.assertEqual(model.layers[1].units, 1)

if __name__ == '__main__':
    unittest.main()
