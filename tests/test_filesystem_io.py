import pickle

import pytest

from utils.filesystem_io import (
    directory_files,
    file_in_directory,
    footballsquads_table_from_file,
    footballsquads_table_to_file,
)


class TestDirectoryFiles:
    def test_returns_all_entries_of_directory(self, tmp_path):
        (tmp_path / "a.pckl").write_bytes(b"a")
        (tmp_path / "b.pckl").write_bytes(b"b")

        assert sorted(directory_files(tmp_path)) == ["a.pckl", "b.pckl"]

    def test_returns_subdirectories_too(self, tmp_path):
        (tmp_path / "sub").mkdir()

        assert directory_files(tmp_path) == ["sub"]

    def test_missing_directory_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            directory_files(tmp_path / "does_not_exist")

    def test_file_path_raises_not_a_directory(self, tmp_path):
        some_file = tmp_path / "file.txt"
        some_file.write_text("x")

        with pytest.raises(NotADirectoryError):
            directory_files(some_file)


class TestFileInDirectory:
    def test_present_filename_returns_true(self, tmp_path):
        (tmp_path / "a.pckl").write_bytes(b"a")

        assert file_in_directory("a.pckl", tmp_path) is True

    def test_absent_filename_returns_false(self, tmp_path):
        assert file_in_directory("nope.pckl", tmp_path) is False

    def test_missing_directory_propagates_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            file_in_directory("a.pckl", tmp_path / "missing")


class TestPickleRoundTrip:
    def test_dict_round_trip(self, tmp_path):
        location = tmp_path / "data.pckl"
        table_data = {"10": ["Player", "MF"], "11": ["Other", "DF"]}

        footballsquads_table_to_file(table_data, location)

        assert footballsquads_table_from_file(location) == table_data

    def test_list_round_trip(self, tmp_path):
        location = tmp_path / "data.pckl"
        table_data = [1, 2, {"a": "b"}]

        footballsquads_table_to_file(table_data, location)

        assert footballsquads_table_from_file(location) == table_data

    def test_accepts_string_path(self, tmp_path):
        location = str(tmp_path / "data.pckl")

        footballsquads_table_to_file({"x": 1}, location)

        assert footballsquads_table_from_file(location) == {"x": 1}

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            footballsquads_table_from_file(tmp_path / "missing.pckl")

    def test_corrupt_pickle_raises(self, tmp_path):
        location = tmp_path / "corrupt.pckl"
        location.write_bytes(b"not a valid pickle")

        with pytest.raises((pickle.UnpicklingError, EOFError)):
            footballsquads_table_from_file(location)
