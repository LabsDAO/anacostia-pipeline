import sys
import os
import json
from typing import List, Any
from datetime import datetime
import time
from logging import Logger

sys.path.append("../../anacostia_pipeline")
from engine.base import BaseResourceNode

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler



class ArtifactStoreNode(BaseResourceNode, FileSystemEventHandler):
    def __init__(
        self, 
        name: str, path: str, tracker_filename: str, 
        init_state: str = "new", max_old_samples: int = None, logger: Logger = None
    ) -> None:

        # TODO: add max_old_samples functionality
        self.max_old_samples = max_old_samples

        self.path = os.path.abspath(path)
        if os.path.exists(self.path) is False:
            os.makedirs(self.path, exist_ok=True)
        
        self.observer = Observer()
        
        if init_state not in ("new", "old"):
            raise ValueError(f"init_state argument of DataStoreNode must be either 'new' or 'old', not '{init_state}'.")
        self.init_state = init_state
        self.init_time = str(datetime.now())
        
        super().__init__(name=name, resource_path=path, tracker_filename=tracker_filename, logger=logger)
    
    @BaseResourceNode.resource_accessor
    def setup(self) -> None:
        self.log(f"Setting up node '{self.name}'")
        self.tracker_filepath = os.path.join(self.anacostia_path, self.tracker_filename)

        if os.path.exists(self.tracker_filepath) is False:
            with open(self.tracker_filepath, "w") as json_file:
                json_entry = {
                    "node": self.name,
                    "resource path": self.path,
                    "node initialization time:": self.init_time,
                    "files": []
                }
                
                if len(os.listdir(self.path)) == 0:
                    self.log(f"Data store is empty at initialization, no files to add to {self.tracker_filename}")
                else:
                    self.log(f"Data store is not empty at initialization, adding files to {self.tracker_filename}")
                    for filepath in os.listdir(self.path):
                        path = os.path.join(self.path, filepath)
                        json_file_entry = {}
                        json_file_entry["filepath"] = os.path.join(path)
                        json_file_entry["state"] = self.init_state
                        json_file_entry["created_at"] = self.init_time
                        json_entry["files"].append(json_file_entry)
                        self.log(f"Added to {self.tracker_filename}: '{filepath}'")
                
                json.dump(json_entry, json_file, indent=4)
                json_file.flush()
                self.log(f"Created tracker file at {self.tracker_filepath}")

        self.log(f"Node '{self.name}' setup complete.")
    
    def start_monitoring(self) -> None:
        self.observer.schedule(event_handler=self, path=self.path, recursive=True)
        self.observer.start()
        self.log(f"Observer started for node '{self.name}' monitoring path '{self.path}'")
    
    @BaseResourceNode.resource_accessor
    def record_artifact(self, filepath: str, log_state: str) -> None:
        with open(self.tracker_filepath, 'r') as json_file:
            json_data = json.load(json_file)
        
        logged_files = [entry["filepath"] for entry in json_data["files"]]
        if filepath not in logged_files:
            json_entry = {}
            json_entry["filepath"] = filepath
            json_entry["state"] = log_state
            json_entry["created_at"] = str(datetime.now())
            json_data["files"].append(json_entry)
        else:
            return

        with open(self.tracker_filepath, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
            json_file.flush()

    @BaseResourceNode.resource_accessor
    def on_modified(self, event):
        if not event.is_directory:
            self.log(f"Detected file: {event.src_path}")
            self.record_artifact(event.src_path, "new") 

    @BaseResourceNode.resource_accessor
    def check_resource(self) -> bool:
        # implement the triggering logic here
        return True
    
    @BaseResourceNode.trap_exceptions
    @BaseResourceNode.resource_accessor
    def create_filename(self) -> str:
        return f"file{self.get_num_artifacts('all')}.txt"
    
    @BaseResourceNode.trap_exceptions
    @BaseResourceNode.resource_accessor
    def save_artifact(self, content: str) -> None:
        pass

    @BaseResourceNode.trap_exceptions
    @BaseResourceNode.resource_accessor
    def list_artifacts(self, state: str) -> List[Any]:
        if state not in ("new", "current", "old", "all"):
            raise ValueError(f"state argument of get_num_artifacts must be either 'new', 'current', 'old', or 'all', not '{state}'.")

        with open(self.tracker_filepath, 'r') as json_file:
            json_data = json.load(json_file)
        
        artifacts = []
        if state == "all":
            for file_entry in json_data["files"]:
                artifacts.append(file_entry["filepath"])
        else:
            for file_entry in json_data["files"]:
                if file_entry["state"] == state:
                    artifacts.append(file_entry["filepath"])
        return artifacts
    
    @BaseResourceNode.trap_exceptions
    @BaseResourceNode.resource_accessor
    def get_num_artifacts(self, state: str) -> int:
        if state not in ("new", "current", "old", "all"):
            raise ValueError(f"state argument of get_num_artifacts must be either 'new', 'current', 'old', or 'all', not '{state}'.")

        with open(self.tracker_filepath, 'r') as json_file:
            json_data = json.load(json_file)
        
        num_artifacts = 0
        if state == "all":
            num_artifacts = len(json_data["files"])
        else:
            for file_entry in json_data["files"]:
                if file_entry["state"] == state:
                    num_artifacts += 1
        return num_artifacts
    
    def update_state(self) -> None:
        if self.get_num_artifacts("new") == 0 and self.get_num_artifacts("current") == 0:
            return

        self.log(f"Updating state of node '{self.name}'")
        with open(self.tracker_filepath, 'r') as json_file:
            json_data = json.load(json_file)

        for file_entry in json_data["files"]:
            if file_entry["state"] == "current":
                self.log(f'{self.name} current -> old: {file_entry["filepath"]}')
                file_entry["state"] = "old"
        
        for file_entry in json_data["files"]:
            if file_entry["state"] == "new":
                self.log(f'{self.name} new -> current: {file_entry["filepath"]}')
                file_entry["state"] = "current"

        with open(self.tracker_filepath, 'w') as json_file:
            json.dump(json_data, json_file, indent=4)
            json_file.flush()
    
    def on_exit(self) -> None:
        self.log(f"Beginning teardown for node '{self.name}'")
        self.observer.stop()
        self.observer.join()
        self.log(f"Observer stopped for node '{self.name}'")