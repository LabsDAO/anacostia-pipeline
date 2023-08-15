import unittest
import logging
import sys
import os
import shutil
import time

sys.path.append('..')
sys.path.append('../anacostia_pipeline')
from anacostia_pipeline.resource.feature_store import FeatureStoreNode

import random
from test_utils import *


# Set the seed for reproducibility
seed_value = 42
random.seed(seed_value)

# Create a logger
log_path = "./testing_artifacts/feature_store.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename=log_path,
    filemode='w'
)
logger = logging.getLogger(__name__)


class NodeTests(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        if os.path.exists("./testing_artifacts") is False:
            os.makedirs("./testing_artifacts")
            os.chmod("./testing_artifacts", 0o777)
        
        self.feature_store_node = FeatureStoreNode(name="feature_store", path="./testing_artifacts")
        self.feature_store_node.set_logger(logger)

        super().__init__(methodName)
    
    """
    def test_setup(self):
        self.feature_store_node.start()
        with self.feature_store_node.resource_lock:
            self.assertTrue(os.path.exists("./testing_artifacts/feature_store"))
            self.assertTrue(os.path.exists("./testing_artifacts/feature_store/feature_store.json"))
        self.feature_store_node.stop()
        self.feature_store_node.join()
    """

    def test_get_current_feature_vectors(self):
        self.feature_store_node.start()
        time.sleep(1)
        with self.feature_store_node.resource_lock:
            for i in range(5):
                random_number = random.randint(0, 100)
                create_numpy_file(
                    file_path=f"./testing_artifacts/feature_store/feature_{i}.npy", 
                    shape=(random_number, 3)
                )
        time.sleep(1)
        self.feature_store_node.stop()
        self.feature_store_node.join()
    
    def tearDown(self) -> None:
        try:
            shutil.move("./testing_artifacts/feature_store/feature_store.json", "./testing_artifacts/feature_store.json")
            shutil.rmtree("./testing_artifacts/feature_store")
        except OSError as e:
            print(f"Error occurred: {e}")
        

if __name__ == "__main__":
    unittest.main()