"""
Script to combine results from two different measuring stations
The concept is to combine two different results into one result
for a single part measured on the robotic cell.
Each station is generating its own result in a .csv file
Srcipt is generating config.ini file where it suppose to be filled
paths to the folder where machines are outputing the results.
"""

from datetime import datetime
import csv
import configparser
import pathlib
import os
import time
import sys

SCRIPT_PATH = pathlib.Path(__file__).resolve().parent
RESULT_FILE_NAME = "result.csv"
CONFIG_FILE_NAME = "config.ini"
CONFIG_PATH = SCRIPT_PATH / CONFIG_FILE_NAME
RESULT_PATH = SCRIPT_PATH / RESULT_FILE_NAME
DEFAULT_CONFIG = {"marposs": "", "kogame": ""}

config = configparser.ConfigParser()


def create_raw_config_file() -> None:
    """
    Create raw config.ini file in the script directory
    """
    config["Settings"] = DEFAULT_CONFIG
    CONFIG_PATH.touch()
    with open(CONFIG_PATH, "w", encoding="UTF-8") as configfile:
        config.write(configfile)
    # Output message to user
    print(">>> Created config.ini file in the script directory")
    print(">>> Please update the config.ini with the paths to the proper folders\n")
    input(">>> PRESS ENTER TO EXIT ")
    sys.exit()


def get_config_paths() -> tuple:
    """
    Read the config file and return the values for marposs and kogame.
    If the file doesn't exist, create a raw file and close the program.
    """
    marposs_config = ""
    kogame_config = ""
    # Try to read config file. If file do not exists -> Create raw file and close the program
    try:
        with open(CONFIG_PATH, "r", encoding="UTF-8"):
            config.read(CONFIG_PATH)
        marposs_config = config.get("Settings", "marposs")
        kogame_config = config.get("Settings", "kogame")
    except FileNotFoundError:
        print(">>> config.ini not found")
        create_raw_config_file()
    except configparser.Error:
        raise ValueError("Error in config.ini")
    if not marposs_config or not kogame_config:
        raise ValueError("Missing path in config.ini")
    return marposs_config, kogame_config


def validate_paths(*paths: str) -> None:
    """
    Check if the given paths exist. If either path does
    not exist or is not a valid directory, raise a ValueError.
    :param: *paths: The paths to the folders containing measurements,
        as specified in the `config.ini` file.
    :raises ValueError: If path is not a valid directory or does not exist.
    """
    for path in paths:
        path = pathlib.Path(path.replace('"', ""))
        if not path.exists():
            raise ValueError(f"Could not find path {path}")


def get_recently_changed_files(path: str) -> tuple:
    """
    Get the recently modified file
    :param: path:
    :return: file path, modification time
    """
    recent_file = max(
        [os.path.join(path, f) for f in os.listdir(path)], key=os.path.getmtime
    )
    recent_file_mod_time = datetime.fromtimestamp(os.path.getmtime(recent_file))
    # recent_file_mod_time = recent_file_mod_time.strftime("%Y-%m-%d %H:%M:%S")
    return recent_file, recent_file_mod_time


def get_data(file_path: str) -> str:
    """
    Get the result from the last line of the file
    :param: file_path: path to the file which we need to get data
    :return: result line as a last line of the result file
    """
    with open(file_path, "r", encoding="UTF-8") as data_file:
        # Seek to the end of the file
        data_file.seek(0, os.SEEK_END)
        # Get the file size
        file_size = data_file.tell()
        # Set the chunk size to 1 KB
        chunk_size = 1024
        # Calculate the number of chunks to read
        num_chunks = file_size // chunk_size + (1 if file_size % chunk_size > 0 else 0)
        # Seek back to the beginning of the file
        data_file.seek(0)
        # Read the file in chunks
        data = ""
        for i in range(num_chunks):
            chunk = data_file.read(chunk_size)
            if i == num_chunks - 1:
                # Trim the last chunk to remove any extra characters
                chunk = chunk[: file_size % chunk_size]
            data += chunk
    return data.strip().split("\n")[-1]


def save_results_to_csv(res_line: str) -> None:
    """
    Writing combined data to a resulting file .csv
    :param: result_line: result line of combined data
    :return: Nothing
    """
    try:
        with open(RESULT_PATH, "a", encoding="UTF-8", newline="") as result_file:
            writer = csv.writer(result_file, delimiter=";")
            writer.writerow(res_line.split(";"))
    except IOError:
        raise IOError("Unable to write to a result file")


if __name__ == "__main__":
    MARPOSS_PATH, KOGAME_PATH = get_config_paths()
    validate_paths(MARPOSS_PATH, KOGAME_PATH)
    marposs_latest_file = get_recently_changed_files(MARPOSS_PATH)
    kogame_latest_file = get_recently_changed_files(KOGAME_PATH)
    # MAIN LOOP
    print(">>> Starting to gather results >>>")
    while True:
        # MARPOSS LOOP
        while True:
            (marposs_result_file, marposs_result_file_mod) = get_recently_changed_files(
                MARPOSS_PATH
            )

            if marposs_result_file_mod > marposs_latest_file[1]:
                marposs_result = get_data(marposs_result_file)
                marposs_latest_file = (marposs_result_file, marposs_result_file_mod)
                break

            time.sleep(5)

        # KOGAME LOOP
        while True:
            (kogame_result_file, kogame_result_file_mod) = get_recently_changed_files(
                KOGAME_PATH
            )

            if kogame_result_file_mod > marposs_latest_file[1]:
                kogame_result = get_data(kogame_result_file)
                kogame_latest_file = (kogame_result_file, kogame_result_file_mod)
                break
            time.sleep(5)
        result_line = (
            (marposs_result.strip() + ";" + kogame_result.strip())
            .replace(",", ";")
            .replace(".", ",")
        )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        result = now + ";" + result_line
        print(now + "\t" + "  ".join(result_line.split(";")))
        save_results_to_csv(result)
