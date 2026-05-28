"""Reserve an experiment ID before writing runners, artifacts, data, or logs.

This is the preferred Hugging Face Hub-style entrypoint: create the experiment
identity first, then put all later files under that reserved ID.
"""

from create_experiment_ticket import main


if __name__ == "__main__":
    main(__doc__)
