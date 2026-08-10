import pickle
from pathlib import Path
from typing import Any


def file_in_directory(filename: str, directory: str | Path) -> bool:
    files = directory_files(directory)
    return filename in files


def directory_files(directory: str | Path) -> list[str]:
    path = Path(directory)
    if not path.exists():
        raise FileNotFoundError(f"directory {directory!r} does not exist")
    if not path.is_dir():
        raise NotADirectoryError(f"{directory!r} is not a directory")
    return [entry.name for entry in path.iterdir()]


def footballsquads_table_to_file(table_data: Any, file_location: str | Path) -> None:
    with open(Path(file_location), "wb") as f:
        pickle.dump(table_data, f, protocol=pickle.HIGHEST_PROTOCOL)


def footballsquads_table_from_file(file_location: str | Path) -> Any:
    with open(Path(file_location), "rb") as f:
        table_object = pickle.load(f)
    return table_object
