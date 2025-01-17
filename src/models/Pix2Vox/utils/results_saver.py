import os

import pandas as pd


def save_test_results_to_csv(samples_names, edlosses, rlosses, ious_dict, path_to_csv):
    data_dict = ious_dict
    data_dict["sample_name"] = samples_names
    data_dict["encoder_loss"] = edlosses
    if len(rlosses) != 0:
        data_dict["refiner_loss"] = rlosses

    results_df = pd.DataFrame(data=data_dict)
    results_df.to_csv(path_to_csv, index=False)


def save_times_to_csv(times, n_views_list, path_to_csv):
    df = pd.DataFrame(data={"time": times,
                            "n_views": n_views_list})
    df.to_csv(path_to_csv, index=False)
