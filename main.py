"""
Script to combine results from two different measuring stations
The concept is to combine two different results into one result
for a single part measured on the robotic cell.
Each station is generating its own result in a .csv file
Srcipt is generating config.ini file where it suppose to be filled
paths to the folder where machines are outputing the results.
"""

import configparser
import csv
import os
import pathlib
import sys
import time
from datetime import datetime

import requests

# Parts ID registers on a specific station
R_MARPOSS_CHECKED_ID = 6
R_KOGAME_CHECKED_ID = 5

SCRIPT_PATH = pathlib.Path(__file__).resolve().parent
RESULT_FILE_NAME = "result.csv"
CONFIG_FILE_NAME = "config.ini"
CONFIG_PATH = SCRIPT_PATH / CONFIG_FILE_NAME
RESULT_PATH = SCRIPT_PATH / RESULT_FILE_NAME
DEFAULT_CONFIG = {"marposs": "", "kogame": "", "ip": "http://192.168.88.2"}

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


def get_config() -> tuple:
    """
    Read the config file and return the values for marposs and kogame.
    If the file doesn't exist, create a raw file and close the program.
    """
    marposs_config = ""
    kogame_config = ""
    ip = ""
    # Try to read config file. If file do not exists -> Create raw file and close the program
    try:
        with open(CONFIG_PATH, "r", encoding="UTF-8"):
            config.read(CONFIG_PATH)
        marposs_config = config.get("Settings", "marposs")
        kogame_config = config.get("Settings", "kogame")
        ip = config.get("Settings", "ip")
        ip += "/MD/NUMREG.VA"
    except FileNotFoundError:
        print(">>> config.ini not found")
        create_raw_config_file()
    except configparser.Error:
        raise ValueError("Error in config.ini")
    if not marposs_config or not kogame_config:
        raise ValueError("Missing path in config.ini")
    return marposs_config, kogame_config, ip


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


def validate_ip(ip: str):
    if not requests.get(url=ip).status_code == 200:
        raise requests.ConnectionError(f"Cannot connect to ip {ip}")


def get_all_registers() -> list:
    """ get all registers from the fanuc Web Server 

    Returns:
        list: all registers from the fanuc Web Server
    """
    path = SCRIPT_PATH / "registers.txt"
    with open(path) as file:
        content = file.read()
    # content = str(requests.get(url=IP).content)
    content = content[content.find("OF Numeric Reg") :]
    content = (
        content.replace("\\r", "")
        .replace("\\'\\'", "")
        .replace(" ", "")
        .replace("\\'", "'")
    )
    content = content.split("\\n")

    return content[:201]


def get_stations_ID() -> tuple:
    stations_ID: list = []
    R_IDs = (R_MARPOSS_CHECKED_ID, R_KOGAME_CHECKED_ID)
    registers = get_all_registers()
    for station_ID in R_IDs:
        unformatted = registers[station_ID]
        if "'" in unformatted:
            value = int(unformatted[unformatted.rfind("=") + 1 : unformatted.find("'")])
        else:
            value = int(unformatted[unformatted.rfind("=") + 1 :])
        stations_ID.append(value)
    return stations_ID


def get_recently_changed_files(path: str) -> tuple:
    """
    Get the recently modified .csv file in the specified directory and its subdirectories.
    
    :param path: The directory path to search for .csv files.
    :return: A tuple containing the file path and the modification time of the recently modified .csv file,
        or None if no .csv file is found.
    """
    recent_file = None

    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            if f.lower().endswith('.csv'):
                file_path = os.path.join(dirpath, f)
                mod_time = os.path.getmtime(file_path)
                if recent_file is None or mod_time > os.path.getmtime(recent_file):
                    recent_file = file_path

    return recent_file


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
    marposs_values = {}
    kogame_values = {}
    MARPOSS_PATH, KOGAME_PATH, IP = get_config()
    validate_paths(MARPOSS_PATH, KOGAME_PATH)
    # validate_ip(ip=IP)
    last_marposs_id = 0
    last_kogame_id = 0
    while last_marposs_id == 0 and last_kogame_id == 0:
        last_marposs_id, last_kogame_id = get_stations_ID()

    # MAIN LOOP
    print(">>> Starting to gather results >>>")
    while True:
        marposs_id, kogame_id = get_stations_ID()

        # Check for Marposs ID change
        if marposs_id != last_marposs_id and marposs_id != 0:
            marposs_latest_file = get_recently_changed_files(MARPOSS_PATH)
            marposs_result = get_data(marposs_latest_file)
            marposs_values[marposs_id] = marposs_result
            last_marposs_id = marposs_id

        # Check for Kogame ID change
        if kogame_id != last_kogame_id and kogame_id != 0:
            kogame_latest_file = get_recently_changed_files(KOGAME_PATH)
            kogame_result = get_data(kogame_latest_file)
            kogame_values[kogame_id] = kogame_result
            last_kogame_id = kogame_id
        if kogame_id in marposs_values:
            result_line = (
                kogame_values.pop(kogame_id) + ";" + marposs_values.pop(kogame_id)
            )
            result_line = (
                result_line.replace(",", ";").replace(".", ",")
                + ";"
                + os.path.basename(kogame_latest_file)
                + ";"
                + os.path.basename(marposs_latest_file)
            )
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result = now + ";" + result_line
            print(now + "\t" + "  ".join(result_line.split(";")))
            save_results_to_csv(result)
        time.sleep(3)
