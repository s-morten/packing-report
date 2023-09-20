import os
import pickle


def file_in_directory(filename: str, directory: str) -> bool:
    files = directory_files(directory)
    return filename in files
    
    
def directory_files(directory: str) -> list[str]:
    if os.path.isdir(directory):
        return os.listdir(directory)
    else:
        raise ValueError("Directory does not exist")
    
def table_to_file(table_data, file_location):  
    with open(file_location, "wb") as f:
        pickle.dump(table_data, f, protocol=pickle.HIGHEST_PROTOCOL)

def table_from_file(file_location):
    with open(file_location, "rb") as f:
        table_object = pickle.load(f)
    return table_object