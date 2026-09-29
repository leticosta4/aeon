"""Tests for aeon CI workflow configuration."""

from pathlib import Path

import pytest
import yaml

from aeon.testing.testing_config import _get_pr_subsample_index

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_pr_subsample_covers_pr_pytest_matrix():
    """Test that PR runs test all estimators on each OS and Python version.

    Reads the pytest job matrix from the PR workflow, so this fails if the workflow
    OS or Python versions change without updating _get_pr_subsample_index.

    A matrix spanning several operating systems must cover all three subsamples on
    every OS and on every Python version. A single-OS matrix can only map one
    subsample per Python version, so for those the matrix as a whole must cover all
    three subsamples.
    """
    # workflow files are not shipped with the package, only test a repository checkout
    if not (REPO_ROOT / ".github").exists():
        pytest.skip("Tests are not being run from a repository checkout.")

    workflow = REPO_ROOT / ".github" / "workflows" / "pr_pytest.yml"
    assert workflow.exists(), f"PR pytest workflow not found at {workflow}."

    with open(workflow, encoding="utf-8") as f:
        workflow_config = yaml.safe_load(f)

    try:
        matrix = workflow_config["jobs"]["pytest"]["strategy"]["matrix"]
        runners = matrix["os"]
        versions = matrix["python-version"]
    except (KeyError, TypeError) as e:
        raise AssertionError(
            f"Could not find the pytest job OS and Python version matrix in "
            f"{workflow.name}."
        ) from e

    # matrix entries which are removed when running with PR testing
    pr_excludes = [e for e in matrix.get("exclude", []) if e.get("pr-testing") is True]

    runner_systems = {"ubuntu": "Linux", "macos": "Darwin", "windows": "Windows"}
    os_indices = {}
    version_indices = {}
    for runner in runners:
        os_str = [s for r, s in runner_systems.items() if runner.lower().startswith(r)]
        assert len(os_str) == 1, f"Unknown OS for runner {runner} in {workflow.name}."

        for version in versions:
            if any(
                e.get("os", runner) == runner
                and e.get("python-version", version) == version
                for e in pr_excludes
            ):
                continue

            i = _get_pr_subsample_index(int(str(version).split(".")[1]), os_str[0])
            os_indices.setdefault(runner, set()).add(i)
            version_indices.setdefault(version, set()).add(i)

    # subsample indices of the combinations which actually run with PR testing
    all_indices = set().union(*os_indices.values())

    scopes = [(f"OS {name}", indices) for name, indices in os_indices.items()]
    scopes += [(f"Python {name}", indices) for name, indices in version_indices.items()]
    if len(os_indices) == 1:
        # a single OS maps one subsample per Python version, so requiring all three
        # subsamples per version would need one job per version per OS
        scopes = [("the matrix in total", all_indices)]

    for scope, indices in scopes:
        assert indices == {0, 1, 2}, (
            f"PR runs for {scope} in {workflow.name} only test estimator subsamples "
            f"{sorted(indices)}, update _get_pr_subsample_index or the workflow "
            f"matrix so that every subsample is tested on each OS and Python version."
        )
