import numpy as np
import sys
import os
import time
from datetime import datetime
import json

sys.path.append("../../anacostia_pipeline")
from engine.node import ResourceNode
from engine.pipeline import Pipeline

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class FeatureStoreNode(ResourceNode, FileSystemEventHandler):
    def __init__(
        self, name: str, 
        path: str, 
        max_old_vectors: int = None, 
    ) -> None:

        # max_old_vectors may be used to limit the number of feature vectors
        # stored in the feature store. If None, then there is no limit.
        # If the number of feature vectors exceeds the limit, then the oldest feature vectors will be deleted.
        self.max_old_vectors = max_old_vectors

        self.feature_store_path = os.path.join(path, "feature_store")
        self.feature_store_json_path = os.path.join(self.feature_store_path, "feature_store.json")
        self.last_checked_time = time.time()
        self.observer = Observer()
        super().__init__(name, "feature_store")
    
    def setup(self) -> None:
        with self.resource_lock:
            if os.path.exists(self.feature_store_json_path) is False:
                os.makedirs(self.feature_store_path, exist_ok=True)

            if os.path.exists(self.feature_store_json_path) is False:
                with open(self.feature_store_json_path, 'w') as json_file:
                    json_entry = {
                        "files": []
                    }
                    json.dump(json_entry, json_file, indent=4)
        
            self.log(f"Setting up node '{self.name}'")
            self.observer.schedule(event_handler=self, path=self.feature_store_path, recursive=True)
            self.observer.start()
            self.log(f"Node '{self.name}' setup complete. Observer started, waiting for file change...")

    def get_current_feature_vectors(self) -> list:
        with self.resource_lock:
            with open(self.feature_store_json_path, 'r') as json_file:
                json_data = json.load(json_file)
                current_feature_vectors_paths = [file_entry["filepath"] for file_entry in json_data["files"] if file_entry["state"] == "current"]

        for path in current_feature_vectors_paths:
            print(path)
            with self.resource_lock:
                try:
                    array = np.load(path)
                    for row in array:
                        yield row

                except Exception as e:
                    self.log(f"Error loading feature vector file: {e}")
                    continue
        
    def on_modified(self, event):
        if not event.is_directory:
            with self.resource_lock:
                with open(self.feature_store_json_path, 'r') as json_file:
                    json_data = json.load(json_file)

                try:
                    if event.src_path.endswith(".npy"):
                        array = np.load(os.path.join(self.feature_store_path, event.src_path))

                        json_entry = {}
                        json_entry["filepath"] = event.src_path
                        json_entry["num_samples"] = array.shape[0]
                        json_entry["shape"] = str(array.shape)
                        json_entry["state"] = "current"
                        json_entry["created_at"] = str(datetime.now())
                        json_data["files"].append(json_entry)

                        self.log(f"New feature vectors detected: {event.event_type} {event.src_path}")

                except Exception as e:
                    self.log(f"Error processing {event.src_path}: {e}")
                
                with open(self.feature_store_json_path, 'w') as json_file:
                    json.dump(json_data, json_file, indent=4)

                # make sure signal is created before triggering
                self.trigger()

            self.last_checked_time = time.time()

    def create_filename(self) -> str:
        """
        Default implementaion to create a filename for the new feature vector file.
        Method can be overridden to create a custom filename; but user must ensure that the filename is unique.
        """
        num_files = len(os.listdir(self.feature_store_path))
        return f"features_{num_files+1}.npy"

    def on_exit(self) -> None:
        self.log(f"Beginning teardown for node '{self.name}'")
        self.observer.stop()
        self.observer.join()
        self.log(f"Observer stopped for node '{self.name}'")